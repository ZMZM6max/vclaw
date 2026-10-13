---
name: sdlc-project-scaffolding
description: Use when architecture design (and optional validation) is approved and the user needs concrete project scaffolding, CI/CD pipelines, transparent test fixtures, and evolution infrastructure
---

# SDLC Project Scaffolding

## Overview

Generate hard deliverables by grounding all historical conclusions into runnable code. Reads the full reasoning chain (PRD, STATE, DECISION_LOG, ARCHITECTURE, XML, INTERFACE_CONTRACT, VALIDATION_REPORT, DESIGN_REVIEW) to ensure every generated file traces back to its origin. Output includes directory trees, dependency files, CI/CD configs, deployment topologies, test fixtures, code-level reasoning comments, and an Architecture Decision Record (ADR).

## VCMF Checkpoints

| Principle | Checkpoint in this Skill |
|-----------|--------------------------|
| Design as Contract | Every generated file must be traceable to PRD or Architecture artifacts |
| Interface as Boundary | Generated code signatures must match `INTERFACE_CONTRACT.md` |
| Reality as Baseline | Tests directory must include both mock tests and real-LLM tests with `skipif` mechanism |
| State as Responsibility | Generated state management code must match `StateModel` ownership in XML |

## When to Use

- The user has approved architecture design (and optional validation)
- You need to produce runnable project scaffolding
- Do NOT use if architecture has not been approved

## Precondition Check

Read `skill/artifacts/STATE.md`. Acceptable phases: `architecture_design_completed` or `architecture_validated`. If neither, stop and instruct the user to complete prior phases.

## Workflow

1. **Read all artifacts**
   - Load ALL historical artifacts:
     - `PRD.md` (requirements origin)
     - `STATE.md` (current phase + known pitfalls)
     - `DECISION_LOG.md` (reasoning chain)
     - `ARCHITECTURE.md` (design summary)
     - `architecture.xml` (strict schema + DecisionTrace)
     - `INTERFACE_CONTRACT.md` (I/O boundaries)
     - `VALIDATION_REPORT.md` (if present, technical validation results)
     - `DESIGN_REVIEW.md` (if present, issue list)

2. **Internal planning**
   - Create an implementation plan for the scaffolding work:
     - Which files to create
     - Which directories to set up
     - Which tests to generate
   - Keep the plan lightweight (a short bullet list is sufficient)

3. **Directory tree and dependencies**
   - Generate the project directory tree under `skill/artifacts/PROJECT_SCAFFOLD/`
   - Generate dependency config files (package.json, requirements.txt, pom.xml, Cargo.toml, etc.) based on the chosen tech stack

4. **Core code skeleton**
   - Generate core module files with class/function signatures that match `INTERFACE_CONTRACT.md`
   - Implement infrastructure code (routing, config loading, error handling)
   - Leave business logic as well-documented placeholders or minimal implementations

5. **Code reasoning comments**
   - Every core module MUST include a header comment linking it to architecture decisions:
     - Architecture Decision ID (from DECISION_LOG or XML DecisionTrace)
     - Reasoning: why this module exists, what PRD requirement it serves
     - Known Risk: any DESIGN_REVIEW issues that apply to this module
   - Every DESIGN_REVIEW issue marked "Must Fix" or "Should Fix" MUST be translated into an inline TODO with issue ID and priority

6. **Deployment topology**
   - Generate `docker-compose.yml` or basic Kubernetes manifests
   - Document containerization strategy in a short README inside the scaffold

7. **CI/CD pipeline**
   - Generate CI config (e.g., `.github/workflows/ci.yml` or `.gitlab-ci.yml`)
   - Must include: dependency install, lint, mock test execution, real test execution (with `continue-on-error` or skip logic so missing API keys do not fail the build)

8. **Environment configuration template**
   - Generate `.env.template` listing all required environment variables (API keys, base URLs, model names, database URLs)
   - Add a comment block at the top explaining that no secrets should be hard-coded

