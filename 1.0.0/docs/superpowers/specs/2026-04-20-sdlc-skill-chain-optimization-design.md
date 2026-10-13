# SDLC Skill Chain Optimization Design

> **Objective**: Refactor the existing 4-skill SDLC chain (`sdlc-requirement-analysis` → `sdlc-architecture-design` → `sdlc-architecture-validation` → `sdlc-project-scaffolding`) from a "role-based relay race" to a "single thinker's iterative drafts" model, guided by insights from industry best practices (Anthropic, OpenAI, Google).

---

## 1. Core Problem Diagnosis

### 1.1 The "Three Departments" Anti-Pattern

The current 4-skill chain implicitly models a factory assembly line: each skill acts as a different worker (PM → Architect → QA → Dev), passing documents downstream. This creates two fundamental problems:

1. **Role boundaries create artificial constraints**: A skill framed as "architecture-design" may refuse to revisit requirement gaps because "that's not my phase." The most valuable reasoning happens at boundaries, but the pipeline seals them off.
2. **Information dies in transit**: Each skill reads only the previous phase's output (compressed conclusions), not the full reasoning chain. Original intent decays, implicit assumptions are lost, and errors accumulate.

### 1.2 The Real Bottleneck

LLMs do not have human limitations (attention span, skill silos, communication overhead). Their bottleneck is **reasoning depth and information completeness**, not "division of labor." The correct multi-agent pattern is **functional parallel exploration** (orchestrator-worker with results flowing back to the orchestrator), not **functional division of labor** (relay race with documents passed downstream).

---

## 2. Guiding Principles (from Industry Practice)

| Principle | Source | Application in This Design |
|-----------|--------|---------------------------|
| **Reasoning chain must not break; it can only fork and merge** | Anthropic | Each skill reads ALL historical artifacts, not just the previous phase's output |
| **Explicit external state, not model memory** | Anthropic / OpenAI | `STATE.md` becomes a cross-session reasoning anchor with 4 categories of information |
| **Multi-agent value is parallel coverage, not division of labor** | Anthropic Research System | `architecture-design` uses orchestrator-worker to evaluate multiple patterns in parallel |
| **Verification agent is a skeptic, not a successor** | Industry best practice | New `sdlc-design-review` skill: its ONLY job is finding problems, not "passing work forward" |
| **Code must carry the reasoning chain** | Google Context-Driven Development | Generated code includes comments linking back to architecture decisions and known risks |

---

## 3. Design Overview

### 3.1 Mental Model Shift

**Old model**: 4 skills = 4 different workers on an assembly line.

**New model**: 4 skills = **the same thinker facing the same complex problem, unfolding it 4 times**, each time focusing on a different dimension but always holding the complete intent:

- **Requirement Analysis** = 1st unfold: Lock the goal and boundaries.
- **Architecture Design** = 2nd unfold: After the goal is locked, explore multiple technical paths in parallel and synthesize the best solution.
- **Design Review** = 3rd unfold: The same thinker deliberately switches to a skeptical lens to examine their own solution.
- **Project Scaffolding** = 4th unfold: Ground all previous conclusions into runnable code.

### 3.2 Key Constraint

Every skill, at startup, MUST read **ALL historical artifacts** (`PRD.md`, `STATE.md`, `DECISION_LOG.md`, `ARCHITECTURE.md`, `architecture.xml`, `INTERFACE_CONTRACT.md`, and `DESIGN_REVIEW.md`), not just the previous phase's output.

---

## 4. Global State Refactoring: `STATE.md` → Reasoning Chain Anchor

### 4.1 Current Problem

Current `STATE.md` is a simple phase marker (`phase: requirement_analysis_completed`). It does not preserve reasoning history or prevent goal drift across sessions.

### 4.2 New Structure

`STATE.md` becomes an **explicit external state file** with four categories of information, directly inspired by Anthropic's `claude-progress.txt` pattern:

