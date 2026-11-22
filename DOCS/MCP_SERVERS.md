# EDA and component-catalog MCP servers

The workspace `.mcp.json` configures local stdio servers for Copilot CLI.
The CLI reads workspace MCP configuration after the folder is trusted. The
JLCPCB servers use `uvx` and EasyEDA Pro uses `npx`, keeping their dependencies
outside the hardware project's Python virtual environment.

## EasyEDA Pro MCP

`easyeda-mcp-pro` is pinned to npm version 1.16.0 and runs under Node.js 24.
It requires EasyEDA Pro and its local MCP bridge to be running. The tool
allow-list includes board inspection, checks, BOM reads, and exports; schematic
or PCB mutation tools are not exposed. Export calls can still write files, so
follow the project preflight and no-overwrite rules before invoking them.

## JLCPCB Search MCP

`jlcpcb-search-mcp` is pinned to PyPI version 1.2.1. On first search it builds a
local SQLite catalog from the `yaqwsx/jlcparts` data. This can take several
minutes and requires a network download. Searches also make live requests to
LCSC/JLCPCB for candidate part availability and pricing, so search terms and
part numbers leave the machine.

Only search, detail, and database-status tools are exposed. The server's
`refresh_database` tool is excluded because it deletes the current database
before refreshing it.

## JLC Parts MCP

`jlcparts-mcp` is pinned to Git commit
`cc11adcfd8d39a53006318af19b0829dd2bdf352` (project version 0.2.0). It
downloads the upstream split `cache.zip`, extracts `cache.sqlite3` temporarily,
and builds its own local `parts.sqlite3`; it does not query the upstream
`cache.sqlite3` in place.

The local database must be built once before search tools can return results.
From PowerShell in this directory:

```powershell
uvx --from "git+https://github.com/ititti-es/jlcparts-mcp.git@cc11adcfd8d39a53006318af19b0829dd2bdf352" jlcparts-mcp build
```

The build downloads catalog data from `yaqwsx/jlcparts` and stores the index in
the user's default `~/.cache/jlcparts-mcp` directory. The configured MCP server
sets `JLCPARTS_MCP_LIVE=0`, so normal searches use the local database without
live JLCPCB requests. Its `update_database` tool is excluded from the exposed
tool list.

## Verify

Run `copilot mcp list` from this workspace to inspect the registered servers.
The `tools` allow-lists in `.mcp.json` are honored by Copilot CLI; other MCP
clients may require their own configuration and tool restrictions. Both
servers are third-party software and depend on catalog data hosted by
`yaqwsx/jlcparts`.
