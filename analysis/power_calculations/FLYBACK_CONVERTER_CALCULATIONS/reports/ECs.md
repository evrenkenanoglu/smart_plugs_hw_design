# Electronic Components 


To translate our mathematical model into a professional PCB design, we need to divide the flyback converter into functional blocks. For a 10W (5V, 2A) professional product, we prioritize **safety margins (derating)**, **low EMI**, and **reliability**.

Since the input is restricted to **220-250V AC** (European/UK/Asian high-line), we can save space and cost on the input bulk capacitor compared to a "Universal Input" (85-265V AC) design.

Here is the complete categorized Bill of Materials (BOM) with professional specifications and example part numbers.

---

### 1. Input Protection & EMI Filter
This section protects the circuit from surges and prevents high-frequency switching noise from entering the AC mains.

*   **F1 (Mains Fuse):** 
    *   **Spec:** 1A, 250VAC, Time-Lag (Slow-Blow). 
    *   *Why:* 10W output means very low continuous current, but the fuse must survive the initial inrush current.
*   **RV1 (Surge Protection MOV):** 
    *   **Spec:** 275VAC or 300VAC rated Varistor, 7mm or 10mm disc.
    *   *Example:* Bourns MOV-07D431K.
*   **RT1 (Inrush NTC Thermistor):** 
    *   **Spec:** 10 Ω, 1A. Limits the surge current when the user first plugs in the device to protect the bridge rectifier.
*   **CX1 (X-Capacitor):** 
    *   **Spec:** 100nF (0.1µF), 275VAC, **X2 Safety Class**. Placed across Line and Neutral.
*   **LF1 (Common Mode Choke):** 
    *   **Spec:** ~10mH to 20mH, 0.5A rated.
    *   *Why:* Crucial for passing CE/FCC EMI regulations.
*   **CY1 (Y-Capacitor):** 
    *   **Spec:** 1000pF (1nF) to 2200pF, 250VAC, **Y1 Safety Class**. 
    *   *Why:* Bridges Primary High-Voltage Ground to Secondary Low-Voltage Ground to provide a return path for high-frequency common-mode noise.

### 2. Primary Rectification & Bulk Storage
Converts the AC mains to the high-voltage DC bus calculated in our script (280V - 353V DC).

*   **BR1 (Bridge Rectifier):** 
    *   **Spec:** 800V or 1000V, 1A. 
    *   *Example:* MB10S (SMD, SOIC-4) or ABS10. (Do not use 400V; the AC peak is ~353V + surges).
*   **C1 (Bulk Input Capacitor):** 
    *   **Spec:** 10µF to 15µF, **400V DC**, Electrolytic, 105°C rated. 
    *   *Why:* Because your design is strictly 220-250VAC, you only need ~1µF per Watt. If this was a 100VAC input design, you would need a 22µF to 33µF cap.

### 3. Power Control & Switching
For a 10W professional adapter, using an **Integrated Offline Switcher** (Controller + High-Voltage MOSFET in one IC) is the absolute industry standard. It radically reduces PCB size and component count.

*   **U1 (Integrated Flyback Switcher):** 
    *   **Spec:** Built-in 65kHz oscillator and 725V rated MOSFET. 
    *   *Example:* **Power Integrations TNY285PG** (TinySwitch-4 series) or **STMicroelectronics VIPer26**.
    *   *Why:* Our script calculated a max MOSFET stress of ~496V. A 725V integrated IC gives a massive, highly reliable safety margin.

### 4. Primary Snubber Network (RCD Clamp)
When the MOSFET turns off, the leakage inductance of the transformer creates a high-voltage spike that can destroy the MOSFET. The RCD clamp absorbs this.

*   **D1 (Snubber Diode):** 
    *   **Spec:** 800V or 1000V, 1A, **Ultra-Fast Recovery (trr < 75ns)**. 
    *   *Example:* US1M or UF4007 (Do NOT use a standard 1N4007; it is too slow).
*   **C2 (Snubber Capacitor):** 
    *   **Spec:** 1000pF (1nF), 1000V (1kV), Ceramic. 
*   **R1 (Snubber Resistor):** 
    *   **Spec:** 100 kΩ to 150 kΩ, 0.5W or 1W (Through-hole or two 1206 SMD resistors in series for voltage clearance).