```markdown
---
title: SDLC State
updated: 2026-04-20
---

## 1. Immutable Goal (Never Overwritten)
> Read at the start of every skill invocation to prevent drift.

- Original product idea: [verbatim from user]
- Core success metrics: [quantifiable criteria]
- Scope boundary (in-scope / out-of-scope): [...]

## 2. Completed Steps (Append-Only, Never Overwritten)
> Each skill appends its key decisions here after completion.

- [2026-04-20 10:00] sdlc-requirement-analysis: Locked P0/P1/P2 scope. Key decision: support only Webhook mode for production; Polling is dev-only.
- [2026-04-20 11:30] sdlc-architecture-design: Evaluated 4 patterns (Layered, Hexagonal, Event-Driven, Microservice). Selected Hexagonal. Reason: PRD requires explicit cross-module contracts.

## 3. Current State (Overwritten)
> Reflects the latest progress.

- phase: architecture_design_completed
- DIVE: Design: completed, Implement: pending, Verify: pending, Evolve: pending
- Next skill: sdlc-design-review (recommended) or sdlc-architecture-validation (optional)

## 4. Known Pitfalls & Risks (Append-Only)
> Every skill MUST append risks discovered during its unfold.

- [2026-04-20 11:30] Risk: Hexagonal architecture has a steep learning curve for the team. Mitigation: comprehensive interface documentation.
- [2026-04-20 11:30] Risk: Event-Driven was rejected due to YAGNI, but if async event flows emerge in Phase 2, architecture may need refactoring.
```

### 4.3 Why This Works

- **Immutability of Goal**: Prevents later skills from silently shifting the original intent.
- **Append-Only History**: The next session reads the complete history, not a compressed conclusion from the previous phase.
- **Known Pitfalls**: Forces risks to surface early. Scaffolding can generate TODOs directly from this section.
- **Overwritable Current State**: Still provides a quick summary of "where we are now."

---

## 5. Skill 2 Refactor: `sdlc-architecture-design` — Parallel Exploration + Synthesis

### 5.1 Current Problem

Current workflow: evaluate 6 patterns → recommend one → detailed modeling. This is **single-path depth-first search**. It wastes the LLM's ability to hold multiple hypotheses simultaneously.

### 5.2 New Workflow: Orchestrator-Worker Pattern

```
┌─────────────────────────────────────────────────────────────┐
│ Orchestrator: architecture-design skill                     │
│ Reads: PRD.md + STATE.md + DECISION_LOG.md (full history)   │
│ Determines: evaluation dimensions (coupling, data isolation, │
│   scalability, team familiarity, maintenance cost)           │
└──────────────────┬──────────────────────────────────────────┘
                   │ Dispatch in parallel
        ┌──────────┼──────────┬──────────┐
        ▼          ▼          ▼          ▼
┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
│ Worker 1 │ │ Worker 2 │ │ Worker 3 │ │ Worker 4 │
│ Layered  │ │Microsvc  │ │Event-Driv│ │Hexagonal │
└────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘
     │            │            │            │
     └────────────┴─────┬──────┴────────────┘
                        ▼
              ┌─────────────────┐
              │ Orchestrator    │
              │ Synthesis Report│
              │ - Score matrix  │
              │ - Recommendation│
              │ - Full reasoning│
              └────────┬────────┘
                       ▼
              Generate ARCHITECTURE.md
              Generate architecture.xml (with DecisionTrace)
              Update DECISION_LOG.md
```

### 5.3 `DECISION_LOG.md` Upgrade: Full Reasoning Chain

Current `DECISION_LOG.md` only records conclusions ("Selected Hexagonal Architecture"). It must record the **complete reasoning chain**:

```markdown
## [2026-04-20 14:30] Architecture Selection Decision Chain

**Evaluation Dimensions**: Coupling, Data Isolation, Scalability, Team Familiarity, Maintenance Cost

| Candidate     | Coupling | Data Isolation | Scalability | Familiarity | Maintenance | Total |
|---------------|----------|----------------|-------------|-------------|-------------|-------|
| Layered       | High     | Medium         | Low         | High        | Low         | 6/10  |
| Hexagonal     | Low      | High           | Medium      | Low         | Medium      | 7/10  |
| Event-Driven  | Low      | High           | High        | Low         | High        | 6/10  |
| Microservice  | Low      | High           | High        | Medium      | High        | 5/10  |

**Recommended**: Hexagonal Architecture

**Full Reasoning**:
1. PRD requires explicit cross-module I/O contracts → Hexagonal's Ports/Adapters naturally satisfy this.
2. PRD anticipates future replacement of external deps (e.g., vector DB) → Hexagonal isolates external dependencies via adapters.
3. Layered has high team familiarity, but historically produces cross-layer call chaos → long-term maintenance cost outweighs short-term familiarity.
4. Event-Driven has excellent scalability, but PRD Phase 1 has no async event flow requirements → violates YAGNI.
5. Microservice is overkill for the current scope and introduces deployment complexity.

**Rejected Alternatives & Why**:
- Layered: Familiarity advantage offset by "cross-layer chaos" long-term risk.
- Event-Driven: Introduces async complexity for a requirement that does not yet exist.
- Microservice: Scope too small to justify operational overhead.
```

