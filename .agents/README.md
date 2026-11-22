# Agent workspace

This folder holds project-specific, portable Agent Skills and guidance for AI-assisted hardware work. `AGENTS.md` at the repository root is the always-on project policy.

```text
.agents/
  README.md
  copilot-instructions.md
  orchestrator.agent.md
  agents/
    emc-precert-review.agent.md
  mcp/
    README.md
  skills/
    easyeda-pro-export/
      SKILL.md
    emc-precertification/
      SKILL.md
    emc-software-only/
      SKILL.md
    openems-modeling/
      SKILL.md
emc/
  README.md
  input-checklist.md
  risk-register.md
  openems/
    README.md
```

Project-specific instructions, skills, and custom agents are kept together under `.agents/`. Skill files use the Agent Skills `SKILL.md` format. The EMC reviewer is read-only.

SolidWorks COM automation guidance is maintained in the sibling `MECHANICAL/.agents/skills/solidworks-com/` directory, where its build procedures and error registry are used.

MCP server policy and setup notes are in `.agents/mcp/README.md`. No server is configured by default: the local simulation workflow does not require one, and an MCP server can execute code or access local resources. Copilot CLI workspace MCP configuration, when genuinely needed and reviewed, belongs in root `.mcp.json`, not in this documentation folder.