9. **Transparent test fixtures**
   - Organize tests into:
     - `tests/mock/` — mock-based unit and integration tests
     - `tests/real/` — real-LLM tests with `pytest.mark.skipif` (or equivalent)
     - `tests/end_to_end/` — end-to-end flow tests
   - Generate test code (Pytest, Jest, etc.)
   - Hard-code or file-ize the mock data from Phase 3 into fixtures
   - Add NFR verification scripts (k6 snippet, JMeter snippet, or security scan commands)
   - Inject strong logging: every assertion must log its inputs and outputs

10. **Documentation sync rules**
   - Generate `docs/sync-rules.md` mapping:
     - Code change type -> Documents to update
   - Example rows: `src/l*/` code changes -> `src/l*/tests/README.md` + `docs/*.xml`

11. **Architecture Decision Record (ADR)**
    - Generate `PROJECT_SCAFFOLD/docs/ADR.md`
    - Transform `DECISION_LOG.md` entries into human-readable ADR format:
      - Status: Accepted / Deprecated / Superseded
      - Context: What forces were at play
      - Decision: What was decided
      - Consequences: Positive and negative

12. **Decision Log and Changelog**
    - Append scaffolding decisions to `skill/artifacts/DECISION_LOG.md`
    - Generate `skill/artifacts/PROJECT_SCAFFOLD/CHANGELOG.md` with an initial entry

13. **Internal verification**
    - Verify that:
      - All generated file paths match the planned structure
      - All interface signatures in generated code match `INTERFACE_CONTRACT.md`
      - `.env.template` covers all external dependencies mentioned in architecture
      - CI config references existing test directories

14. **Traceability audit**
    - Randomly sample 3-5 generated files
    - For each file, answer:
      - What PRD requirement does this file trace back to?
      - What INTERFACE_CONTRACT entry does its signature trace back to?
      - Does its state management match the XML StateModel?
    - If any answer is untraceable, mark as traceability gap and append to STATE.md Known Pitfalls

15. **State update**
    - Update `STATE.md`:
      - Append to **Completed Steps**: `[YYYY-MM-DD HH:MM] sdlc-project-scaffolding: Generated PROJECT_SCAFFOLD with [N] files`
      - Update **Current State**: `phase: scaffolding_completed`, DIVE `Implement: completed`, `Verify: completed`, `Evolve: in_progress`

16. **Human gate**
    - Present a summary of generated files (bullet list)
    - Say exactly: "项目脚手架已生成，包含工程目录、CI/CD 配置、测试脚本、文档同步规则和环境变量模板。请确认当前阶段输出。回复 [APPROVE] 完成全流程，或提出修改意见。"
    - Do NOT mark complete without [APPROVE]

<HARD-GATE>
Do NOT mark the SDLC workflow as complete until the user replies [APPROVE].
</HARD-GATE>

## Output Specification

- `skill/artifacts/PROJECT_SCAFFOLD/` containing concrete, runnable files
- `skill/artifacts/PROJECT_SCAFFOLD/.env.template`
- `skill/artifacts/PROJECT_SCAFFOLD/docs/sync-rules.md`
- `skill/artifacts/PROJECT_SCAFFOLD/docs/ADR.md`
- `skill/artifacts/PROJECT_SCAFFOLD/CHANGELOG.md`
- Code reasoning comments in every core module header
- Inline TODOs for every DESIGN_REVIEW Must Fix / Should Fix issue
- No placeholder text or abstract suggestions allowed

## Red Flags

- Do NOT output vague advice like "you should add error handling"
- Do NOT skip the CI/CD config
- Do NOT proceed without the human gate
- Do NOT forget to inject logging into tests
- Do NOT generate hard-coded API keys or secrets in any file
- Do NOT create interface signatures that contradict `INTERFACE_CONTRACT.md`
