# config.py


class Config:
    """
    CENTRAL CONFIGURATION & CONSTANTS
    ---------------------------------
    """

    # --- IPC-2221 STANDARDS (External Layers) ---
    IPC_K = 0.048
    IPC_B = 0.44
    IPC_C = 0.725
    IPC_TEMP_RISE_C = 10

    # 1oz Copper = approx 1.37 mils (35um) thickness
    IPC_THICKNESS_MILS_PER_OZ = 1.37

    # --- MANUFACTURING LIMITS (DfM) ---
    DFM_MIN_SIGNAL_WIDTH_MM = 0.25

    # --- ENGINEERING SAFETY FACTORS ---
    SAFETY_FACTOR_POWER_RAILS = 2.5

    # --- MECHANICAL ROBUSTNESS ---
    MIN_WIDTH_AC_MAINS_MM = 1.00
    MIN_WIDTH_POWER_RAIL_MM = 0.40

    # --- LOGIC THRESHOLDS ---
    THRESHOLD_POLYGON_AMPS = 15.0
    THRESHOLD_POWER_NET_AMPS = 0.1
    DEFAULT_SIGNAL_LOAD_AMPS = 0.05
