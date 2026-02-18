# ⚡ Power Supply Design Rationale: AC-DC Logic Section
**Project:** 4-Channel 20A Smart Plug  
**Module:** Hi-Link HLK-10M05 (10W)  
**Input:** 230V AC | **Output:** 5V DC  

This section details the selection of components for the "Logic Power" path. These components do **not** power the external loads (Heaters/Motors); they strictly power the ESP32, Relays, and Sensors.

---

## 1. The Core Power Module
| Component | Part Number | Specs | Selection Reason |
| :--- | :--- | :--- | :--- |
| **AC/DC Module** | **HLK-10M05** | 10W / 5V / 2A | **Capacity:** The total calculated peak current of the system (4 Relays + ESP32 Wi-Fi Bursts) is **~1.41A**. <br>**Headroom:** The 5W (1A) module would overheat. The 10W (2A) module runs at ~70% load, ensuring longevity and thermal stability. |

---

## 2. Input Protection (Safety & Surge)
*Located immediately after the AC Logic Input Terminals.*

| Component | Designator | Part / Value | Selection Reason |
| :--- | :--- | :--- | :--- |
| **Fuse** | `F1` | **1A Slow Blow** | **Short Circuit Protection:** Protects the PCB traces if the Power Module fails catastrophically. <br>**Type:** "Slow Blow" (Time-Lag) is required to prevent "nuisance tripping" caused by the initial capacitor charging current. |
| **NTC Thermistor** | `NTC1` | **10D-7** (10Ω) | **Inrush Limiting:** When plugged in, empty capacitors look like short circuits. This resistor limits the initial "spark" current to safe levels (~23A max), protecting the Fuse and Bridge Rectifier from stress damage. |
| **Varistor (MOV)** | `RV1` | **14D471K** | **Surge Protection:** If a lightning strike or grid spike occurs (>470V), this component clamps the voltage by shorting the excess energy, sacrificing itself to save the Power Module. |

---

## 3. EMI / EMC Filtering (Compliance)
*Prevents the device from injecting noise back into the home electrical grid (Required for FCC/CE).*

| Component | Designator | Part / Value | Selection Reason |
| :--- | :--- | :--- | :--- |
| **Safety Capacitor** | `CX1` | **0.1µF (100nF) X2** | **Differential Mode Filtering:** Filters noise between Live and Neutral. <br>**Rating:** "X2" Class is mandatory here because if it fails, it fails "Open" (Safe) rather than shorting out (Fire). |
| **Common Mode Choke** | `L1` | **UU9.8 10mH** | **Common Mode Filtering:** Blocks high-frequency noise trying to escape on *both* lines simultaneously. <br>**Inductance:** 10mH is optimized for the ~60-100kHz switching frequency of the HLK module. |

---

## 4. Isolation & Noise Return
*The critical link between High Voltage and Low Voltage.*

| Component | Designator | Part / Value | Selection Reason |
| :--- | :--- | :--- | :--- |
| **Y-Capacitor** | `CY1` | **2.2nF 400V Y1** | **The "EMI Loop":** Bridges AC Neutral to DC Ground. <br>**Why:** It provides a return path for internal switching noise so it doesn't radiate out the DC wires (Antenna effect). <br>**Safety:** "Y1" Class is mandatory for Reinforced Insulation (Industrial standard). It is designed never to short-circuit, keeping the user safe from electrocution. |

---

## 5. DC Output Stabilization
*Conditioning the 5V rail for the digital logic.*

| Component | Designator | Part / Value | Selection Reason |
| :--- | :--- | :--- | :--- |
| **Bulk Capacitor** | `C1` | **220µF 16V Elec.** | **Energy Reservoir:** The HLK module cannot react instantly to the ESP32's massive Wi-Fi current spikes. This capacitor stores energy to fill those gaps, preventing the MCU from resetting (Brownout). |
| **Noise Capacitor** | `C3` | **100nF Ceramic** | **High-Freq Filtering:** Electrolytic caps are too slow to filter sharp switching noise. This small ceramic capacitor cleans up the high-frequency ripple on the 5V line. |

---

## 🔌 The Signal Path Logic
The components are arranged in this specific order to maximize protection and minimize noise:

`Input (J1)` $\rightarrow$ `Fuse` $\rightarrow$ `NTC` $\rightarrow$ `MOV` $\rightarrow$ `X2 Cap` $\rightarrow$ `Choke` $\rightarrow$ `[Y-CAP BRIDGE]` $\rightarrow$ `HLK Module` $\rightarrow$ `DC Caps` $\rightarrow$ `System`