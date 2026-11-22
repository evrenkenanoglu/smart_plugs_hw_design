# MCP server policy

No MCP server is enabled for this project. EMC work can use local, inspectable tools such as openEMS and ngspice without granting an agent access to a remote service or arbitrary local commands.

Before adding a server:

1. State the task it enables and why ordinary local tools are insufficient.
2. Verify the publisher, source code or package, endpoint, permissions, and exact launch command.
3. Prefer read-only, narrowly scoped tools. Do not grant access to native CAD files, credentials, or unrestricted shell execution without a specific need.
4. Keep API keys and tokens out of the repository. Use the supported local secret mechanism.
5. Test the server with a low-impact, read-only request and inspect the tool activity.

Copilot CLI reads workspace server configuration from root `.mcp.json`. This folder is documentation only; files here are not loaded as MCP configuration.
