# Safety Analysis: Smart Power Bar
    
## 1. Component Specifications
* **Transistor:** SS8050 (SOT-23)
* **Diode:** B5819W SL (Schottky)
* **Load:** 400.0mW Relay Coil [cite: 21]

## 2. Calculated Values
| Parameter | Value | Limit / Goal |
| :--- | :--- | :--- |
| **Relay Current (Ic)** | 80.0 mA | Max 1500.0 mA |
| **Voltage at Relay** | 4.75 V | Min 3.5 V  |
| **Transistor Heat (Pd)** | 20.0 mW | Max 300.0 mW |
| **Base Drive (Ib)** | 2.60 mA | ~2-5 mA recommended |

## 3. Safety Verdicts
* **Current Capacity:** ✅ SAFE
* **Thermal Management:** ✅ SAFE
* **Switching Reliability:** ✅ RELIABLE
* **Flyback Protection:** ✅ DIODE SUITABLE

> **Note:** The diode handles 80.0mA, which is only **8.0%** of its 1A rating.