### 5.4 XML Enhancement: `<DecisionTrace>` Node

`architecture.xml` gains a `<DecisionTrace>` section to externalize key reasoning nodes directly into the architecture document:

```xml
<SystemArchitecture type="Hexagonal">
    <DecisionTrace>
        <Decision id="ARCH-001" date="2026-04-20">
            <Question>Why Hexagonal over Layered?</Question>
            <Answer>PRD requires explicit cross-module contracts; Hexagonal Ports/Adapters naturally satisfy this.</Answer>
            <Risk>Team learning curve is steep; compensate with comprehensive interface docs.</Risk>
        </Decision>
        <Decision id="ARCH-002" date="2026-04-20">
            <Question>Why not Event-Driven?</Question>
            <Answer>No async event flow requirements in PRD Phase 1; YAGNI.</Answer>
            <Risk>If async flows emerge in Phase 2, architecture may need extension (not replacement).</Risk>
        </Decision>
    </DecisionTrace>
    <!-- Existing: Module, DataModel, StateModel, Security -->
</SystemArchitecture>
```

**Benefit**: Architecture documents carry their own reasoning. Later skills (and human readers) can understand *why* without relying on model context memory.

---

## 6. New Skill: `sdlc-design-review` — Skeptical Examination, Not Relay

### 6.1 Design Philosophy

Current `sdlc-architecture-validation` implicitly acts as a "gatekeeper": check → PASS/FAIL → if pass, proceed to scaffolding. This is still a relay race.

The new `sdlc-design-review` skill's **ONLY job is to find problems**. It does NOT produce a "pass" conclusion. It does NOT control whether scaffolding can proceed. It produces a **problem list** for the user and subsequent skills to reference.

This is **adversarial inspection**, not **relay handoff**.

### 6.2 Three Inspection Lenses

```
Reads: ALL historical artifacts (PRD, STATE, DECISION_LOG, ARCHITECTURE, XML, INTERFACE_CONTRACT)
        │
        ▼
┌─────────────────────────────────────────┐
│ Adversarial Review (Red Team Mode)      │
│ Examine architecture from 3 independent │
│ perspectives                            │
└──────────────────┬──────────────────────┘
                   │
        ┌──────────┼──────────┐
        ▼          ▼          ▼
   ┌────────┐ ┌────────┐ ┌────────┐
   │Attacker│ │Operator│ │Extender│
   │Lens    │ │Lens    │ │Lens    │
   └────┬───┘ └────┬───┘ └────┬───┘
        │          │          │
        └──────────┼──────────┘
                   ▼
        ┌─────────────────────┐
        │ Consolidated Issue  │
        │ List                │
        │ - Must Fix          │
        │ - Should Fix        │
        │ - Nice to Fix       │
        │ - Documented Risk   │
        └──────────┬──────────┘
                   ▼
        Write DESIGN_REVIEW.md
        Update STATE.md (append Known Pitfalls)
        Present to user
```

**Attacker Lens** (Security & Robustness):
- Does every module validate its input boundaries?
- Are there race conditions in state transitions?
- What happens if an external dependency (DB, API) fails? Is there a degradation path?
- Are there single points of failure?
- Is data encrypted in transit and at rest?

**Operator Lens** (Operability & Debuggability):
- If a module fails, can the root cause be located quickly?
- Does the logging strategy cover all critical paths?
- Do config changes require a restart?
- Is test coverage sufficient (mock + real environment)?
- Are docs and code synchronized?

