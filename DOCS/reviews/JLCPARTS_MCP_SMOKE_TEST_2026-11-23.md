# JLC Parts MCP catalog smoke test

**Result:** Build and offline API smoke tests passed. Catalog results are not
evidence of component suitability, design approval, current live stock, or
safety.

## Provenance

- MCP source: `ititti-es/jlcparts-mcp` commit
  `cc11adcfd8d39a53006318af19b0829dd2bdf352`.
- Catalog source: `yaqwsx/jlcparts` archive, upstream last-modified
  **2026-11-23 01:03:39 UTC**.
- Database build: **2026-11-23 09:00:16 local time**
  (**08:00:16 UTC**); the MCP reported index version 2 and 646,202 in-stock
  parts.
- The database is in the user's default cache and is not committed to this
  repository.

## Offline smoke tests

All calls used `live=false`; no live JLCPCB requests were made.

- Database status reported the index present and idle, with no build error.
- `search_parts(query="ESP32 C6")` returned three mirror candidates.
- `check_bom` for `C20627095`, quantity 1, returned `ok`, zero problems, and
  one line from the mirror (`stock_checked`: `mirror 2026-10-06`).
- Exact offline searches for the current BOM numbers `C48935101` and
  `C5366877` returned no matches. An offline BOM check marked both as unknown
  / not in the mirror and reported two problems.

## Limitations

The smoke test verifies the local index and offline search/BOM code paths, not
the current smart-plug BOM. The mirror is incomplete, and stock freshness is
per-part: the archive timestamp does not make every row's stock or price
current. The two current BOM part numbers were not found offline, so do not
use this mirror to validate or substitute those components.
