Based on the datasheet, here's a full breakdown:

---

## Strapping Pins

| Pin | Module Pin # | Purpose | Default | Recommendation for Smart Plug |
|---|---|---|---|---|
| **MTMS** (IO4) | 4 | SDIO clock edge | Floating | Leave floating (not using SDIO) |
| **MTDI** (IO5) | 5 | SDIO clock edge | Floating | Leave floating |
| **GPIO8** | 10 | Boot mode + ROM print | Floating | Leave floating (SPI boot) |
| **GPIO9** | 15 | Boot mode | Pull-up (internal) | Keep HIGH for SPI boot — don't pull low |
| **GPIO15** | 23 | JTAG source | Floating | Must **not** float — tie to GND or 3V3 |

**Critical rules:**
- GPIO9 HIGH = normal SPI boot ✅
- GPIO9 LOW + GPIO8 HIGH = download/flash mode
- GPIO8=0, GPIO9=0 = **invalid, avoid**
- GPIO15 has **no internal pull resistor** — must be driven externally

---

## Pins Already at 3.3V by Design

From the datasheet, these are directly connected to your 3V3 rail:

| Pin | No. | Notes |
|---|---|---|
| **3V3** | 2 | Main power input |
| **EN** | 3 | Needs RC circuit — high = chip on |
| **VDD_SPI** | internal | Powers flash, handled inside module |
| **GPIO9** | 15 | Internal weak pull-up to 3V3 already |

---

## Required External Components

### Power Supply
| Component | Value | Purpose |
|---|---|---|
| Bulk capacitor | 22 µF | Power rail stabilization |
| Decoupling capacitor | 100 nF | High-freq noise filtering |

### EN Pin RC Delay Circuit
| Component | Value | Purpose |
|---|---|---|
| Resistor | 10 kΩ | EN pull-up |
| Capacitor | 1 µF | Delayed power-on reset |

### Boot Mode / Flash Button
| Component | Value | Purpose |
|---|---|---|
| Resistor to 3V3 | 10 kΩ | GPIO9 pull-up (backup, belt-and-suspenders) |
| Tactile switch to GND | — | Pull GPIO9 low to enter flash mode |
| Resistor | 100Ω series | Button debounce protection |

### Reset Button
| Component | Value | Purpose |
|---|---|---|
| Tactile switch to GND | — | Pull EN low to reset |
| Capacitor | 100 nF | Debounce |

### GPIO15 (JTAG)
| Component | Value | Purpose |
|---|---|---|
| Resistor to GND | 10 kΩ | Tie low = use USB Serial/JTAG controller |

### UART Programming Header (optional but recommended)
| Component | Value | Purpose |
|---|---|---|
| 2.54mm header 4-pin | — | TXD0, RXD0, GND, 3V3 |

### Decoupling per GPIO rail
| Component | Value | Purpose |
|---|---|---|
| 100 nF × 2 | — | Near pin 1 and pin 28 (GND pins) |

---

## ASCII PCB Text Diagram

```
                    ESP32-C6-WROOM-1-N8
    
    3V3 ──┬──────────────────────────────────── [Pin 2] 3V3
          │
         C_bulk (22µF)    C_dec (100nF)
          │                    │
         GND                  GND

    EN  ──┬──── R_en (10kΩ) ──── 3V3
          │
         C_en (1µF)
          │
         GND ──── SW_RESET (tactile) ──── EN


    GPIO9 ─┬──── R_pu (10kΩ) ──── 3V3        [Pin 15]
            │
           SW_BOOT (tactile)
            │
           GND


    GPIO8 ────────────────── floating         [Pin 10]


    GPIO15 ──── R (10kΩ) ──── GND             [Pin 23]
    (JTAG source → USB Serial/JTAG)


    TXD0 ──────────────────── [Pin 25] ──── UART Header Pin 1
    RXD0 ──────────────────── [Pin 24] ──── UART Header Pin 2
    GND  ──────────────────── [Pin 1]  ──── UART Header Pin 3
    3V3  ──────────────────── [Pin 2]  ──── UART Header Pin 4


    ┌─────────────────────────────────────────────┐
    │           SMART PLUG GPIO USAGE             │
    │                                             │
    │  IO6  [Pin 6]  ──── Relay 1 control        │
    │  IO7  [Pin 7]  ──── Relay 2 control        │
    │  IO0  [Pin 8]  ──── Relay 3 control        │
    │  IO1  [Pin 9]  ──── Relay 4 control        │
    │                                             │
    │  IO4  [Pin 4]  ──── ADC - Socket 1 sense   │
    │  IO5  [Pin 5]  ──── ADC - Socket 2 sense   │
    │  IO2  [Pin 27] ──── ADC - Socket 3 sense   │
    │  IO3  [Pin 26] ──── ADC - Socket 4 sense   │
    │                                             │
    │  IO6  [Pin 6]  ──── I2C SDA (alt use)      │
    │  IO7  [Pin 7]  ──── I2C SCL (alt use)      │
    │                                             │
    │  IO8  [Pin 10] ──── Status LED (Matter)    │
    │  IO10 [Pin 11] ──── User button            │
    └─────────────────────────────────────────────┘


    GND pins: Pin 1, Pin 28, Pin 29 (EPAD)
    ── EPAD must be soldered to ground plane ──
```

---

## Key Design Notes

1. **EPAD (Pin 29)** — solder to a solid ground plane, critical for thermal and electrical performance
2. **Antenna keepout zone** — no copper, traces, or components under the PCB antenna area on your base board
3. **3V3 regulator** — for a 4000W plug, use an isolated SMPS with a clean 3.3V LDO stage for the ESP32 (e.g. HLK-PM03 → AMS1117-3.3)
4. **Relay isolation** — use optocouplers (e.g. PC817) between ESP32 GPIOs and relay coil drivers to protect the module from mains transients
5. **EN RC timing** — the datasheet specifies minimum 3ms hold time after power rails stabilize before EN goes high — the 10kΩ + 1µF RC handles this automatically