**Extender Lens** (Scalability & Evolvability):
- If user load grows 10x, which module becomes the bottleneck first?
- To add a new feature module, how much existing code must change?
- Do interface contracts allow backward-compatible evolution?
- Is state ownership clear (who creates, writes, reads, cleans up)?

### 6.3 Output: `DESIGN_REVIEW.md`

```markdown
# Design Review Report

## Review Metadata
- Date: 2026-04-20
- Reviewer: sdlc-design-review (Red Team Mode)
- Artifacts Reviewed: PRD.md, ARCHITECTURE.md, architecture.xml, INTERFACE_CONTRACT.md, DECISION_LOG.md

## Issues Found

### 🔴 Must Fix (Critical)

| ID | Issue | Location | Impact | Suggested Fix |
|----|-------|----------|--------|---------------|
| R001 | L3 Orchestration has no timeout handling for L5 tool calls | architecture.xml Module "L3" | L5 hang causes L3 infinite wait | Add timeout config + fallback in INTERFACE_CONTRACT |

### 🟡 Should Fix (High Risk)

| ID | Issue | Location | Impact | Suggested Fix |
|----|-------|----------|--------|---------------|
| R002 | StateModel lacks cleanup policy for abandoned sessions | architecture.xml StateModel "Session" | Memory leak over time | Add TTL + auto-cleanup lifecycle |

### 🟢 Nice to Fix (Low Risk)

| ID | Issue | Location | Impact | Suggested Fix |
|----|-------|----------|--------|---------------|
| R003 | Coupling graph is not validated for cycles | architecture.xml Coupling | Potential circular dependency | Add cycle detection to health-check script |

### ⚪ Documented Risks (Accepted)

| ID | Risk | Why Accepted | Mitigation |
|----|------|--------------|------------|
| R004 | Hexagonal architecture learning curve | PRD contract requirements outweigh short-term cost | Comprehensive onboarding docs + pair programming |

## Cross-Reference to Architecture Decisions

| Issue ID | Linked Decision | Note |
|----------|----------------|------|
| R001 | ARCH-001 | "Explicit contracts" assumed synchronous response; timeout not modeled |
| R002 | ARCH-003 | Session state ownership defined but lifecycle incomplete |

## Human Gate

**This is NOT a pass/fail check. It is a problem list.**
**Please review the issues above and decide which to fix, which to accept, and which to defer.**
**Reply [APPROVE] to proceed to scaffolding, [FIX <id>] to request a fix, or provide feedback.**
```

### 6.4 Relationship with Existing `sdlc-architecture-validation`

`sdlc-architecture-validation` is **retained but scope is narrowed**:
- **Technical validation**: consistency checks (XML vs Interface Contract), mock data flow validation, topology connectivity.
- **Health-check script generation**: `health-check.sh`.

It answers "Does the architecture document hang together technically?"

`sdlc-design-review` answers "Are there design flaws a technically correct document can still have?"

Users can run either or both:
- Run only `validation` if they trust the design.
- Run `design-review` for high-stakes or complex projects.
- Run both for maximum rigor.

---

## 7. Skill 4 Adjustment: `sdlc-project-scaffolding` — Grounding with Full Context

### 7.1 Input Expansion

| Current Reads | New Reads |
|---------------|-----------|
| `ARCHITECTURE.md`, `architecture.xml`, `INTERFACE_CONTRACT.md`, `VALIDATION_REPORT.md` | **ALL historical artifacts**: `PRD.md`, `STATE.md`, `DECISION_LOG.md`, `ARCHITECTURE.md`, `architecture.xml`, `INTERFACE_CONTRACT.md`, `VALIDATION_REPORT.md`, **`DESIGN_REVIEW.md`** |

**Why**: Scaffolding without full context is "construction by blueprint." When the blueprint is incomplete (inevitable), the worker guesses. With full context, scaffolding can trace ambiguous points back to original requirements, decision reasoning, and known risks.

### 7.2 Generated Code: Reasoning Chain Comments

Every core module MUST include a header comment linking it to architecture decisions and known risks:

