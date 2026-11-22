# reporter.py
import datetime
from Calculator import IPCCalculator


class MarkdownReporter:
    def __init__(self, template_path, output_path):
        self.template_path = template_path
        self.output_path = output_path

    def generate_ac_table(self, targets, sys_volts):
        rows = ""
        for name, amps in targets:
            if "AC_" in name:
                pwr_kw = (sys_volts * amps) / 1000.0
                rows += f"| {name} | {sys_volts}V | {amps:.3f} A | {pwr_kw:.3f} kW |\n"
        return rows

    def generate_width_table(self, targets, analyzer, copper_oz):
        rows = ""
        for name, amps in targets:
            phys_min = IPCCalculator.calculate_min_width_mm(amps, copper_oz)
            rec_str = analyzer.get_trace_recommendation(name, amps, phys_min)
            rows += f"| {name} | {amps:.3f} | {phys_min:.3f} mm | {rec_str} |\n"
        return rows

    def write(self, context):
        with open(self.template_path, "r", encoding="utf-8") as t:
            template = t.read()

        with open(self.output_path, "w", encoding="utf-8") as f:
            f.write(template.format(**context))
