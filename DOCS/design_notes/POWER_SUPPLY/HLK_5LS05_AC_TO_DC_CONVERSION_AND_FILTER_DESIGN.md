## 2. Core Conversion & High Voltage DC
*The main switching module and its required external high-voltage storage.*

| Component        | Designator | Value / Part  | Function                                                                                    |
| :--------------- | :--------- | :------------ | :------------------------------------------------------------------------------------------ |
| **Power Module** | `U1`       | **HLK-5LS05** | **5W / 5V SIP Module.** Converts 230V AC to 5V DC.                                          |
| **HV Capacitor** | `C1`       | **10uF 450V** | **Primary Bulk Storage.** Connects to HLK Pins 3 & 4 to stabilize the internal 325V DC bus. |
| **Y-Capacitor**  | `CY1`      | **2.2nF Y1**  | **Isolation Bridge.** Connects AC Neutral to DC Ground to suppress EMI radiation.           |

**🔗 Wiring Topology:**
*   **HLK Pins 1 & 2:** Connect to Output of Input EMI Block.
*   **HLK Pins 3 & 4:** Connect directly to `C1` (10uF 450V). **Critical High Voltage Loop.**
*   **HLK Pin 4 (-HV):** Connects to `CY1`, which goes to DC Ground (Pin 5).

---

## 3. DC Output Pi-Filter Block
*Cleans the 5V output to ensure zero ripple for the ESP32.*

| Component | Designator | Value / Part | Function |
| :--- | :--- | :--- | :--- |
| **Bulk Cap 1** | `C_BULK1` | **220uF 25V** | **Primary Reservoir.** Handles the immediate energy demand. |
| **Inductor** | `L1` (Output) | **10uH SMD** | **Filter Choke.** Blocks high-frequency switching noise from the HLK. (TDK Shielded). |
| **Bulk Cap 2** | `C_BULK2` | **220uF 25V** | **Secondary Reservoir.** Provides ultra-clean power after the inductor. |
| **Ceramic Cap** | `C2` | **10uF 0603** | **HF Decoupling.** Filters very fast noise spikes. |
| **TVS Diode** | `D1` | **SMBJ5.0A** | **Over-Voltage Protection.** Clamps the rail if the PSU fails, saving the ESP32. |

**🔗 Wiring Topology:**
`HLK (+5V Out)` $\rightarrow$ `C_BULK1` $\rightarrow$ `L1 (Inductor)` $\rightarrow$ `C_BULK2` $\rightarrow$ `C2` $\rightarrow$ `D1` $\rightarrow$ **To System +5V**.

---

## 📝 Important Notes for Assembly
1.  **Duplicate Designator L1:** You have two components named `L1` in your list (The Input Choke `UU9.8` and the Output Inductor `SLF7055`). Ensure they are renamed (e.g., `L_EMI` and `L_DC`) in the PCB software to avoid placement errors.
2.  **RV1 Description:** The text description in your list says "440pF" (which is the parasitic capacitance), but the part number `14D431K` is a **Varistor**. This is correct for the design.
3.  **C2 Footprint:** This is an **0603 SMD** part. Ensure it is placed close to the output connector/ESP32.