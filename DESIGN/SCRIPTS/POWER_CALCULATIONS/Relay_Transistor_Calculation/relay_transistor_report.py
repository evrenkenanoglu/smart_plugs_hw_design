def generate_safety_report():
    # --- VARIABLES ---
    project_name = "Smart Power Bar"
    transistor_model = "SS8050 (SOT-23)"
    diode_model = "B5819W SL (Schottky)"
    
    # Supply and Logic
    v_supply = 5.0          
    v_logic = 3.3           
    
    # Relay Specs (HF115F-I-005-1HS3A)
    relay_coil_watt = 0.4   # 400mW [cite: 21]
    relay_min_pickup_v = 3.5 # 3.5V 
    
    # Transistor Specs
    max_pd = 0.3            
    max_ic = 1.5            
    vce_sat = 0.25          
    vbe_sat = 0.7           
    
    # Diode Specs (B5819W)
    diode_max_i = 1.0       # 1A Continuous Forward Current
    diode_max_v = 40.0      # 40V Reverse Voltage
    
    # Component Choices
    r_base = 1000           
    
    # --- CALCULATIONS ---
    i_load = relay_coil_watt / v_supply  
    v_relay_actual = v_supply - vce_sat
    p_transistor = i_load * vce_sat
    i_base = (v_logic - vbe_sat) / r_base
    
    # --- SAFETY CHECKS ---
    is_current_safe = i_load < max_ic
    is_power_safe = p_transistor < max_pd
    is_switching_reliable = v_relay_actual > relay_min_pickup_v
    is_diode_safe = i_load < diode_max_i and v_supply < diode_max_v
    
    # --- GENERATE MARKDOWN ---
    md_content = f"""# Safety Analysis: {project_name}
    
## 1. Component Specifications
* **Transistor:** {transistor_model}
* **Diode:** {diode_model}
* **Load:** {relay_coil_watt*1000}mW Relay Coil [cite: 21]

## 2. Calculated Values
| Parameter | Value | Limit / Goal |
| :--- | :--- | :--- |
| **Relay Current (Ic)** | {i_load*1000:.1f} mA | Max {max_ic*1000} mA |
| **Voltage at Relay** | {v_relay_actual:.2f} V | Min {relay_min_pickup_v} V  |
| **Transistor Heat (Pd)** | {p_transistor*1000:.1f} mW | Max {max_pd*1000} mW |
| **Base Drive (Ib)** | {i_base*1000:.2f} mA | ~2-5 mA recommended |

## 3. Safety Verdicts
* **Current Capacity:** {"✅ SAFE" if is_current_safe else "❌ OVERLOAD"}
* **Thermal Management:** {"✅ SAFE" if is_power_safe else "❌ OVERHEATING"}
* **Switching Reliability:** {"✅ RELIABLE" if is_switching_reliable else "⚠️ UNRELIABLE"}
* **Flyback Protection:** {"✅ DIODE SUITABLE" if is_diode_safe else "❌ DIODE RISKY"}

> **Note:** The diode handles {i_load*1000:.1f}mA, which is only **{(i_load/diode_max_i)*100:.1f}%** of its 1A rating.
"""

    with open("safety_report.md", "w", encoding="utf-8") as f:
        f.write(md_content)
    
    print("Report generated: safety_report.md")

if __name__ == "__main__":
    generate_safety_report()