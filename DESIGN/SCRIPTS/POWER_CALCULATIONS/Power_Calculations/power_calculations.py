import json
import math
import datetime

class Config:
    """
    CENTRAL CONFIGURATION & CONSTANTS
    ---------------------------------
    """
    # --- IPC-2221 STANDARDS (External Layers) ---
    IPC_K = 0.048
    IPC_B = 0.44
    IPC_C = 0.725
    IPC_TEMP_RISE_C = 10 
    
    # 1oz Copper = approx 1.37 mils (35um) thickness
    IPC_THICKNESS_MILS_PER_OZ = 1.37 

    # --- MANUFACTURING LIMITS (DfM) ---
    # Note: For 1oz copper, you can technically go down to 0.15mm, 
    # but 0.25mm is a safer default for all weights.
    DFM_MIN_SIGNAL_WIDTH_MM = 0.25  
    
    # --- ENGINEERING SAFETY FACTORS ---
    SAFETY_FACTOR_POWER_RAILS = 2.5  
    
    # --- MECHANICAL ROBUSTNESS ---
    MIN_WIDTH_AC_MAINS_MM = 1.00     
    MIN_WIDTH_POWER_RAIL_MM = 0.40   
    
    # --- LOGIC THRESHOLDS ---
    THRESHOLD_POLYGON_AMPS = 15.0    
    THRESHOLD_POWER_NET_AMPS = 0.1   
    DEFAULT_SIGNAL_LOAD_AMPS = 0.05  

# --- CORE CALCULATION ENGINE ---

def calc_ipc_width_mm(amps, copper_weight_oz):
    """
    Calculates minimum trace width based on Load and Copper Weight.
    Formula: Width[mils] = (Amps / (k * dT^b))^(1/c) / Thickness[mils]
    """
    if amps <= 0: return Config.DFM_MIN_SIGNAL_WIDTH_MM
    
    # Dynamic Thickness Calculation
    thickness_mils = copper_weight_oz * Config.IPC_THICKNESS_MILS_PER_OZ
    
    # Denominator: k * dT^b
    denom = Config.IPC_K * (Config.IPC_TEMP_RISE_C ** Config.IPC_B)
    
    # Calculate Area (mils^2) and Width (mils)
    area_mils2 = (amps / denom) ** (1 / Config.IPC_C)
    width_mils = area_mils2 / thickness_mils
    
    # Convert to mm
    return max(width_mils * 0.0254, Config.DFM_MIN_SIGNAL_WIDTH_MM)

def get_trace_recommendation(name, load_amps, calculated_width_mm):
    """Applies Engineering Rules and Safety Factors."""
    
    # 1. High Current -> Polygon Pour
    if load_amps > Config.THRESHOLD_POLYGON_AMPS:
        return "**POLYGON POUR**"
    
    # 2. AC Mains -> Mechanical Strength Rule
    if "AC_" in name:
        rec = max(calculated_width_mm, Config.MIN_WIDTH_AC_MAINS_MM)
        return f"**{rec:.2f} mm** (Mech)"
    
    # 3. DC Power Rails -> Safety Factor Rule
    if load_amps > Config.THRESHOLD_POWER_NET_AMPS:
        target = calculated_width_mm * Config.SAFETY_FACTOR_POWER_RAILS
        rec = max(target, Config.MIN_WIDTH_POWER_RAIL_MM)
        rec = math.ceil(rec * 20) / 20.0 # Round to 0.05mm
        return f"**{rec:.2f} mm** (SF={Config.SAFETY_FACTOR_POWER_RAILS})"
        
    # 4. Standard Signals
    return f"**{Config.DFM_MIN_SIGNAL_WIDTH_MM} mm**"

def calculate_ac_input(dc_power_watts, efficiency, mains_voltage):
    ac_input_watts = dc_power_watts / efficiency
    ac_input_amps = ac_input_watts / mains_voltage
    return ac_input_watts, ac_input_amps

# --- DATA PROCESSING HELPERS ---

