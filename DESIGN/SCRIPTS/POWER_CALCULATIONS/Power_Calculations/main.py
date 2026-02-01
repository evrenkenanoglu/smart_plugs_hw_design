# main.py
import json
import datetime
from Analyzer import PowerAnalyzer
from Reporter import MarkdownReporter


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    print("🚀 Starting PCB Power Analysis...")

    # 1. Initialize
    raw_data = load_json("peak_data.json")
    analyzer = PowerAnalyzer(raw_data)
    reporter = MarkdownReporter("report_template.md", "PCB_Engineering_Report.md")

    # 2. Run Analysis
    dc_rows = analyzer.analyze_dc_loads()
    ac_watts, ac_amps = analyzer.get_ac_requirements()

    # 3. Build Targets for Trace Calculation
    width_targets = analyzer.build_width_targets(ac_amps)

    # 4. Format Tables
    ac_table_rows = reporter.generate_ac_table(
        width_targets, raw_data["system_info"]["mains_voltage_ac_v"]
    )

    width_table_rows = reporter.generate_width_table(
        width_targets, analyzer, raw_data["system_info"]["copper_weight_oz"]
    )

    # 5. Compile Data for Template
    sys_info = raw_data["system_info"]
    report_content = {
        "project_name": sys_info["project_name"],
        "date": datetime.date.today(),
        "copper_oz": sys_info["copper_weight_oz"],
        "ac_volts": sys_info["mains_voltage_ac_v"],
        "dc_volts": sys_info["main_voltage_rail_dc_v"],
        "psu_name": raw_data["power_supply"]["name"],
        "psu_limit": raw_data["power_supply"]["max_output_current_ma"],
        "dc_load_rows": dc_rows.strip(),
        "total_peak": analyzer.total_dc_ma,
        "safety_margin": sys_info["safety_margin_percent"],
        "design_load": analyzer.design_load_psu,
        "psu_status": analyzer.get_psu_status(),
        "ac_load_rows": ac_table_rows.strip(),
        "trace_width_rows": width_table_rows.strip(),
    }

    # 6. Write File
    reporter.write(report_content)
    print("✅ PCB_Engineering_Report.md generated successfully.")


if __name__ == "__main__":
    main()
