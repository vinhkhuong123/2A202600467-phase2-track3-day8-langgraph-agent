"""Routing functions for conditional edges."""

from __future__ import annotations

from .state import AgentState, Route


def route_after_classify(state: AgentState) -> str:
    """Map classified route to the next graph node."""
    route = state.get("route", Route.SIMPLE.value)
    mapping = {
        Route.SIMPLE.value: "answer",
        Route.TOOL.value: "tool",
        Route.MISSING_INFO.value: "clarify",
        Route.RISKY.value: "risky_action",
        Route.ERROR.value: "retry",
    }
    # Fallback to 'answer' if route is unknown
    if route not in mapping:
        print(f"Warning: Unknown route '{route}'. Falling back to 'answer'.")
    return mapping.get(route, "answer")


def route_after_retry(state: AgentState) -> str:
    """Decide whether to retry, fallback, or dead-letter."""
    attempt = int(state.get("attempt", 0))
    max_attempts = int(state.get("max_attempts", 3))
    
    # Bounded retry: if we reached max attempts, go to dead_letter
    if attempt >= max_attempts:
        return "dead_letter"
    return "tool"


def route_after_evaluate(state: AgentState) -> str:
    """Decide whether tool result is satisfactory or needs retry."""
    # Structured validation result check
    if state.get("evaluation_result") == "needs_retry":
        return "retry"
    return "answer"


def route_after_approval(state: AgentState) -> str:
    """Continue only if approved."""
    approval = state.get("approval") or {}
    # Support reject outcome: route to clarify
    return "tool" if approval.get("approved") else "clarify"
