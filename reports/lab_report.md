# Day 08 Lab Report

## 1. Team / student

- Name: 2A202600467 - Khương Quang Vinh
- Repo/commit: local
- Date: 2026-05-11

## 2. Architecture

- Nodes: intake, classify, clarify, tool, risky_action, approval, retry, answer, evaluate, dead_letter, finalize.
- Edges: conditional routing based on `route` variable, evaluating tool results for retry loops, and requiring approval for risky actions.

## 3. State schema

| Field | Reducer | Why |
|---|---|---|
| messages | append | audit conversation/events |
| events | append | track all actions for grading |
| errors | append | track transient and permanent errors |
| route | overwrite | current route only |
| attempt | overwrite | track retry counts |

## 4. Scenario results

- Total scenarios: 7
- Success rate: 100.00%
- Average nodes visited: 6.43
- Total retries: 3
- Total interrupts: 2

| Scenario | Expected route | Actual route | Success | Retries | Interrupts |
|---|---|---|---:|---:|---:|
| S01_simple | simple | simple | True | 0 | 0 |
| S02_tool | tool | tool | True | 0 | 0 |
| S03_missing | missing_info | missing_info | True | 0 | 0 |
| S04_risky | risky | risky | True | 0 | 1 |
| S05_error | error | error | True | 2 | 0 |
| S06_delete | risky | risky | True | 0 | 1 |
| S07_dead_letter | error | error | True | 1 | 0 |

## 5. Failure analysis

1. **Retry or tool failure:** Managed by bounded `attempt` counting and tracking `max_attempts`. If limit is reached, query is sent to `dead_letter`.
2. **Risky action without approval:** Handled by routing risky requests strictly to `risky_action` then `approval` before executing `tool`.

## 6. Persistence / recovery evidence

Used `MemorySaver` by default for fast iteration and implemented `SqliteSaver` using `sqlite3.connect` to ensure checkpoints survive process restart.

## 7. Extension work

N/A

## 8. Improvement plan

- Implement LLM-as-judge in `evaluate_node`.
- Connect to an actual ticketing API.
