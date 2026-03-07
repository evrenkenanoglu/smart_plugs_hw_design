import json
import math


class FlybackDesigner:
    def __init__(self, config_file):
        with open(config_file, "r") as f:
            self.params = json.load(f)

        # Extract parameters
        self.Vac_min = self.params["vac_min"]
        self.Vac_max = self.params["vac_max"]
        self.V_out = self.params["v_out"]
        self.I_out = self.params["i_out"]
        self.eff = self.params["efficiency"]
        self.f_sw = self.params["f_sw"]
        self.V_ro = self.params["v_ro"]
        self.K_rf = self.params["k_rf"]
        self.V_f = self.params["v_f_diode"]
        self.V_ripple = self.params["v_ripple_out"]

    def calculate(self):
        results = {}

        # 1. Power and DC Link Voltage Calculations
        P_out = self.V_out * self.I_out
        P_in = P_out / self.eff

        # Approximate DC bus voltage (factor of 0.9 accounts for input capacitor ripple)
        V_dc_min = self.Vac_min * math.sqrt(2) * 0.9
        V_dc_max = self.Vac_max * math.sqrt(2)

        # 2. Duty Cycle Calculation (at minimum input voltage)
        D_max = self.V_ro / (self.V_ro + V_dc_min)

        # 3. Transformer Turns Ratio (Primary to Secondary)
        N_ps = self.V_ro / (self.V_out + self.V_f)

        # 4. Primary Current Calculations
        # I_edc is the average current during the MOSFET ON time
        I_edc = P_in / (V_dc_min * D_max)

        # Peak primary current
        I_pk = P_in / (V_dc_min * D_max * (1 - self.K_rf / 2))

        # RMS primary current (Trapezoidal/Triangular waveform)
        I_rms_pri = I_pk * math.sqrt(
            D_max * (1 / 3 - self.K_rf / 2 + (self.K_rf**2) / 3)
        )

        # 5. Primary Inductance Calculation
        # L = V * dt / dI
        L_p = (V_dc_min * D_max) / (I_pk * self.K_rf * self.f_sw)

        # 6. Component Voltage Stresses
        # MOSFET Stress = Max DC + Reflected Voltage + Leakage Inductance Spike (Assumed 30% of V_ro)
        V_spike = self.V_ro * 0.3
        V_ds_max = V_dc_max + self.V_ro + V_spike

        # Diode Peak Inverse Voltage (PIV)
        V_piv_diode = self.V_out + self.V_f + (V_dc_max / N_ps)

        # 7. Output Capacitor Calculation (Simplified for ESR dominating ripple)
        # C_out = (I_out * D_max) / (f_sw * V_ripple)
        C_out = (self.I_out * D_max) / (self.f_sw * self.V_ripple)

        # Compile Results
        results = {
            "Power Parameters": {
                "Input Power (W)": round(P_in, 2),
                "Output Power (W)": round(P_out, 2),
                "Min DC Bus Voltage (V)": round(V_dc_min, 1),
                "Max DC Bus Voltage (V)": round(V_dc_max, 1),
            },
            "Transformer Parameters": {
                "Max Duty Cycle (D_max)": round(D_max, 3),
                "Turns Ratio (Np/Ns)": round(N_ps, 2),
                "Primary Inductance (Lp) (uH)": round(L_p * 1e6, 1),
                "Primary Peak Current (A)": round(I_pk, 3),
                "Primary RMS Current (A)": round(I_rms_pri, 3),
            },
            "Component Selection": {
                "MOSFET Min Vds Rating (V)": round(V_ds_max, 1),
                "Diode Min Reverse Voltage (V)": round(V_piv_diode, 1),
                "Min Output Capacitance (uF)": round(C_out * 1e6, 1),
            },
        }

        return results

    def print_report(self, results):
        print("=" * 50)
        print("   FLYBACK CONVERTER DESIGN CALCULATION REPORT")
        print("=" * 50)
        for category, metrics in results.items():
            print(f"\n[{category}]")
            for key, value in metrics.items():
                print(f"  {key:<30}: {value}")
        print("\n" + "=" * 50)


if __name__ == "__main__":
    designer = FlybackDesigner("specs.json")
    design_results = designer.calculate()
    designer.print_report(design_results)