def process_dc_components(components):
    rows = ""
    total_ma = 0
    rail_3v3_ma = 0
    relay_coil_total_ma = 0

    for c in components:
        tot = c['peak_current_ma'] * c['quantity']
        volts = c.get('voltage_v', 5.0)
        
        total_ma += tot
        
        if volts < 4.5:
            rail_3v3_ma += tot
            
        if "Coil" in c['name'] or "Relay" in c['name']:
            relay_coil_total_ma += tot
            
        rows += f"| {c['name']} | {volts}V | {c['quantity']} | {c['peak_current_ma']} | {tot:.1f} |\n"
    
    return rows, total_ma, rail_3v3_ma, relay_coil_total_ma

def build_width_targets(data, design_load_psu, rail_3v3_load, relay_gnd_load, ac_amps):
    targets = []
    
    for line in data['ac_power_lines']:
        targets.append((line['name'], line['max_current_a']))
        
    targets.append(("AC_MAINS_INPUT", ac_amps))
    targets.append(("DC_MAIN_5V", design_load_psu / 1000.0))
    targets.append(("DC_3V3_RAIL", rail_3v3_load / 1000.0))
    targets.append(("DC_RELAY_GND", relay_gnd_load / 1000.0))
    targets.append(("DC_SIGNAL", Config.DEFAULT_SIGNAL_LOAD_AMPS))
    
    return targets

def generate_ac_table_rows(targets, sys_volts):
    rows = ""
    for name, amps in targets:
        if "AC_" in name: 
            pwr_kw = (sys_volts * amps) / 1000.0
            rows += f"| {name} | {sys_volts}V | {amps:.3f} A | {pwr_kw:.3f} kW |\n"
    return rows

def generate_width_table_rows(targets, copper_oz):
    rows = ""
    for name, amps in targets:
        # PASS COPPER WEIGHT TO CALC FUNCTION
        phys_min = calc_ipc_width_mm(amps, copper_oz)
        rec_str = get_trace_recommendation(name, amps, phys_min)
        rows += f"| {name} | {amps:.3f} | {phys_min:.3f} mm | {rec_str} |\n"
    return rows

# --- FILE OPERATIONS ---

def load_json(path):
    with open(path, 'r', encoding='utf-8') as f: return json.load(f)

def write_markdown(path, content):
    with open('report_template.md', 'r', encoding='utf-8') as t: template = t.read()
    with open(path, 'w', encoding='utf-8') as f: f.write(template.format(**content))

# --- MAIN EXECUTION ---

def main():
    # 1. Load Data
    data = load_json('peak_data.json')
    sys = data['system_info']
    psu = data['power_supply']

    # 2. Analyze DC Components
    dc_rows, total_dc_ma, rail_3v3_ma, relay_gnd_ma = process_dc_components(data['dc_components'])
    
    # 3. Design Loads
    design_load_psu = total_dc_ma * (1 + sys['safety_margin_percent']/100)
    design_load_3v3 = rail_3v3_ma * (1 + sys['safety_margin_percent']/100)
    
    psu_status = "✅ **PASS**" if design_load_psu <= psu['max_output_current_ma'] else "❌ **FAIL**"

    # 4. Analyze AC Input
    dc_watts = (design_load_psu / 1000.0) * sys['main_voltage_rail_dc_v']
    ac_watts, ac_amps = calculate_ac_input(dc_watts, psu.get('efficiency', 0.7), sys['mains_voltage_ac_v'])

    # 5. Build Targets
    width_targets = build_width_targets(data, design_load_psu, design_load_3v3, relay_gnd_ma, ac_amps)

    # 6. Generate Tables (PASSING COPPER OZ)
    ac_table_rows = generate_ac_table_rows(width_targets, sys['mains_voltage_ac_v'])
    width_table_rows = generate_width_table_rows(width_targets, sys['copper_weight_oz'])

    # 7. Compile Report
    content = {
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
        "design_load": design_load_psu,
        "psu_status": psu_status,
        "ac_load_rows": ac_table_rows.strip(),
        "trace_width_rows": width_table_rows.strip()
    }

    write_markdown('PCB_Engineering_Report.md', content)
    print(f"✅ Report generated using {sys['copper_weight_oz']}oz Copper logic.")

if __name__ == "__main__":
    main()