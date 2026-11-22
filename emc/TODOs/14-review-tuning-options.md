# TODO 14 — Review design-for-tuning options

**Status:** Conditional — recommendations require evidence and qualified review  
**Depends on:** TODOs 02 and 04

## Work

- [ ] Identify whether a future board revision would benefit from alternative
  footprints or DNP options, based on the verified schematic and risk review.
- [ ] Consider only components whose function and circuit conditions are
  understood, such as low-voltage rail filtering or a documented, accessible
  switching node.
- [ ] Do not assume a sealed AC/DC module exposes an adjustable gate or switch
  node. Do not add a generic snubber or gate resistor without a validated
  circuit model and qualified electrical review.
- [ ] Do not recommend generic extra X/Y capacitors or a choke-bypass link.
  Capacitor class, leakage/touch current, discharge, voltage, and the safety
  barrier require component- and product-specific review.
- [ ] Check that even unpopulated pads preserve required creepage, clearance,
  isolation, thermal, and current-capacity requirements; obtain qualified
  review for safety-related regions.
- [ ] Record candidate variants in documentation only. Do not edit the native
  EasyEDA project or manufacturing files under this TODO.

## Done when

Any proposed option has a documented purpose, evidence basis, safety review
requirement, and DNP/populated variant impact. The TODO does not authorize
hardware changes or imply that footprints can be tuned without lab feedback.
