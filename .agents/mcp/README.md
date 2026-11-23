# MCP server policy and inventory

The project has reviewed workspace MCP definitions in the repository-root `.mcp.json`. Copilot CLI only discovers workspace configuration in `.mcp.json` or `.github/mcp.json`; keep the executable configuration at the root and keep AI-specific policy and setup documentation here.

Currently configured servers are EasyEDA Pro, JLCPCB Search, and JLC Parts. Their pinned versions, exposed tools, data flows, and setup instructions are documented in [CONFIGURED_SERVERS.md](CONFIGURED_SERVERS.md).

EMC work can use local, inspectable tools such as openEMS and ngspice without an MCP server. Only use configured MCPs when the task needs them.

Before adding a server:

1. State the task it enables and why ordinary local tools are insufficient.
2. Verify the publisher, source code or package, endpoint, permissions, and exact launch command.
3. Prefer read-only, narrowly scoped tools. Do not grant access to native CAD files, credentials, or unrestricted shell execution without a specific need.
4. Keep API keys and tokens out of the repository. Use the supported local secret mechanism.
5. Test the server with a low-impact, read-only request and inspect the tool activity.

This folder is documentation only; files here are not loaded as MCP configuration.
