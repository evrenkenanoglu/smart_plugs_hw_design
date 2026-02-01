import json
import math
import datetime

# --- CONSTANTS ---
K, B, C = 0.048, 0.44, 0.725  # IPC-2221 Constants for External Layers

# --- CONFIGURATION ---
SAFETY_FACTOR_POWER = 2.5  # Multiplier for DC Power Rails (Robustness)
MIN_WIDTH_POWER = 0.40     # Minimum mm for any power rail
MIN_WIDTH_SIGNAL = 0.25    # Minimum mm for signals
MIN_WIDTH_AC_MECH = 1.00   # Minimum mm for AC Mains (Mechanical strength)

# --- CORE CALCULATION FUNCTIONS ---

def calc_ipc_width_2oz(amps):
    """Calculates min trace width (mm) for 2oz copper per IPC-2221."""
    if amps <= 0: return 0.2
    # Width(mils) = [Amps / (k * dT^b)]^(1/c) / Thickness(mils)
    # 2oz thickness approx 2.74 mils
    width_mils = ((amps / (K * (10 ** B))) ** (1 / C)) / 2.74
    return max(width_mils * 0.0254, 0.2)

def get_trace_recommendation(name, load, calculated_width):
    """
    Calculates the recommended rule PROPORTIONALLY based on load.
    Formula: Recommended = Max(Calculated * SafetyFactor, Min_Floor)
    """
    
    # 1. High Power AC (>15A) -> Physical Limit Reached
    if load > 15:
        return "**POLYGON POUR**"
    
    # 2. AC Mains Input (Low Current but High Voltage/Mech Stress)
    # Enforce mechanical floor of 1.0mm, otherwise proportional
    elif "AC_" in name:
        rec = max(calculated_width, MIN_WIDTH_AC_MECH)
        return f"**{rec:.2f} mm**"
    
    # 3. DC Power Rails (> 100mA)
    # Apply Safety Factor (2.5x) for voltage stability
    elif load > 0.1:
        # Proportional Calculation
        target = calculated_width * SAFETY_FACTOR_POWER
        
        # Apply Floor
        rec = max(target, MIN_WIDTH_POWER)
        
        # Round to nearest 0.05mm for neatness
        rec = math.ceil(rec * 20) / 20.0
        return f"**{rec:.2f} mm** (SF={SAFETY_FACTOR_POWER})"
        
    # 4. Low Power Signals
    else:
        return f"**{MIN_WIDTH_SIGNAL} mm**"

def calculate_ac_input(dc_power_watts, efficiency, mains_voltage):
    """Calculates required AC input based on DC power draw."""
    ac_input_watts = dc_power_watts / efficiency
    ac_input_amps = ac_input_watts / mains_voltage
    return ac_input_watts, ac_input_amps

# --- REPORT GENERATION HELPERS ---

def generate_dc_report_data(components):
    """Processes DC components."""
    rows = ""
    total_ma = 0
    rail_3v3_ma = 0

    for c in components:
        tot = c['peak_current_ma'] * c['quantity']
        volts = c.get('voltage_v', 5.0)
        
        total_ma += tot
        if volts < 4.5:
            rail_3v3_ma += tot
            
        rows += f"| {c['name']} | {volts}V | {c['quantity']} | {c['peak_current_ma']} | {tot:.1f} |\n"
    
    return rows, total_ma, rail_3v3_ma

def generate_ac_report_data(ac_lines, calc_input_amps, calc_input_watts, sys_volts):
    """Generates table rows for AC lines."""
    rows = ""
    width_targets = []

    for line in ac_lines:
        current = line['max_current_a']
        pwr_kw = (line['voltage_v'] * current) / 1000
        rows += f"| {line['name']} | {line['voltage_v']}V | {current} A | {pwr_kw:.1f} kW |\n"
        width_targets.append((line['name'], current))

    rows += f"| AC_MAINS_INPUT (Calc) | {sys_volts}V | {calc_input_amps:.3f} A | {calc_input_watts/1000:.3f} kW |\n"
    width_targets.append(("AC_MAINS_INPUT", calc_input_amps))

    return rows, width_targets

def generate_trace_width_rows(ac_targets, dc_design_load, rail_3v3_load):
    """Combines AC and DC targets."""
    targets = ac_targets.copy()
    
    # Add DC Targets
    targets.append(("DC_MAIN_5V", dc_design_load / 1000))
    targets.append(("DC_3V3_RAIL", rail_3v3_load / 1000))
    targets.append(("DC_RELAY_GND", 0.216 * 4))
    targets.append(("DC_SIGNAL", 0.05))

    rows = ""
    for name, load in targets:
        calc_mm = calc_ipc_width_2oz(load)
        rec_str = get_trace_recommendation(name, load, calc_mm)
        rows += f"| {name} | {load:.3f} | {calc_mm:.3f} mm | {rec_str} |\n"
    
    return rows

# --- FILE I/O ---

def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def write_report(content, template_path, output_path):
    with open(template_path, 'r', encoding='utf-8') as t:
        template = t.read()
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(template.format(**content))

# --- MAIN ORCHESTRATOR ---

def main():
    data = load_json('peak_data.json')
    sys = data['system_info']
    psu = data['power_supply']

    dc_rows, total_dc_ma, rail_3v3_ma = generate_dc_report_data(data['dc_components'])
    
    design_load_psu_ma = total_dc_ma * (1 + sys['safety_margin_percent']/100)
    design_load_3v3_ma = rail_3v3_ma * (1 + sys['safety_margin_percent']/100)
    
    psu_status = "✅ **PASS**" if design_load_psu_ma <= psu['max_output_current_ma'] else "❌ **FAIL**"

    dc_power_watts = (design_load_psu_ma / 1000.0) * sys['main_voltage_rail_dc_v']
    ac_in_watts, ac_in_amps = calculate_ac_input(
        dc_power_watts, 
        psu.get('efficiency', 0.7), 
        sys['mains_voltage_ac_v']
    )

    ac_rows, width_targets = generate_ac_report_data(
        data['ac_power_lines'], 
        ac_in_amps, 
        ac_in_watts, 
        sys['mains_voltage_ac_v']
    )

    trace_rows = generate_trace_width_rows(
        width_targets, 
        design_load_psu_ma, 
        design_load_3v3_ma
    )

    report_content = {
        "project_name": sys['project_name'],
        "date": datetime.date.today(),
        "copper_oz": sys['copper_weight_oz'],
        "ac_volts": sys['mains_voltage_ac_v'],
        "dc_volts": sys['main_voltage_rail_dc_v'],
        "psu_name": psu['name'],
        "psu_limit": psu['max_output_current_ma'],
        "dc_load_rows": dc_rows.strip(),
        "total_peak": total_dc_ma,
        "safety_margin": sys['safety_margin_percent'],
        "design_load": design_load_psu_ma,
        "psu_status": psu_status,
        "ac_load_rows": ac_rows.strip(),
        "trace_width_rows": trace_rows.strip()
    }

    write_report(report_content, 'report_template.md', 'PCB_Engineering_Report.md')
    print("✅ PCB_Engineering_Report.md generated successfully.")

if __name__ == "__main__":
    main()