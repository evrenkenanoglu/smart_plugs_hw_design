# Power calculation reconciliation review

**Status:** Review performed; current-design reconciliation is blocked. No
calculation input or report was changed. This review is design assistance, not
proof of electrical safety, compliance, or certification.

## Current-design evidence

The project README identifies **HLK-5LS05** and **ESP32-C6** as the current
decisions. The inspected `EMC/smart_power_strip/inputs/locked_rev/MAIN_OMRON/BOM.csv`
lists HLK-5LS05 (C48935101), and
`EMC/smart_power_strip/inputs/locked_rev/UI/BOM.csv` lists
ESP32-C6-WROOM-1-N8 (C5366877). These BOM entries establish component
identities only; they do not establish approved circuit configuration, peak
load assumptions, or allowable operating conditions.

## Legacy inputs and formula concerns

`ANALYSIS/power_calculations/POWER_CALCULATIONS/data/peak_data.json` still
names HLK-10M05, assumes a 2000 mA supply limit and 70% efficiency (lines 3-6),
and includes ESP32-WROOM-32UE at 700 mA / 3.3 V (lines 14-29). Other relay,
UI, and rail assumptions also remain in that file (including lines 49-64).
It was preserved unchanged.

`ANALYSIS/power_calculations/POWER_CALCULATIONS/scripts/Analyzer.py` (lines
20, 35, 40-51) totals component currents across the modeled loads and compares
that sum to the PSU current limit. The input data includes loads at different
rail voltages, so that comparison needs engineering review; current cannot be
combined across rails without a justified conversion or power-based method.
The calculation also applies a configured margin.
`ANALYSIS/power_calculations/POWER_CALCULATIONS/scripts/Calculator.py` (lines
29-33) derives AC input current from DC power and efficiency, while
`ANALYSIS/power_calculations/POWER_CALCULATIONS/scripts/Reporter.py` (lines
7-18) derives power and trace-width outputs from the configured targets. These
formulas do not establish that the legacy inputs describe the current circuit.

The checked-in
`ANALYSIS/power_calculations/POWER_CALCULATIONS/reports/Report_Main_Power_Board.md`
and its generated counterpart name HLK-10M05 and ESP32-WROOM-32UE; the UI
report names HLK-10M05. The main report's PASS is only a result for those
inputs. Do not treat it as a pass for the HLK-5LS05 / ESP32-C6 design.

## Evidence needed before reconciliation

- The approved schematic/circuit revision and matching main/UI BOMs.
- Engineering-reviewed maximum and transient loads for every rail, including
  ESP32-C6 operating modes, relay coils, UI loads, and any conversion losses.
- Supply output-current/derating conditions and efficiency values applicable
  to the approved circuit.
- Engineering review of the calculation's rail aggregation and margin method.

Until that evidence is available, keep `peak_data.json` and the numerical
reports unchanged; do not generate replacement values from catalog listings
or component-name substitutions alone.
