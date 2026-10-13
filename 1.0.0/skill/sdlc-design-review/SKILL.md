---
name: sdlc-design-review
description: Use when a system architecture has been designed and the user wants an adversarial inspection to find design flaws before implementation begins
---

# SDLC Design Review

## Overview

Perform adversarial inspection (Red Team mode) on an approved architecture. The ONLY job of this skill is to find problems. It does NOT produce a PASS/FAIL gate. It produces a problem list for the user and subsequent skills to reference.

This skill answers: "Are there design flaws a technically correct document can still have?"
For technical consistency checks, use `sdlc-architecture-validation` instead.

## VCMF Checkpoints

| Principle | Checkpoint in this Skill |
|-----------|--------------------------|
| Design as Contract | Verify that architecture decisions trace back to PRD requirements; flag orphaned assumptions |
| Interface as Boundary | Verify that interfaces handle edge cases and failure modes, not just happy path |
| Reality as Baseline | Verify that mock data covers abnormal paths and NFR stress scenarios |
| State as Responsibility | Verify that every StateModel has complete lifecycle (create, read, update, delete, cleanup) |

## When to Use

- The user has approved an architecture and wants a skeptical second opinion
- High-stakes or complex projects where design flaws are costly
- Do NOT use if no architecture exists or has not been approved

## Precondition Check

Read `skill/artifacts/STATE.md`. If `phase` is not `architecture_design_completed` or `architecture.xml` is missing, stop and instruct the user to run `sdlc-architecture-design` first.

## Workflow

1. **Read all historical artifacts**
   - Load `PRD.md`, `STATE.md`, `DECISION_LOG.md`, `ARCHITECTURE.md`, `architecture.xml`, `INTERFACE_CONTRACT.md`
   - Understand the full reasoning chain, not just conclusions

2. **Attacker Lens (Security & Robustness)**
   - Does every module validate its input boundaries?
   - Are there race conditions in state transitions?
   - What happens if an external dependency (DB, API) fails? Is there a degradation path?
   - Are there single points of failure?
   - Is data encrypted in transit and at rest?
   - Are authentication and authorization enforced at every boundary?

3. **Operator Lens (Operability & Debuggability)**
   - If a module fails, can the root cause be located quickly?
   - Does the logging strategy cover all critical paths?
   - Do config changes require a restart?
   - Is test coverage sufficient (mock + real environment)?
   - Are docs and code synchronized?
   - Can the system be monitored and alerted effectively?

4. **Extender Lens (Scalability & Evolvability)**
   - If user load grows 10x, which module becomes the bottleneck first?
   - To add a new feature module, how much existing code must change?
   - Do interface contracts allow backward-compatible evolution?
   - Is state ownership clear (who creates, writes, reads, cleans up)?
   - Can external dependencies be swapped without rewriting core logic?

5. **Consolidate issue list**
   - Categorize findings:
     - **Must Fix**: Critical flaws that would cause system failure or security breach
     - **Should Fix**: High-risk issues that should be addressed before production
     - **Nice to Fix**: Low-risk improvements
     - **Documented Risks**: Accepted risks with explicit mitigation strategy
   - Cross-reference each issue to architecture decisions in `DECISION_LOG.md`

6. **Write `DESIGN_REVIEW.md`**
   - Output file: `skill/artifacts/DESIGN_REVIEW.md`
   - Must include:
     - Review metadata (date, artifacts reviewed)
     - Issue table with ID, description, location, impact, suggested fix
     - Cross-reference table linking issues to architecture decisions
     - Human gate phrase

7. **Update `STATE.md`**
   - Append all identified risks to **Known Pitfalls & Risks**
   - Set `phase: design_review_completed` (or keep existing phase if validation not yet run)

8. **Human gate**
   - Present issue summary (count by severity)
   - Say exactly: "设计审查报告已生成。这不是'通过/不通过'的检查，而是一份问题清单。请审阅上述问题，决定哪些需要修复、哪些可以接受。回复 [APPROVE] 进入项目脚手架阶段，回复 [FIX <issue_id>] 要求修复特定问题，或提出修改意见。"
   - Do NOT proceed until [APPROVE]

<HARD-GATE>
Do NOT proceed to project-scaffolding until the user replies [APPROVE]. This skill does NOT produce a PASS/FAIL conclusion.
</HARD-GATE>

## Output Specification

- `skill/artifacts/DESIGN_REVIEW.md`
- Must include: Must Fix / Should Fix / Nice to Fix / Documented Risks sections
- Must cross-reference issues to `DECISION_LOG.md` entries
- Must NOT contain a "PASS" or "FAIL" summary

## Red Flags

- Do NOT act as a gatekeeper; produce a problem list, not a verdict
- Do NOT skip any of the three lenses
- Do NOT invent issues not supported by the artifacts
- Do NOT proceed without the human gate
- Do NOT overwrite `STATE.md` Completed Steps (append-only)
