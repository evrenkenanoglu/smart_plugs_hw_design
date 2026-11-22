# TODO 12 — Model radio/antenna interaction, if present

**Status:** Conditional — exact radio/antenna evidence remains necessary for claims  
**Depends on:** TODOs 08 and 09; requires the exact radio/antenna data

## Work

- [ ] Identify whether the selected candidate contains a radio and document
  its exact module, antenna, feed, and vendor layout constraints.
- [ ] Include the actual relevant board ground/copper and nearby enclosure or
  metal only when their geometry/materials are known.
- [ ] Define a suitable RF feed/port and calculate the requested quantity,
  such as a controlled S11 or coupling comparison, with correct port
  normalization.
- [ ] Compare only justified layout/enclosure variants; mesh-refine the feed,
  keep-out, and nearby features.
- [ ] Do not infer receiver desensitization, coexistence performance, or radio
  compliance from S11 alone.

## Done when

The model matches the exact radio implementation and provides a converged
relative result for its stated quantity, with unmodeled radio behavior listed.
