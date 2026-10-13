---
title: SDLC State
description: Template for the file-based state used by the SDLC skill chain
---

# SDLC State

## 1. Immutable Goal (Never Overwritten)
> Read at the start of every skill invocation to prevent drift.

- Original product idea: [verbatim from user]
- Core success metrics: [quantifiable criteria]
- Scope boundary (in-scope / out-of-scope): [...]

## 2. Completed Steps (Append-Only, Never Overwritten)
> Each skill appends its key decisions here after completion.

- [YYYY-MM-DD HH:MM] sdlc-requirement-analysis: [key decision summary]
- [YYYY-MM-DD HH:MM] sdlc-architecture-design: [key decision summary]

## 3. Current State (Overwritten)
> Reflects the latest progress.

- phase: [requirement_analysis_completed | architecture_design_completed | architecture_validated | scaffolding_completed]
- DIVE: Design: [pending|in_progress|completed], Implement: [pending|in_progress|completed], Verify: [pending|in_progress|completed], Evolve: [pending|in_progress|completed]
- Next skill: [sdlc-architecture-design | sdlc-architecture-validation | sdlc-design-review | sdlc-project-scaffolding]

## 4. Known Pitfalls & Risks (Append-Only)
> Every skill MUST append risks discovered during its unfold.

- [YYYY-MM-DD] Risk: [description]. Mitigation: [strategy].
