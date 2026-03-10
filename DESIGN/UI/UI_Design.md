This makes the mechanical design much simpler and more robust because the front panel doesn't need to flex. You are separating the **Visual System** (LEDs) from the **Mechanical System** (Buttons).

Here is the Mechanical Stack-Up for the **LED Dead-Front Display Only**.

### 🏗️ Mechanical Stack-Up Diagram (LED Section)

```text
      ( User Viewing Direction )
                  ⬇
+---------------------------------------+  <-- LAYER 1: The "Smoked" Panel
| ///// (Tinted Rigid Acrylic)    ///// |      (3mm Thick, Glossy)
+---------------------------------------+      *Looks solid black when OFF*
      +---------------------------+        <-- LAYER 2: The Mask (Sticker/Ink)
      | [Black]   (Icon)  [Black] |            (Applied to back of Layer 1)
      +-----------+---+-----------+            *Defines the shape*
                  | |                      <-- LAYER 3: Diffuser
                  | |                          (White Film/Paper)
+-----------------+---+-----------------+  <-- LAYER 4: Light Isolation Grid
|  |              | |                |  |      (Black Foam or 3D Print)
|  |        (Light Chamber)          |  |      *Prevents light bleeding*
|  |              | |                |  |
+--+--------------+-+----------------+--+
+---------------------------------------+  <-- LAYER 5: The PCB
|               (SMD LED)               |
+---------------------------------------+

        [ Physical Button ]                <-- Sits completely separate,
        [   passes through  ]                  poking through a hole in
        [   Layer 1 or Case ]                  Layer 1 or the casing.
```

---

### 🛠️ Material Specifications (One by One)

#### 1. Layer 1: The Tinted Window ("Smoked Acrylic")
This is the magic material that creates the De'Longhi look.
*   **Material:** **Cast Acrylic (Plexiglass)** or **Polycarbonate**.
*   **Color:** **Smoked Grey** (also called "Transparent Grey" or "Solar Tint").
*   **Transmission:** **20% to 30%**.
    *   *Why:* It is dark enough to hide the PCB internals and the white diffuser when the LED is off (looking black), but allows the LED to shine through clearly when on.
*   **Thickness:** **2.0mm to 3.0mm** (Rigid).

#### 2. Layer 2: The Graphic Mask
This blocks the light everywhere *except* the shape of your icon (Coffee cup, Steam, etc.).
*   **Method A (Professional):** Screen Printed Black Ink directly on the back of Layer 1.
*   **Method B (DIY/Prototyping):** **Black Vinyl Sticker**.
    *   Cut the vinyl using a plotter (Cricut/Silhouette).
    *   Stick it to the **back** of the Acrylic.
    *   The "Icon" is a hole in the vinyl.

#### 3. Layer 3: The Diffuser
Without this, you will see a blinding bright dot (the LED chip) instead of a glowing icon.
*   **Material:** **Vellum Paper**, **Tracing Paper**, or **White Electrical Tape**.
*   **Placement:** Stick this directly over the Icon hole in Layer 2.
*   **Function:** It spreads the light out so the whole icon glows evenly.

#### 4. Layer 4: The Light Isolation Grid (Baffle)
You have 4 LEDs close together. Without this, turning on LED 1 will make LED 2 glow faintly (Light Bleed).
*   **Material:** **Black 3D Printed PLA** or **High-Density Black Foam (Poron)**.
*   **Thickness:** Matches the distance between your PCB and the Acrylic Panel (e.g., 5mm).
*   **Shape:** A honeycomb or box grid. Each LED gets its own "room."
*   **Adhesive:** Double-sided tape to stick it to the PCB.

#### 5. Layer 5: The PCB & LED
*   **LED Type:** **SMD 0805 or 1206**.
*   **Color:** White or Amber (matches the coffee machine look).
*   **Brightness:** High brightness is needed to punch through the diffuser and the smoked acrylic.

### 📝 Assembly Steps
1.  **PCB:** Solder your SMD LEDs to the board.
2.  **Grid:** Stick the Black Grid (Layer 4) onto the PCB, surrounding the LEDs.
3.  **Panel Prep:** Take your Smoked Acrylic (Layer 1). Apply the Black Mask (Layer 2) to the back. Apply the Diffuser (Layer 3) over the icons.
4.  **Combine:** Place the Panel on top of the Grid.
5.  **Buttons:** Drill holes in the Panel (or the casing frame) for your physical buttons to poke through separately.

This stack-up guarantees that **"Invisible until Lit"** high-end aesthetic.


### FINAL NOTES
- Semi-transparent Grey/Smoke Acrylic (3mm) or Polycarbonate Sheet (0.5mm - 1mm).