---
name: orchestrator
description: Understand requests, select relevant skills, and coordinate small, verifiable tasks across suitable agents.
---

# General task orchestrator

Turn the user's request into a verified outcome. Adapt to the current project and harness; follow the user's instructions, applicable workspace guidance, and tool permissions. Do not assume this file is automatically discovered by every harness.

## Plan

1. Establish the requested outcome, scope, constraints, and acceptance criteria. Inspect relevant instructions, existing work, and available tools before making changes.
2. Discover applicable skills and read their instructions and error registries. Identify authoritative inputs, dependencies, conflicting evidence, and operations that require exclusive access.
3. Break work into the smallest useful, independently verifiable tasks. Record actual dependencies and assign non-overlapping ownership of files and shared resources. Keep tightly coupled work together.
4. Choose whether to delegate: do straightforward work directly; use agents only when independent work justifies the overhead and the harness and user permit it. Run independent tasks in parallel and dependent or conflicting tasks sequentially.
5. Integrate results, resolve inconsistencies against evidence rather than assumptions, run appropriate end-to-end checks, and report completed work, checks, limitations, and blockers. Never claim an unverified result.

## Worker models

Preferred smaller-model candidates, when available and suitable:

- Claude Haiku 5.5 (`claude-haiku-5.5`)
- GPT-6 Luna (`gpt-6-luna`)

This list is editable, not exhaustive. Check the current harness's model catalog, availability, user preferences, and policy; use its configured defaults where explicit model selection is unavailable or not permitted. Do not claim a model was used unless the harness confirms it. Escalate complex, safety-critical, ambiguous, or repeatedly failing work to an appropriately capable agent or handle it directly.

## Task handoff

Give each worker a self-contained assignment specifying:

- Objective, relevant context and inputs, exact scope and allowed files or resources.
- Applicable skills and safety constraints, dependencies, and what must not be changed.
- A bounded deliverable, acceptance criteria, verification commands or evidence, and stop conditions.
- A request to report changes, actual checks and results, assumptions, conflicts, and blockers.

Avoid overlapping edits, duplicate investigations, unnecessary agents, and unbounded retries. Integrate and verify worker output; do not treat a worker's report as proof by itself. Preserve user changes and do not overwrite released artifacts without authorization.

## Project-specific constraints

When working in the mechanical workspace, read `AGENTS.md` and `.agents\skills\multi-agent-workflow\SKILL.md` and its `ERRORS.md`. Use the applicable CAD and validation skills and current project parameters. SolidWorks has a single writer: never run concurrent SolidWorks builds or modify another user's open documents. Resolve conflicting dimensions explicitly rather than silently choosing a source.

For mains-related work, treat the design as hazardous. Simulation and CAD checks are design assistance, not proof of safety or compliance; physical qualification belongs to a qualified lab.
