import json

def generate_professional_report(data, filename="report.md"):
    with open(filename, 'w', encoding='utf-8') as f:
        f.write("# UI LED Calculation & BOM Report\n\n")
        f.write("| Component Name | Source | Target mA | Req. Ω | E24 Choice | Power (mW) |\n")
        f.write("| :--- | :--- | :--- | :--- | :--- | :--- |\n")
        
        for led in data['leds']:
            vs = led['source_voltage']
            vf_avg = (led['forward_voltage_min'] + led['forward_voltage_max']) / 2
            target_i_a = led['target_current_ma'] / 1000
            
            # Ohms Law: R = (Vs - Vf) / I
            res_val = (vs - vf_avg) / target_i_a
            suggested = find_nearest_e24(res_val)
            
            # Power: P = I^2 * R
            power_mw = (target_i_a**2 * suggested) * 1000
            
            f.write(f"| {led['name']} | {vs}V | {led['target_current_ma']} | {res_val:.1f}Ω | **{suggested}Ω** | {power_mw:.1f} |\n")

    print(f"✅ Report generated: {filename}")

def find_nearest_e24(value):
    e24 = [10, 11, 12, 13, 15, 16, 18, 20, 22, 24, 27, 30, 33, 36, 39, 43, 47, 51, 56, 62, 68, 75, 82, 91]
    scale = 1
    t = value
    while t >= 100: t /= 10; scale *= 10
    while t < 10: t *= 10; scale /= 10
    nearest = min(e24, key=lambda x: abs(x - t))
    return int(nearest * scale)

if __name__ == "__main__":
    with open('led_data.json', 'r') as f:
        config = json.load(f)
    generate_professional_report(config)