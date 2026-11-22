
## 1. Input EMI & Protection Block
*Filters the dirty AC mains entering the board and protects against surges/fire.*

| Component | Designator | Value / Part | Function |
| :--- | :--- | :--- | :--- |
| **Fuse Holder** | `FH1` | **PTF-77** | Holds the **1A Slow Blow Fuse**. Protects against catastrophic short circuits. |
| **NTC Thermistor** | `R2` | **10D-7** (10Ω) | Limits **Inrush Current** when plugged in to protect the Fuse and Bridge Rectifier. |
| **Varistor** | `RV1` | **14D431K** | **Surge Protection.** Clamps voltage spikes (Lightning/Grid swells). *Note: 431K is rated for 275VAC Max.* |
| **Safety Cap** | `C7` | **100nF X2** | **Differential Filter.** Removes noise between Live and Neutral. |
| **Common Mode Choke** | `L1` (Input) | **UU9.8 10mH** | **Common Mode Filter.** Blocks high-frequency noise from escaping back to the grid. |

**🔗 Wiring Topology:**
`AC Live` $\rightarrow$ `FH1 (Fuse)` $\rightarrow$ `R2 (NTC)` $\rightarrow$ [`RV1` + `C7`] (Parallel) $\rightarrow$ `L1 (Choke)` $\rightarrow$ **To HLK AC Input**.

