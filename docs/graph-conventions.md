# Graph conventions
- Edge `A -> B` means **A supplies B**; B depends on A.
- Relationship types: `required` (hard dependency), `partial` (degrades B in proportion to strength),
  `backup` (alternative supplier used when the primary fails). Exact propagation rules are fixed in Phase 4.
- `capacity` and `demand` share the node's own `meta.unit`.
  `meta.demands` lists what a node needs from its suppliers (e.g. {"electricity": 60}).
- All NEXUS Campus values are synthetic demonstration data.