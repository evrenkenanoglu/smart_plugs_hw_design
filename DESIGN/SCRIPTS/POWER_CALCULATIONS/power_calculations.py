import json
import math

# --- CONSTANTS ---
# IPC-2221 External Layer Constants
K_IPC = 0.048
B_IPC = 0.44
C_IPC = 0.725

# IEC/IPC Clearance Guidelines (Simplified for Pollution Degree 2, Coated Board)
# Values in mm
RULES_CLEARANCE = {
    "DC_Low_Voltage": 0.15,   # < 15V (IPC Min)
    "AC_Mains_Func": 1.5,     # 230V Phase-Neutral (IEC 60950 Basic)
    "AC_to_DC_Iso": 3.0       # 230V Primary-Secondary (Reinforced - Compact)
}

RULES_CREEPAGE = {
    "DC_Low_Voltage": 0.15,
    "AC_Mains_Func": 2.5,     # Surface distance (Pollution Deg 2)
    "AC_to_DC_Iso": 5.0       # Safe separation for Reinforced Insulation
}

def calculate_ipc_width_2oz(current_amps, temp_rise_c=10):
    """ Calculates 2oz Copper Trace Width (mm) per IPC-2221 """
    if current_amps <= 0: return 0.2
    thickness_mils = 2.74 # 2oz
    denom = K_IPC * (temp_rise_c ** B_IPC)
    area_mils2 = (current_amps / denom) ** (1 / C_IPC)
    width_mils = area_mils2 / thickness_mils
    return max(width_mils * 0.0254, 0.2)

def analyze_system(json_file):
    with open(json_file, 'r') as f:
        data = json.load(f)

    sys = data['system_info']
    print(f"\n============================================================")
    print(f"🏗️  PCB ENGINEERING REPORT: {sys['project_name']}")
    print(f"   Spec: {sys['copper_weight_oz']}oz Copper | 230V AC | 5V DC")
    print(f"============================================================")

    # --- 1. DC POWER ANALYSIS ---
    print(f"\n🔋 PART 1: POWER SUPPLY LOAD")
    print(f"{'COMPONENT':<25} | {'QTY':<4} | {'PEAK (mA)':<10} | {'TOTAL (mA)'}")
    print("-" * 65)
    total_dc = 0
    for comp in data['dc_components']:
        tot = comp['peak_current_ma'] * comp['quantity']
        total_dc += tot
        print(f"{comp['name']:<25} | {comp['quantity']:<4} | {comp['peak_current_ma']:<10.1f} | {tot:<10.1f}")
    
    margin_load = total_dc * (1 + sys['safety_margin_percent']/100)
    psu = data['power_supply']
    status = "✅ PASS" if margin_load <= psu['max_output_current_ma'] else "❌ FAIL"
    
    print("-" * 65)
    print(f"TOTAL PEAK (Calc):       {total_dc:.1f} mA")
    print(f"DESIGN LOAD (+{sys['safety_margin_percent']}%):      {margin_load:.1f} mA")
    print(f"PSU LIMIT ({psu['name']}):  {psu['max_output_current_ma']:.1f} mA  -> {status}")

    # --- 2. TRACE WIDTHS ---
    print(f"\n\n📏 PART 2: TRACE WIDTHS (2oz Copper / +10°C Rise)")
    print(f"{'NET FUNCTION':<20} | {'LOAD (A)':<8} | {'MIN (mm)':<10} | {'ALTIUM RULE (mm)'}")
    print("-" * 70)
    
    targets = [
        ("AC_LOAD_20A", 20.0),
        ("DC_MAIN_5V", margin_load/1000),
        ("DC_RELAY_GND", 0.216 * 4),
        ("DC_ESP32", 0.5),
        ("DC_SIGNAL", 0.05)
    ]
    
    for name, load in targets:
        w_min = calculate_ipc_width_2oz(load)
        if load > 10:
            rec = "POLYGON"
        else:
            rec = math.ceil(w_min * 10)/10 + 0.1 # Round up + 0.1 safety
            if rec < 0.25: rec = 0.254
            rec = f"{rec:.2f}"
            
        print(f"{name:<20} | {load:<8.3f} | {w_min:<10.3f} | {rec}")
        
    # --- 3. CLEARANCE & CREEPAGE ---
    print(f"\n\n🛡️  PART 3: SAFETY SPACING RULES (IEC 60950 / IPC-2221)")
    print(f"   *Pollution Degree 2 (Standard Office/Home Environment)*")
    print("-" * 80)
    print(f"{'ZONE A':<15} {'ZONE B':<15} | {'CLEARANCE':<12} | {'CREEPAGE':<12} | {'RECOMMENDATION'}")
    print("-" * 80)
    
    rules = [
        ("AC Phase", "AC Neutral", RULES_CLEARANCE['AC_Mains_Func'], RULES_CREEPAGE['AC_Mains_Func'], "Keep 3.0mm Gap"),
        ("AC Mains", "DC Logic", RULES_CLEARANCE['AC_to_DC_Iso'], RULES_CREEPAGE['AC_to_DC_Iso'], "Isolation Slot if <5mm"),
        ("AC Relay Pin", "Faston Tab", "N/A", "N/A", "Polygon Pour (Connected)"),
        ("DC 5V", "DC GND", RULES_CLEARANCE['DC_Low_Voltage'], RULES_CREEPAGE['DC_Low_Voltage'], "0.25mm Min")
    ]
    
    for z1, z2, cl, cr, note in rules:
        cl_str = f"{cl} mm" if isinstance(cl, float) else cl
        cr_str = f"{cr} mm" if isinstance(cr, float) else cr
        print(f"{z1:<15} {z2:<15} | {cl_str:<12} | {cr_str:<12} | {note}")
        
    print("-" * 80)
    print("NOTE: 'Clearance' is air gap. 'Creepage' is surface distance along PCB.")
    print("      For AC 230V, try to maintain >3.0mm everywhere for robustness.")

if __name__ == "__main__":
    analyze_system('power_components.json')