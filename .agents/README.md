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
EMC/
  README.md
  input-checklist.md
  risk-register.md
  openems/
    README.md
```

Project-specific instructions, skills, and custom agents are kept together under `.agents/`. Skill files use the Agent Skills `SKILL.md` format. The EMC reviewer is read-only.

SolidWorks COM automation guidance is maintained in the sibling `MECHANICAL/.agents/skills/solidworks-com/` directory, where its build procedures and error registry are used.

MCP server policy and setup notes are in `.agents/mcp/`. The actual workspace configuration stays in root `.mcp.json` because Copilot CLI discovers workspace MCP configuration there (or in `.github/mcp.json`), not under `.agents/`. Keep server use task-scoped and review each server's publisher, permissions, and launch command before enabling it.

The root `.github/workflows/` directory contains only GitHub Actions workflows; GitHub does not discover workflows under `.agents/`.