### 5. Custom Transformer (T1)
You will send these exact specs to a transformer manufacturer (like Wurth Elektronik, Coilcraft, or a custom winding house).

*   **Core Material:** PC40 (Standard Ferrite)
*   **Core Size:** EE16 (Perfect for 10W-15W)
*   **Primary Inductance (Lp):** 3.9 mH (±10%)
*   **Turns Ratio (Np:Ns):** 20:1
    *   *Winding Details:*
    *   **Primary (Np):** 100 Turns (AWG 34 / 0.16mm wire)
    *   **Secondary (Ns):** 5 Turns (Triple Insulated Wire, AWG 24 / 0.5mm, strictly required for safety isolation).
    *   **Auxiliary (Na):** 12 Turns (Creates ~12V to power the feedback circuitry/IC on the primary side).
*   **Isolation:** 3000V AC High-Pot test between Primary and Secondary.

### 6. Secondary Rectification & Filtering
Converts the high-frequency pulsed AC from the transformer into clean 5V DC.

*   **D2 (Output Rectifier):** 
    *   **Spec:** 40V or 45V, 3A to 5A, **Schottky Diode**. 
    *   *Example:* SS34 or SS54 (SMD, DO-214AB). 
    *   *Why:* Our script calculated a reverse voltage of ~23V. A 40V part gives a >70% safety margin. Schottky is required to minimize forward voltage drop ($V_f \approx 0.45V$), keeping efficiency high.
*   **C3, C4 (Output Capacitors):** 
    *   **Spec:** Two 470µF or 680µF, 10V, **Low ESR Electrolytic** capacitors in parallel.
    *   *Example:* Panasonic FM or Rubycon ZLH series. 
    *   *Why:* The script calculated 174µF minimum for capacitance, but in flybacks, **ESR (Equivalent Series Resistance) dictates the output ripple**. Using two larger low-ESR caps in parallel dramatically lowers ripple and handles the high RMS ripple current.
*   **L1 & C5 (Optional LC Post-Filter for ultra-clean 5V):** 
    *   **L1:** 2.2µH or 4.7µH, 3A rated SMD Inductor.
    *   **C5:** 100µF, 10V Ceramic (MLCC) or Solid Polymer capacitor. 

### 7. Feedback & Regulation Loop
Maintains exactly 5.0V under varying loads by passing an optically isolated signal back to the primary IC.

*   **U2 (Optocoupler):** 
    *   **Spec:** 5000Vrms isolation, CTR (Current Transfer Ratio) of 80% - 160% (Class A).
    *   *Example:* PC817A or LTV-817A.
*   **U3 (Error Amplifier / Voltage Reference):** 
    *   **Spec:** 2.5V precision programmable shunt regulator.
    *   *Example:* **TL431** (SMD SOT-23 package).
*   **R_Top & R_Bottom (Voltage Divider Resistors):** 
    *   **Spec:** 10 kΩ, **1% Tolerance**, 0603 or 0805 SMD. 
    *   *Why:* The TL431 regulates to 2.5V. Using a 10k/10k divider perfectly scales your 5.0V output down to the 2.5V reference.
*   **R_Bias (Optocoupler LED Resistor):**
    *   **Spec:** 330 Ω or 470 Ω, 5% SMD. Drops the voltage into the optocoupler's LED.
*   **C_Comp (Compensation Capacitor):** 
    *   **Spec:** 10nF to 100nF, 50V Ceramic. Placed between the REF and CATHODE pins of the TL431 to stabilize the control loop and prevent oscillation.

---

### Important PCB Layout Rules for these Components:
1. **Creepage and Clearance:** Maintain at least **6.0mm (preferably 8.0mm)** of physical distance on the PCB between all Primary side (High Voltage) components and Secondary side (5V) components to meet CE/UL safety requirements. Put an isolation slot (cutout) in the PCB under the Optocoupler (U2) and Transformer (T1).
2. **Current Loops:** The loop formed by **C1 $\rightarrow$ Primary Winding $\rightarrow$ U1 (IC) $\rightarrow$ Ground** must be as short and tight as physically possible to minimize EMI. 
3. **Secondary Loop:** The loop formed by **Transformer Secondary $\rightarrow$ D2 $\rightarrow$ C3/C4 $\rightarrow$ Ground** carries massive peak currents. Make these copper traces extremely wide and short.