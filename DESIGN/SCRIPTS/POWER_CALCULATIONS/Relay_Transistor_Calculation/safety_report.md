# Safety Analysis: Smart Power Bar
    
## 1. Component Specifications
* **Transistor:** SS8050 (SOT-23)
* **Load:** 900.0mW Relay Coil

## 2. Calculated Values
| Parameter | Value | Limit / Goal |
| :--- | :--- | :--- |
| **Relay Current (Ic)** | 180.0 mA | Max 1500.0 mA |
| **Voltage at Relay** | 4.75 V | Min 3.75 V |
| **Transistor Heat (Pd)** | 45.0 mW | Max 300.0 mW |
| **Base Drive (Ib)** | 2.60 mA | ~2-5 mA recommended |

## 3. Safety Verdicts
* **Current Capacity:** ✅ SAFE
* **Thermal Management:** ✅ SAFE
* **Switching Reliability:** ✅ RELIABLE

> **Note:** Actual Transistor Power is using only **15.0%** of its rated capacity.
