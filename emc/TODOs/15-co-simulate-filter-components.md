# TODO 15 — Co-simulate filter components and PCB network

**Status:** Candidate co-simulation permitted with explicit model assumptions and strict numerical checks  
**Depends on:** TODO 07 and relevant completed local models; requires
component models or explicitly bounded candidate assumptions

## Work

- [ ] Confirm exact component manufacturer part numbers and model validity over
  the target frequency range.
- [ ] Combine the component and PCB networks using documented ports,
  terminations, reference impedances, and network normalization.
- [ ] Compare controlled cases: schematic-only, component parasitics, and
  component parasitics plus extracted PCB parasitics.
- [ ] Sweep justified component and material tolerances; identify which
  assumptions dominate the comparison.
- [ ] Report model results as relative behavior for the selected network only.

## Done when

The comparison is reproducible, component models cover the analysis band, and
any claimed layout effect is larger than numerical and input uncertainty.

## Stop condition

Do not recommend PCB changes based on arbitrary dB thresholds or unsupported
component/source models. This is a network-level model, not an emissions test.
