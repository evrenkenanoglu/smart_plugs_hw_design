# 📑 Technical Specification: 4-Channel 20A Smart Plug Controller
**Revision:** 1.0  
**Status:** Frozen / Ready for Manufacturing  
**Date:** February 7, 2026  

---

## 1. System Overview
This device is an industrial-grade, high-power switching unit capable of controlling four independent AC loads up to 20A each. It utilizes an ESP32 microcontroller for Wi-Fi/Bluetooth logic and dedicated hardware isolation for safety.

---

## 2. Electrical Specifications

### 2.1 Power Input
*   **Main Voltage:** 230V AC (50/60Hz).
*   **Logic Power Supply:** Isolated AC/DC Module (Hi-Link HLK-10M05).
    *   **Power Rating:** 10 Watts.
    *   **Output:** 5V DC / 2.0A.
*   **Protection:**
    *   **Fuse (F1):** 10A Cartridge (Protects PCB logic trace only).
    *   **Surge:** MOV (Varistor) 470V across AC Input.

### 2.2 Output Capabilities
*   **Channels:** 4 Independent Channels.
*   **Switching Method:** Electromechanical Relay (Hongfa HF105F-1/005D-1HST).
*   **Max Current Per Channel:**
    *   *Relay Rating:* 30A / 240VAC.
    *   **System Rated Load:** **20A Continuous** (Limited by thermal dissipation and connector specs).
*   **Connection Type:** 6.35mm Vertical Faston Tabs (Spade Terminals).

### 2.3 Logic & Control
*   **Controller:** ESP32-DevKitC V4 (Socketed via 2x 1x19 Pin Headers).
*   **Logic Voltage:** 3.3V (via AMS1117-3.3 LDO).
*   **I/O Expansion:** MCP23017 (I2C) handling Relay Drivers and Button Inputs.
*   **Relay Drivers:** Discrete NPN (SS8050 SOT-23) with Flyback Diodes (1N4148W).
*   **Interrupts:** Wired-OR configuration (INTA + INTB) $\rightarrow$ ESP32 GPIO.

---

## 3. PCB Manufacturing Specifications (Gerber Settings)
*These settings are critical for the 20A current handling capacity.*

| Parameter          | Specification                 | Notes                            |
| :----------------- | :---------------------------- | :------------------------------- |
| **Dimensions**     | 228mm x 80mm (Approx)         | See Mechanical Layer             |
| **Material**       | FR-4 Standard TG              |                                  |
| **Layers**         | 2 Layers                      | Top / Bottom                     |
| **Thickness**      | **1.6 mm**                    | Required for mechanical strength |
| **Copper Weight**  | **2 oz (70µm)**               | **CRITICAL for 20A Loads**       |
| **Solder Mask**    | Blue                          |                                  |
| **Silkscreen**     | White                         |                                  |
| **Surface Finish** | HASL (with Lead) or Lead-Free | ENIG optional                    |

---

## 4. PCB Design Rules & Layout Strategy

### 4.1 Trace Widths (Calculated for 2oz Copper)
| Function           | Net Name   | Width Rule       | Rationale                                                 |
| :----------------- | :--------- | :--------------- | :-------------------------------------------------------- |
| **AC Load (20A)**  | `AC_LOAD`  | **Polygon Pour** | ~14mm solid pour. **Direct Connect** (No thermal spokes). |
| **AC Mains Logic** | `AC_L/N`   | **1.00 mm**      | Mechanical robustness.                                    |
| **DC Main 5V**     | `+5V`      | **0.80 mm**      | Voltage stability for Relays + ESP32.                     |
| **DC Relay GND**   | `GND`      | **0.60 mm**      | Common return path for 4 relay coils.                     |
| **DC 3.3V**        | `+3V3`     | **0.40 mm**      | Power for ESP32/Logic.                                    |
| **Signals**        | `I2C/GPIO` | **0.25 mm**      | Standard DfM limit.                                       |

### 4.2 Safety & Isolation
*   **HV/LV Clearance:** Minimum **3.0 mm** air gap between any High Voltage (AC) track and Low Voltage (DC) track.
*   **Earth Guard Ring:** A 3.0mm wide chassis ground ring runs along the PCB edge (Bottom Layer), connected to mounting holes `J3`, `J4`, `J5`.
    *   *Purpose:* EMI Shielding and ESD discharge only.

---

## 5. Assembly & Wiring Guidelines

### 5.1 Component Assembly Notes
1.  **J2 (ESP32):** **DO NOT SOLDER** the ESP32 module directly.
    *   *Action:* Solder 2x **1x19 Pin Female Headers (2.54mm)**. Plug the ESP32 into the headers.
2.  **Faston Tabs:** Requires High-Power Soldering Iron (60W+). The "Direct Connect" polygon will absorb heat rapidly.
3.  **Relays:** Ensure flush seating against the PCB before soldering.

### 5.2 External Wiring Logic (Star Configuration)
*To ensure safety, high fault currents must NOT flow through the PCB Earth tracks.*

*   **AC Live (L):** Wall $\rightarrow$ Wago Connector $\rightarrow$ **PCB Faston IN** $\rightarrow$ Relay $\rightarrow$ **PCB Faston OUT** $\rightarrow$ Socket.
*   **AC Neutral (N):** Wall $\rightarrow$ Wago Connector $\rightarrow$ Socket.
    *   *Branch:* Thin wire from Wago $\rightarrow$ PCB `J1` (Powering the HLK-10M05).
*   **Earth (PE):** Wall $\rightarrow$ Wago Connector $\rightarrow$ Socket.
    *   *Branch:* Thin wire from Wago $\rightarrow$ PCB `J1` (Grounding the Shield Ring).

---

## 6. Bill of Materials (Key Components)

| Designator  | Component     | Value/Part #           | Package | Qty  |
| :---------- | :------------ | :--------------------- | :------ | :--- |
| **PS1**     | AC/DC Module  | **HLK-10M05**          | Module  | 1    |
| **K11-K14** | Relay         | **HF105F-1/005D-1HST** | THT     | 4    |
| **J2**      | Socket        | **Female Header 1x19** | 2.54mm  | 2    |
| **FT_xx**   | Faston Tab    | **726386-2 (6.35mm)**  | THT     | 8    |
| **Q11-Q14** | Transistor    | **SS8050**             | SOT-23  | 4    |
| **U1**      | LDO Regulator | **AMS1117-3.3**        | SOT-223 | 1    |
| **U2**      | I/O Expander  | **MCP23017-E/SS**      | SSOP-28 | 1    |

---

## 7. Known Constraints
1.  **Relay Logic:** Relays are "Active High" (Base of SS8050).
2.  **I/O Mirroring:** `INTA` and `INTB` on MCP23017 are physically shorted on the PCB. Firmware must configure `IOCON.MIRROR = 1`.
3.  **Mechanical Clearance:** Ensure the plastic enclosure allows for the height of the ESP32 mounted on headers (~20mm total height).

---
*End of Specification.*