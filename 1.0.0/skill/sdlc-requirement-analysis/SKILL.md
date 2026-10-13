---
name: sdlc-requirement-analysis
description: Use when a user provides an initial product idea or goal and needs a structured PRD with user stories, acceptance criteria, interface boundaries, and functional requirements
---

# SDLC Requirement Analysis

## Overview

Transform a raw product idea into a structured, reviewable PRD. This skill combines methodology alignment and PRD construction into one continuous workflow. It also seeds the Decision Log to prevent requirement drift across phases.

## VCMF Checkpoints

| Principle | Checkpoint in this Skill |
|-----------|--------------------------|
| Design as Contract | PRD must define closed-loop success metrics and scope boundaries |
| Interface as Boundary | Identify and list all cross-module interaction points in the PRD |
| Reality as Baseline | Acceptance criteria must be observable and testable |
| State as Responsibility | Document who owns each business state mentioned in user stories |

## When to Use

- The user says "I want to build..." or provides a vague product concept
- You need to produce a PRD before any architecture or code work can begin
- Do NOT use if a PRD already exists and has been approved

## Precondition Check

Read `skill/artifacts/STATE.md` if it exists. If `phase` is already `requirement_analysis_completed` or later, confirm with the user whether to overwrite or continue from the existing artifact.

## Workflow

1. **Methodology alignment**
   - Explain the "four-dimensional deduction" (Why / What / How / Modules)
   - State the five PRD quality standards (clear logic, closed loop, visuals, traceability, prioritization)
   - Surface edge-case questions (malicious traffic, third-party downtime, data consistency)

2. **State initialization**
   - Read `skill/artifacts/STATE.md` if it exists
   - If starting fresh, create `STATE.md` and populate the **Immutable Goal** section with the user's product idea, success metrics, and scope boundary
   - If `STATE.md` exists and `phase` is already `requirement_analysis_completed` or later, confirm with user whether to overwrite or continue

3. **Context gathering**
   - Ask 3-5 targeted questions about user personas, pain points, and business value
   - Wait for the user's answers

4. **Cross-module interaction mapping**
   - Based on the gathered context, identify all cross-module or cross-system interactions
   - List them in a dedicated section of the PRD

5. **PRD generation**
   - Produce a structured PRD containing:
     - Project background and goals (Why + success metrics)
     - Target user personas and scenarios
     - User stories with acceptance criteria (Given-When-Then or checklist)
     - Functional requirements graded P0 / P1 / P2
     - Non-functional requirements (performance, security, compliance)
     - Cross-module interaction points
     - Main process flow and fallback strategies
   - Write the PRD to `skill/artifacts/PRD.md`

6. **Decision Log seeding**
   - Create or update `skill/artifacts/DECISION_LOG.md`
   - Record the date, key requirement decisions, reasons, and rejected alternatives

7. **State update**
   - Read `skill/artifacts/STATE.md`
   - Write the **Immutable Goal** section if not already present (verbatim user idea + success metrics + scope boundary)
   - Append to **Completed Steps**: `[YYYY-MM-DD HH:MM] sdlc-requirement-analysis: Locked P0/P1/P2 scope. Key decisions: [list]`
   - Set `phase: requirement_analysis_completed`
   - Set DIVE `Design: in_progress`, others `pending`
   - Update artifact statuses

8. **Human gate**
   - Present a concise PRD summary (3-5 bullets)
   - Say exactly: "PRD 和决策日志已生成。请确认当前阶段输出。回复 [APPROVE] 进入架构设计阶段，或提出修改意见。"
   - Do NOT proceed until the user replies [APPROVE]

<HARD-GATE>
Do NOT proceed to architecture-design, write any code, or scaffold any project until the user replies [APPROVE].
</HARD-GATE>

## Output Specification

- `skill/artifacts/PRD.md`
- `skill/artifacts/DECISION_LOG.md`
- Must include P0/P1/P2 grading
- Must include acceptance criteria for every user story
- Must include at least one abnormal-path fallback
- Must include a "Cross-Module Interactions" section

## Red Flags

- Do NOT skip the human gate
- Do NOT generate architecture or code during this phase
- Do NOT proceed without writing `PRD.md` and `DECISION_LOG.md`
- Do NOT lose edge-case analysis from the original conversation
- Do NOT let acceptance criteria contain unobservable adjectives like "fast" or "user-friendly" without quantification
