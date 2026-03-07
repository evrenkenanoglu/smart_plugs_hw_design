

Here is the "home recipe" to wind the exact **3.9mH, 20:1 ratio** transformer we calculated for your 10W TNY288PG design.

### 1. What You Need to Buy (Materials & Tools)
You can buy all of this on AliExpress, Amazon, or eBay for very cheap.
*   **The Core & Bobbin:** Search for **"EE16 Core and Bobbin PC40"**. (PC40 is the standard ferrite material). Buy the vertical bobbin with 8 or 10 pins.
*   **Primary Wire:** Enamelled copper magnet wire, **0.16mm diameter** (AWG 34).
*   **Secondary Wire (CRITICAL):** Do not use standard magnet wire for the 5V side. You must buy **Triple Insulated Wire (TIW)**, **0.5mm diameter** (AWG 24). This wire has three layers of plastic insulation and is legally required to guarantee you won't get electrocuted if the transformer gets hot.
*   **Transformer Tape:** Yellow Mylar/Polyester tape (often called Kapton tape), **8mm wide** (to fit exactly inside the EE16 bobbin).
*   **An LCR Meter:** A cheap digital LCR meter (like the common LC100-A or a multimeter that measures Inductance) is **mandatory**. You cannot build a flyback without measuring the inductance.

---

### 2. The Winding Recipe (Step-by-Step)
Because the **TNY288PG** is a smart IC, it powers itself directly from the high-voltage pin. This means we don't even need to wind an "Auxiliary" winding. We only need two coils!

**Step 1: The Primary Winding (High Voltage)**
1. Solder the 0.16mm wire to **Pin 1** of the bobbin.
2. Wind exactly **100 turns** tightly and neatly across the bobbin. It will take about 3 or 4 layers to fit 100 turns.
3. Solder the end of the wire to **Pin 3**. 
4. *Important:* Wrap **3 complete layers** of the yellow transformer tape tightly over this whole winding to seal it in. 

**Step 2: The Secondary Winding (5V Output)**
1. Take your 0.5mm Triple Insulated Wire (TIW) and solder it to **Pin 6** (on the opposite side of the bobbin).
2. Wind exactly **5 turns**. Space them out evenly across the yellow tape. 
3. Solder the end to **Pin 7**.
4. Wrap **3 complete layers** of yellow tape over the top to protect the wire.

---

### 3. The Secret Step: "Gapping" the Core
This is where most beginners fail. If you just put the two black ferrite core halves into the bobbin right now and measure the primary pins (1 and 3) with your LCR meter, it will probably measure something huge, like **12.0mH**. 

If you put a 12mH transformer into your circuit, the IC will explode because the magnetic core will "saturate." We need exactly **3.9mH**.

**How to get 3.9mH (The Air Gap):**
1. Take a small piece of your yellow tape (or standard printer paper) and put it on the center leg of one of the ferrite halves. 
2. Insert both ferrite halves into the bobbin so they meet in the middle, but the tape forces a tiny microscopic "air gap" between them.
3. Hook up your LCR meter to Pins 1 and 3. 
4. Squeeze the core halves tightly together with your fingers. 
5. Read the meter. 
    * If it says **5.0mH**, your gap is too small. Add another layer of tape/paper.
    * If it says **2.5mH**, your gap is too big. Use thinner tape.
6. Keep adjusting the thickness of the tape/paper in the center leg until your LCR meter reads exactly **3.9mH** (anything between 3.6mH and 4.2mH is perfectly fine).

### 4. Final Assembly
Once you have the exact paper/tape thickness to get ~3.9mH, wrap yellow tape entirely around the outside of the black ferrite core to hold the two halves tightly together so they don't rattle or buzz (flyback transformers will physically "sing" or buzz at high frequencies if the cores aren't taped tightly together).

### Summary of your custom transformer:
*   **Pin 1 to Pin 3:** 100 Turns (0.16mm wire) -> *Connects to 300V DC and TNY288PG Drain.*
*   **Pin 6 to Pin 7:** 5 Turns (0.5mm TIW) -> *Connects to your Schottky Diode and 5V Output.*
*   **Inductance (Pin 1 to 3):** 3.9mH (Set via paper air gap).

You can easily wind this while watching a TV show. Once you do it successfully, you will have unlocked a major "wizard-level" electronics skill, and you will never have to rely on confusing Chinese datasheets again!