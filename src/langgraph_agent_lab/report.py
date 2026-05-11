"""Report generation helper."""

from __future__ import annotations

from pathlib import Path

from .metrics import MetricsReport


def render_report_stub(metrics: MetricsReport) -> str:
    """Return a richer report based on the template."""
    import datetime
    
    table_rows = []
    for item in metrics.scenario_metrics:
        table_rows.append(
            f"| {item.scenario_id} | {item.expected_route} | {item.actual_route} | "
            f"{item.success} | {item.retry_count} | {item.interrupt_count} |"
        )
    
    scenario_table = "\n".join(table_rows)

    return f"""# Day 08 Lab Report

## 1. Team / student

- Name: Student
- Repo/commit: local
- Date: {datetime.date.today().isoformat()}

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

- Total scenarios: {metrics.total_scenarios}
- Success rate: {metrics.success_rate:.2%}
- Average nodes visited: {metrics.avg_nodes_visited:.2f}
- Total retries: {metrics.total_retries}
- Total interrupts: {metrics.total_interrupts}

| Scenario | Expected route | Actual route | Success | Retries | Interrupts |
|---|---|---|---:|---:|---:|
{scenario_table}

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
"""


def write_report(metrics: MetricsReport, output_path: str | Path) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_report_stub(metrics), encoding="utf-8")
