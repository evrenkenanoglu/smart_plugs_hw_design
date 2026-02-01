# analyzer.py
import math
from Config import Config
from Calculator import IPCCalculator


class PowerAnalyzer:
    def __init__(self, data):
        self.data = data
        self.sys = data["system_info"]
        self.psu = data["power_supply"]

        # State variables
        self.total_dc_ma = 0
        self.rail_3v3_ma = 0
        self.relay_gnd_ma = 0
        self.design_load_psu = 0

    def analyze_dc_loads(self):
        """Iterates components to sum loads."""
        dc_rows = ""
        for c in self.data["dc_components"]:
            tot = c["peak_current_ma"] * c["quantity"]
            volts = c.get("voltage_v", 5.0)

            self.total_dc_ma += tot

            if volts < 4.5:
                self.rail_3v3_ma += tot

            if "Coil" in c["name"] or "Relay" in c["name"]:
                self.relay_gnd_ma += tot

            dc_rows += f"| {c['name']} | {volts}V | {c['quantity']} | {c['peak_current_ma']} | {tot:.1f} |\n"

        # Calculate Design Load with Margin
        self.design_load_psu = self.total_dc_ma * (
            1 + self.sys["safety_margin_percent"] / 100
        )
        return dc_rows

    def get_psu_status(self):
        limit = self.psu["max_output_current_ma"]
        return "✅ **PASS**" if self.design_load_psu <= limit else "❌ **FAIL**"

    def get_ac_requirements(self):
        dc_watts = (self.design_load_psu / 1000.0) * self.sys["main_voltage_rail_dc_v"]
        return IPCCalculator.calculate_ac_input(
            dc_watts, self.psu.get("efficiency", 0.7), self.sys["mains_voltage_ac_v"]
        )

    def build_width_targets(self, ac_amps):
        """Creates the list of nets to analyze."""
        targets = []

        # AC Lines from JSON
        for line in self.data["ac_power_lines"]:
            targets.append((line["name"], line["max_current_a"]))

        targets.append(("AC_MAINS_INPUT", ac_amps))
        targets.append(("DC_MAIN_5V", self.design_load_psu / 1000.0))

        # 3V3 Rail calculation
        design_load_3v3 = self.rail_3v3_ma * (
            1 + self.sys["safety_margin_percent"] / 100
        )
        targets.append(("DC_3V3_RAIL", design_load_3v3 / 1000.0))

        targets.append(("DC_RELAY_GND", self.relay_gnd_ma / 1000.0))
        targets.append(("DC_SIGNAL", Config.DEFAULT_SIGNAL_LOAD_AMPS))

        return targets

    def get_trace_recommendation(self, name, load_amps, calculated_width_mm):
        """Applies Engineering Rules to the physics result."""

        # Rule 1: Polygon
        if load_amps > Config.THRESHOLD_POLYGON_AMPS:
            return "**POLYGON POUR**"

        # Rule 2: AC Mechanical Floor
        if "AC_" in name:
            rec = max(calculated_width_mm, Config.MIN_WIDTH_AC_MAINS_MM)
            return f"**{rec:.2f} mm** (Mech)"

        # Rule 3: DC Power Safety Factor
        if load_amps > Config.THRESHOLD_POWER_NET_AMPS:
            target = calculated_width_mm * Config.SAFETY_FACTOR_POWER_RAILS
            rec = max(target, Config.MIN_WIDTH_POWER_RAIL_MM)
            rec = math.ceil(rec * 20) / 20.0
            return f"**{rec:.2f} mm** (SF={Config.SAFETY_FACTOR_POWER_RAILS})"

        # Rule 4: Signals
        return f"**{Config.DFM_MIN_SIGNAL_WIDTH_MM} mm**"
