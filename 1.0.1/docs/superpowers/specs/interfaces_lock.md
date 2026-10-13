# Core Interface Lock Decisions

## Date: 2026-04-22

## Decision 1: RuntimeInterface.run_command

- **XML requires:** `run_command(command, timeout)` as SecondaryMethod
- **Code had:** Only `run_code(language, code, timeout, environment_config)`
- **Locked to:** Added `run_command`. `run_code` stays as PrimaryMethod.
- **Rationale:** L5 terminal tool needs shell command execution without wrapping in code.

## Decision 2: MemoryInterface.delete parameter

- **XML requires:** `delete(document_id: str)`
- **Code has:** `delete(document_ids: List[str])` (batch delete)
- **Locked to:** Keep `List[str]` — batch delete is intentional and more efficient.
- **Action:** XML spec will be updated to match code (batch is the real contract).

## Decision 3: ExecutionResult.resource_usage

- **XML requires:** `memory_peak`, `cpu_time` populated
- **Code has:** Empty `{}`
- **Locked to:** Populate from Docker container stats API (Phase 1.6).
- **Fields:** `{"memory_peak_mb": float, "cpu_time_ms": float}`

## Decision 4: L2.process_event return type

- **XML implies:** L2 orchestrates L3→L5 loop and returns final response
- **Code has:** Returns `L3Input`
- **Locked to:** Change return type to `str` (final response) in Phase 1.1.
