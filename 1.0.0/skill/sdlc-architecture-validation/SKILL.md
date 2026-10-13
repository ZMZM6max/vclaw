---
name: sdlc-architecture-validation
description: Use when a system architecture XML and interface contracts have been approved and the user wants to validate them through LLM-based sandbox simulation with mock data
---

# SDLC Architecture Validation

## Overview

Perform technical validation of an approved architecture XML: consistency checks, mock data flow simulation, topology connectivity verification. This skill focuses on "does the architecture document hang together technically?" For adversarial design inspection, use `sdlc-design-review` instead.

## VCMF Checkpoints

| Principle | Checkpoint in this Skill |
|-----------|--------------------------|
| Design as Contract | Verify that XML modules map back to PRD requirements |
| Interface as Boundary | Verify that every `Coupling` in XML matches `INTERFACE_CONTRACT.md` |
| Reality as Baseline | Run real-LLM validation on semantic-sensitive points (security judgment, format constraint, error translation, tool selection); degrade to mock+consistency if no API key |
| State as Responsibility | Verify that `StateModel` lifecycle definitions are internally consistent |

## When to Use

- The user has approved an architecture XML and wants virtual validation
- Do NOT use if the architecture XML has not been approved

## Precondition Check

Read `skill/artifacts/STATE.md`. If `phase` is not `architecture_design_completed` or `architecture.xml` is missing, stop and instruct the user to run `sdlc-architecture-design` first.

## Workflow

1. **API readiness check**
   - Ask the user for API Key and Base URL if not already configured
   - If the user declines or has no API access, state clearly that real-LLM validation is skipped and this phase will run mock validation + consistency checks only

2. **Consistency check: XML vs Interface Contract**
   - Compare every `Module/Interface` in `architecture.xml` against `INTERFACE_CONTRACT.md`
   - Flag any mismatch in input/output schema or missing error codes

3. **Consistency check: XML vs PRD**
   - Verify that every module in XML can be traced to a requirement or user story in `PRD.md`
   - Flag any orphaned modules

4. **Mock injection (flow validation)**
   - Load the mock data defined in `ARCHITECTURE.md`
   - Use the mock data as the trigger source for simulation

5. **Module-by-module simulation**
   - For each `Module` in `architecture.xml`:
     - Simulate receiving the upstream output
     - Verify `Security` requirements (auth/encryption)
     - Verify `Coupling` dependencies exist and are reachable
     - Verify output schema matches the next module's input schema

6. **Real-LLM validation (minimal coverage)**
   - If API key is available, run real LLM calls on a minimal coverage set focused on format/schema compliance only:
     - Does the LLM output match the expected XML schema when prompted?
     - Does the LLM correctly parse and return the mock data structure?
   - If API key is unavailable, skip this step and note it in the report
   - Note: Security judgment, error translation, and tool selection validation are performed by `sdlc-design-review`

7. **Trace logging**
   - Print the simulation trace in this format:
     ```
     [API Response] -> [Case ID] -> Inject Mock -> [Module A] Receive -> [Auth: Valid] -> Simulate Logic -> [Data Contract: PASS] -> Route to [Module B] ... -> Final Result
     ```

8. **Self-healing loop**
   - If any validation fails:
     - Document the failure in the report
     - Tell the user: "架构校验未通过。请回复 [RETRY] 退回架构设计阶段修改 XML，或提出修改意见。"
     - Do NOT proceed to scaffolding
   - If all pass:
     - Write `skill/artifacts/VALIDATION_REPORT.md` with full trace and pass summary

9. **Health-check script generation**
   - Generate `skill/artifacts/health-check.sh` that checks:
     - XML well-formedness
     - All `Coupling` targets exist as `Module` names
     - All `StateModel` entries have required attributes
   - The script should be runnable in a Unix shell

10. **State update**
    - Update `STATE.md`: `phase: architecture_validated`
    - Set DIVE `Verify: completed`

11. **Human gate**
    - Present validation summary
    - Say exactly: "架构验证报告和健康检查脚本已生成。请确认当前阶段输出。回复 [APPROVE] 进入项目脚手架阶段，或提出修改意见。"
    - Do NOT proceed until [APPROVE]

<HARD-GATE>
Do NOT proceed to project-scaffolding if validation failed. If validation passed, do NOT proceed until the user replies [APPROVE].
</HARD-GATE>

## Output Specification

- `skill/artifacts/VALIDATION_REPORT.md`
- `skill/artifacts/health-check.sh`
- Must include the full simulation trace
- Must clearly state PASS or FAIL per module
- Must note whether real-LLM validation was run or skipped

## Red Flags

- Do NOT skip validation failures
- Do NOT proceed to scaffolding if validation failed
- Do NOT hallucinate API responses; explicitly state what is simulated vs real
- Do NOT generate an empty or placeholder health-check script
- Do NOT perform adversarial design inspection; delegate that to `sdlc-design-review`