```python
# src/l3/l3_orchestration.py
# ------------------------------------------------------------------------------
# Module: L3 Orchestration Layer
# Architecture Decision: ARCH-001 (see DECISION_LOG.md)
# Reasoning: PRD requires ReAct loop + security judgment + L5 error handling.
#   Pure ReAct chosen over TaskPlanner-as-primary because current task
#   complexity does not justify multi-agent orchestration overhead.
# Known Risk: R004 — If future phases require multi-step complex tasks,
#   TaskPlanner integration will be needed (see DESIGN_REVIEW.md).
# ------------------------------------------------------------------------------
```

### 7.3 Code-Level TODOs from Design Review

Issues from `DESIGN_REVIEW.md` are translated into inline TODOs with explicit priority:

```python
# TODO(DESIGN-REVIEW-R001): L5 tool call timeout not yet implemented.
#   Current: Orchestration.run() waits indefinitely for L5 response.
#   Required: Add timeout config (default 30s) + fallback to error Observation.
#   Priority: Must Fix. Blocking for production use.

# TODO(DESIGN-REVIEW-R002): Session cleanup policy not implemented.
#   Current: Sessions accumulate in memory forever.
#   Required: Add TTL (7 days) + scheduled cleanup job.
#   Priority: Should Fix. Non-blocking for MVP.
```

### 7.4 New Artifact: Architecture Decision Record (`docs/ADR.md`)

Inside `PROJECT_SCAFFOLD/docs/ADR.md`, the reasoning chain from `DECISION_LOG.md` is transformed into a human-readable Architecture Decision Record. This is a **persistent reasoning anchor** inside the codebase.

### 7.5 New Verification Step: Traceability Audit

After internal verification (paths, signatures), scaffolding performs a **traceability audit**:

```
For 3-5 randomly sampled generated files:
  Q1: What PRD requirement does this file trace back to?
  Q2: What INTERFACE_CONTRACT entry does this file's signature trace back to?
  Q3: Does this file's state management match the XML StateModel?
  
  If any answer is untraceable → mark as traceability gap
  → Append to STATE.md Known Pitfalls
```

---

## 8. Complete Refactored Flow

```
User inputs product idea
        │
        ▼
┌─────────────────────────────────────────────────────────────┐
│ Skill 1: sdlc-requirement-analysis                         │
│ 1st Unfold: Lock goal and boundaries                       │
│ Reads: None (starting fresh)                               │
│ Outputs: PRD.md + DECISION_LOG.md (seeded)                 │
│ Updates STATE.md: Immutable Goal + Completed Steps         │
└──────────────────┬──────────────────────────────────────────┘
                   │ [APPROVE]
                   ▼
┌─────────────────────────────────────────────────────────────┐
│ Skill 2: sdlc-architecture-design                          │
│ 2nd Unfold: Explore tech paths in parallel, synthesize     │
│ Reads: PRD.md + STATE.md + DECISION_LOG.md (full history)  │
│ Internal: Orchestrator-Worker parallel evaluation          │
│ Outputs: ARCHITECTURE.md + INTERFACE_CONTRACT.md           │
│          + architecture.xml (with DecisionTrace)           │
│ Updates DECISION_LOG.md: Full reasoning chain              │
│ Updates STATE.md: Append completed step                    │
└──────────────────┬──────────────────────────────────────────┘
                   │ [APPROVE]
                   ▼
        ┌─────────┴─────────┐
        ▼                   ▼
┌───────────────┐   ┌─────────────────────────┐
│ validation    │   │ design-review            │
│ (Optional)    │   │ (New, Adversarial)       │
│ Technical     │   │ Attacker / Operator /    │
│ consistency   │   │ Extender lenses          │
│ + mock flow   │   │ Output: Issue list       │
└───────────────┘   └─────────────────────────┘
        │                   │
        └─────────┬─────────┘
                  ▼
           User reviews issue list
           [APPROVE] or [FIX <id>]
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│ Skill 4: sdlc-project-scaffolding                          │
│ 4th Unfold: Ground with full context                       │
│ Reads: ALL artifacts (PRD + STATE + DECISION_LOG           │
│        + ARCHITECTURE + XML + INTERFACE + VALIDATION       │
│        + DESIGN_REVIEW)                                    │
│ Outputs: PROJECT_SCAFFOLD/                                 │
│          (with reasoning comments + ADR + code TODOs)      │
│ Verification: Traceability audit                           │
│ Updates STATE.md: Append completed step + update state     │
└──────────────────┬──────────────────────────────────────────┘
                   │ [APPROVE]
                   ▼
                 Done
```

