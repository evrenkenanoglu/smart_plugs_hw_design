# main.py
import json
import datetime
from Analyzer import PowerAnalyzer
from Reporter import MarkdownReporter

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def main():
    print("🚀 Starting PCB System Analysis...")

    # 1. Initialize
    raw_data = load_json("peak_data.json")
    psu_info = raw_data["power_supply"]
    project_name = raw_data["project_name"]

    # 2. Iterate through all boards
    for board in raw_data["boards"]:
        b_name = board["board_name"]
        print(f"   ... Analyzing: {b_name}")

        # Initialize Analysis for this specific board
        analyzer = PowerAnalyzer(board, psu_info)
        
        # Output filename: e.g., "Report_Power_Board.md"
        output_file = f"Report_{b_name}.md"
        reporter = MarkdownReporter("report_template.md", output_file)

        # Run Analysis
        dc_rows = analyzer.analyze_dc_loads()
        ac_watts, ac_amps = analyzer.get_ac_requirements()
        width_targets = analyzer.build_width_targets(ac_amps)

        # Format Tables
        ac_table_rows = reporter.generate_ac_table(
            width_targets, board.get("mains_voltage_ac_v", 0)
        )
        
        width_table_rows = reporter.generate_width_table(
            width_targets, analyzer, board["copper_weight_oz"]
        )

        # Compile Data
        report_content = {
            "project_name": f"{project_name} - {b_name}",
            "date": datetime.date.today(),
            "copper_oz": board["copper_weight_oz"],
            "ac_volts": board.get("mains_voltage_ac_v", "N/A"),
            "dc_volts": board["main_voltage_rail_dc_v"],
            "psu_name": psu_info["name"],
            "psu_limit": psu_info["max_output_current_ma"],
            "dc_load_rows": dc_rows.strip(),
            "total_peak": analyzer.total_dc_ma,
            "safety_margin": board["safety_margin_percent"],
            "design_load": analyzer.design_load_psu,
            "psu_status": analyzer.get_psu_status(),
            "ac_load_rows": ac_table_rows.strip() if ac_table_rows else "| N/A | N/A | N/A | N/A |",
            "trace_width_rows": width_table_rows.strip(),
        }

        reporter.write(report_content)
        print(f"   ✅ Generated {output_file}")

if __name__ == "__main__":
    main()