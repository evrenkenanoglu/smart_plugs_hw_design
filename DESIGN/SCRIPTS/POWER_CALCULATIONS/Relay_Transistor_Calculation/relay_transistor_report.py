def generate_safety_report():
    # --- VARIABLES (Adjust these as needed) ---
    project_name = "Smart Power Bar"
    transistor_model = "SS8050 (SOT-23)"
    
    # Supply and Logic
    v_supply = 5.0          # Volts
    v_logic = 3.3           # Volts (ESP32/MCP23017)
    
    # Relay Specs (HF105F-1/005D-1HST)
    relay_coil_watt = 0.9   # 900mW
    relay_min_pickup_v = 3.75 # 75% of 5V
    
    # Transistor Specs from Datasheet
    max_pd = 0.3            # 300mW Power Dissipation Limit
    max_ic = 1.5            # 1.5A Collector Current Limit
    vce_sat = 0.25          # Typical voltage drop at ~200mA
    vbe_sat = 0.7           # Base-Emitter voltage drop
    
    # Component Choices
    r_base = 1000           # 1k Ohm base resistor
    
    # --- CALCULATIONS ---
    # 1. Load Current
    i_load = relay_coil_watt / v_supply  # Amps
    
    # 2. Voltage delivered to Relay
    v_relay_actual = v_supply - vce_sat
    
    # 3. Power Dissipated by Transistor
    p_transistor = i_load * vce_sat
    
    # 4. Base Current provided by MCP23017
    i_base = (v_logic - vbe_sat) / r_base
    
    # --- SAFETY CHECKS ---
    is_current_safe = i_load < max_ic
    is_power_safe = p_transistor < max_pd
    is_switching_reliable = v_relay_actual > relay_min_pickup_v
    
    # --- GENERATE MARKDOWN ---
    md_content = f"""# Safety Analysis: {project_name}
    
## 1. Component Specifications
* **Transistor:** {transistor_model}
* **Load:** {relay_coil_watt*1000}mW Relay Coil

## 2. Calculated Values
| Parameter | Value | Limit / Goal |
| :--- | :--- | :--- |
| **Relay Current (Ic)** | {i_load*1000:.1f} mA | Max {max_ic*1000} mA |
| **Voltage at Relay** | {v_relay_actual:.2f} V | Min {relay_min_pickup_v} V |
| **Transistor Heat (Pd)** | {p_transistor*1000:.1f} mW | Max {max_pd*1000} mW |
| **Base Drive (Ib)** | {i_base*1000:.2f} mA | ~2-5 mA recommended |

## 3. Safety Verdicts
* **Current Capacity:** {"✅ SAFE" if is_current_safe else "❌ OVERLOAD"}
* **Thermal Management:** {"✅ SAFE" if is_power_safe else "❌ OVERHEATING"}
* **Switching Reliability:** {"✅ RELIABLE" if is_switching_reliable else "⚠️ UNRELIABLE"}

> **Note:** Actual Transistor Power is using only **{(p_transistor/max_pd)*100:.1f}%** of its rated capacity.
"""

    with open("safety_report.md", "w", encoding="utf-8") as f:
        f.write(md_content)
    
    print("Report generated: safety_report.md")

if __name__ == "__main__":
    generate_safety_report()