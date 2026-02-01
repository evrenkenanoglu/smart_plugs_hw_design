# calculator.py
from Config import Config

class IPCCalculator:
    @staticmethod
    def calculate_min_width_mm(amps, copper_weight_oz):
        """
        Calculates theoretical minimum trace width based on Load and Copper Weight.
        Formula: Width[mils] = (Amps / (k * dT^b))^(1/c) / Thickness[mils]
        """
        if amps <= 0: return Config.DFM_MIN_SIGNAL_WIDTH_MM
        
        # Dynamic Thickness Calculation
        thickness_mils = copper_weight_oz * Config.IPC_THICKNESS_MILS_PER_OZ
        
        # Denominator: k * dT^b
        denom = Config.IPC_K * (Config.IPC_TEMP_RISE_C ** Config.IPC_B)
        
        # Calculate Area (mils^2) and Width (mils)
        area_mils2 = (amps / denom) ** (1 / Config.IPC_C)
        width_mils = area_mils2 / thickness_mils
        
        # Convert to mm
        return max(width_mils * 0.0254, Config.DFM_MIN_SIGNAL_WIDTH_MM)

    @staticmethod
    def calculate_ac_input(dc_power_watts, efficiency, mains_voltage):
        """Calculates AC Amps required to produce the DC Output."""
        ac_input_watts = dc_power_watts / efficiency
        ac_input_amps = ac_input_watts / mains_voltage
        return ac_input_watts, ac_input_amps