---

## 9. Mechanism Summary

| Mechanism | Current Design | New Design | Rationale |
|-----------|---------------|------------|-----------|
| **Information Transfer** | Read only previous phase's output | **Read ALL historical artifacts** | Prevents information decay; next skill sees full history |
| **Reasoning Chain** | Relies on model context memory | **Externalized to STATE.md + DECISION_LOG + XML DecisionTrace** | Session continuity via explicit state, not model memory |
| **Architecture Decision** | Single-path depth-first | **Orchestrator-Worker parallel exploration + synthesis** | Uses LLM's ability to evaluate multiple hypotheses simultaneously |
| **Verification Role** | Gatekeeper (PASS/FAIL, then proceed) | **Skeptic (finds problems, does NOT control flow)** | Adversarial inspection, not relay handoff |
| **Code Comments** | Functional description | **Carry reasoning chain (why exists, linked decision, known risk)** | Codebase becomes self-documenting reasoning anchor |
| **State File** | Simple phase marker | **4 categories: Immutable Goal + Append-Only History + Overwritable State + Append-Only Pitfalls** | Cross-session reasoning chain anchor |
| **Decision Log** | Conclusion-only | **Full reasoning chain (evaluation matrix + rejected alternatives + why)** | Decisions are reviewable and reversible |

---

## 10. Migration Path

### 10.1 Files to Modify

| File | Change |
|------|--------|
| `skill/sdlc-state.md` | Update template to 4-category structure |
| `skill/sdlc-requirement-analysis/SKILL.md` | Add: read STATE.md at start; write Immutable Goal section; append to Completed Steps |
| `skill/sdlc-architecture-design/SKILL.md` | Refactor: add orchestrator-worker parallel evaluation; upgrade DECISION_LOG to reasoning chain; add DecisionTrace to XML schema |
| `skill/sdlc-architecture-validation/SKILL.md` | Narrow scope: remove adversarial inspection; focus on technical consistency + mock flow |
| `skill/sdlc-project-scaffolding/SKILL.md` | Expand reads: add DESIGN_REVIEW.md; add code reasoning comments requirement; add ADR generation; add traceability audit |
| `skill/README.md` | Add `sdlc-design-review` to skills table; update flow diagram |
| `skill/sdlc-design.md` | Update to reflect new design philosophy |

### 10.2 Files to Create

| File | Purpose |
|------|---------|
| `skill/sdlc-design-review/SKILL.md` | New skill: adversarial inspection with 3 lenses |
| `skill/sdlc-design-review/` | New directory |

### 10.3 Backward Compatibility

- Existing `STATE.md` files with the old format can be **migrated automatically**: extract `phase` → Current State; append a migration note → Completed Steps.
- The 4-skill chain (without `design-review`) still works; `design-review` is **opt-in** but recommended.
- `sdlc-architecture-validation` still exists; its scope narrowing does not break existing invocations.

---

## 11. Acceptance Criteria

1. `STATE.md` template contains 4 categories: Immutable Goal, Completed Steps, Current State, Known Pitfalls.
2. `sdlc-architecture-design` SKILL.md describes orchestrator-worker parallel evaluation workflow.
3. `architecture.xml` schema includes `<DecisionTrace>` node with `<Question>`, `<Answer>`, `<Risk>` children.
4. `DECISION_LOG.md` format requires full reasoning chain (evaluation matrix + rejected alternatives + why).
5. `sdlc-design-review` SKILL.md exists and defines 3 inspection lenses (Attacker, Operator, Extender).
6. `sdlc-design-review` output is a problem list, NOT a PASS/FAIL gate.
7. `sdlc-project-scaffolding` SKILL.md requires reading `DESIGN_REVIEW.md` and generating code with reasoning comments.
8. `sdlc-project-scaffolding` generates `docs/ADR.md` inside the scaffold.
9. `sdlc-project-scaffolding` includes a traceability audit step.
10. All 5 skills (4 existing + 1 new) are documented in `skill/README.md`.

---

*Design Version: v1.0*
*Date: 2026-04-20*
