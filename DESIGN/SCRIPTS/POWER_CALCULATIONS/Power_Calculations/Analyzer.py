# analyzer.py
import math
from Config import Config
from Calculator import IPCCalculator

class PowerAnalyzer:
    def __init__(self, board_data, psu_data):
        self.b_data = board_data
        self.psu = psu_data

        # State variables
        self.total_dc_ma = 0
        self.rail_3v3_ma = 0
        self.relay_gnd_ma = 0
        self.design_load_psu = 0

    def analyze_dc_loads(self):
        dc_rows = ""
        for c in self.b_data["dc_components"]:
            tot = c["peak_current_ma"] * c["quantity"]
            volts = c.get("voltage_v", 5.0)

            self.total_dc_ma += tot

            # Track 3V3 loads specifically
            if volts < 4.5:
                self.rail_3v3_ma += tot

            if "Coil" in c["name"] or "Relay" in c["name"]:
                self.relay_gnd_ma += tot

            dc_rows += f"| {c['name']} | {volts}V | {c['quantity']} | {c['peak_current_ma']} | {tot:.1f} |\n"

        # Calculate Design Load with Margin
        self.design_load_psu = self.total_dc_ma * (1 + self.b_data["safety_margin_percent"] / 100)
        return dc_rows

    def get_psu_status(self):
        # Only check PSU limit on the main power board or aggregate (simplified here)
        limit = self.psu["max_output_current_ma"]
        return "✅ **PASS**" if self.design_load_psu <= limit else "❌ **FAIL**"

    def get_ac_requirements(self):
        # If board has no mains voltage (e.g. UI Board), return 0
        mains_v = self.b_data.get("mains_voltage_ac_v", 0)
        if mains_v <= 0:
            return 0.0, 0.0
            
        dc_watts = (self.design_load_psu / 1000.0) * self.b_data["main_voltage_rail_dc_v"]
        return IPCCalculator.calculate_ac_input(
            dc_watts, self.psu.get("efficiency", 0.7), mains_v
        )

    def build_width_targets(self, ac_amps):
        targets = []

        # 1. AC Lines (Only if they exist)
        if "ac_power_lines" in self.b_data:
            for line in self.b_data["ac_power_lines"]:
                targets.append((line["name"], line["max_current_a"]))

        # 2. Input Power Traces
        if self.b_data.get("mains_voltage_ac_v", 0) > 0:
            targets.append(("AC_MAINS_INPUT", ac_amps))
        
        # 3. DC Power Rails
        # Main Rail (Input to board)
        targets.append((f"DC_IN_{self.b_data['main_voltage_rail_dc_v']}V", self.design_load_psu / 1000.0))

        # 3V3 Rail (if it exists on this board)
        if self.rail_3v3_ma > 0:
             # If main rail is already 3.3V, we don't need a separate entry, but harmless to add
            targets.append(("DC_3V3_RAIL", self.rail_3v3_ma / 1000.0))

        if self.relay_gnd_ma > 0:
            targets.append(("DC_RELAY_GND", self.relay_gnd_ma / 1000.0))
            
        targets.append(("DC_SIGNAL", Config.DEFAULT_SIGNAL_LOAD_AMPS))

        return targets

    def get_trace_recommendation(self, name, load_amps, calculated_width_mm):
        # ... (Same logic as before, just kept concise for this snippet) ...
        if load_amps > Config.THRESHOLD_POLYGON_AMPS:
            return "**POLYGON POUR**"
        
        if "AC_" in name:
            rec = max(calculated_width_mm, Config.MIN_WIDTH_AC_MAINS_MM)
            return f"**{rec:.2f} mm** (Mech)"

        if load_amps > Config.THRESHOLD_POWER_NET_AMPS:
            target = calculated_width_mm * Config.SAFETY_FACTOR_POWER_RAILS
            rec = max(target, Config.MIN_WIDTH_POWER_RAIL_MM)
            rec = math.ceil(rec * 20) / 20.0
            return f"**{rec:.2f} mm** (SF={Config.SAFETY_FACTOR_POWER_RAILS})"

        return f"**{Config.DFM_MIN_SIGNAL_WIDTH_MM} mm**"