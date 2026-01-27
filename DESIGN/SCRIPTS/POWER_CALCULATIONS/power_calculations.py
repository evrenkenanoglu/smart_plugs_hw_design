import json

def calculate_power(json_file):
    with open(json_file, 'r') as f:
        data = json.load(f)
    
    total_current_ma = 0
    total_power_w = 0
    
    print(f"--- Power Calculation for {data['system_info']['project_name']} ---")
    
    for comp in data['components']:
        # Calculate current for this component type
        qty = comp['quantity']
        if 'nominal_current_ma' in comp:
            comp_current = comp['nominal_current_ma'] * qty
        elif 'peak_current_ma' in comp:
            comp_current = comp['peak_current_ma'] * qty
        else:
            comp_current = comp['quiescent_current_ma'] * qty
            
        total_current_ma += comp_current
        
        # Calculate power (P = V * I)
        voltage = comp.get('operating_voltage_v') or comp.get('coil_voltage_v')
        if voltage:
            comp_power = (voltage * comp_current) / 1000
            total_power_w += comp_power
        else:
            comp_power = 0
        
        print(f"{comp['name']} ({qty}x): {comp_current:.2f}mA | {comp_power:.2f}W")

    # Safety Margin (20%)
    required_current = total_current_ma * 1.2
    required_power = total_power_w * 1.2
    
    psu = data['power_supply']
    status = "OK" if required_current <= psu['max_output_current_ma'] else "OVERLOADED"

    print("-" * 40)
    print(f"Total Peak Current: {total_current_ma:.2f} mA")
    print(f"Total Power: {total_power_w:.2f} W")
    print(f"Required Current with 20% Margin: {required_current:.2f} mA")
    print(f"Required Power with 20% Margin: {required_power:.2f} W")
    print(f"PSU Capacity ({psu['name']}): {psu['max_output_current_ma']} mA | {psu['max_output_power_w']} W")
    print(f"System Status: {status}")

if __name__ == "__main__":
    calculate_power('power_components.json')
