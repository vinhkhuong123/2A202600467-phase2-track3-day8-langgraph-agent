"""Node skeletons for the LangGraph workflow.

Each function should be small, testable, and return a partial state update. Avoid mutating the
input state in place.
"""

from __future__ import annotations

from .state import AgentState, ApprovalDecision, Route, make_event


def intake_node(state: AgentState) -> dict:
    """Normalize raw query into state fields."""
    query = state.get("query", "").strip()
    normalized_query = query.lower()
    
    # Mock PII check
    has_pii = "@" in normalized_query or sum(c.isdigit() for c in normalized_query) >= 7
    metadata = {"has_pii": has_pii, "length": len(query)}

    return {
        "query": query,
        "messages": [f"intake:{query[:40]}"],
        "events": [make_event("intake", "completed", "query normalized", **metadata)],
    }


def classify_node(state: AgentState) -> dict:
    """Classify the query into a route."""
    query = state.get("query", "").lower()
    words = query.split()
    clean_words = [w.strip("?!.,;:") for w in words]
    
    route = Route.SIMPLE
    risk_level = "low"
    
    risky_keywords = ["refund", "delete", "send", "cancel", "remove", "revoke", "hoàn tiền", "xóa", "xoá"]
    tool_keywords = ["status", "order", "lookup", "check", "track", "find", "search", "đơn hàng", "tình trạng"]
    error_keywords = ["timeout", "fail", "error", "crash", "unavailable", "lỗi"]
    
    if any(kw in query for kw in risky_keywords):
        route = Route.RISKY
        risk_level = "high"
    elif any(kw in query for kw in tool_keywords):
        route = Route.TOOL
    elif len(clean_words) < 5 and any(pr in clean_words for pr in ["it", "this", "that"]):
        route = Route.MISSING_INFO
    elif any(kw in query for kw in error_keywords):
        route = Route.ERROR

    return {
        "route": route.value,
        "risk_level": risk_level,
        "events": [make_event("classify", "completed", f"route={route.value}")],
    }


def ask_clarification_node(state: AgentState) -> dict:
    """Ask for missing information instead of hallucinating."""
    query = state.get("query", "")
    question = f"Could you provide more specific details regarding your request: '{query}'?"
    return {
        "pending_question": question,
        "final_answer": question,
        "events": [make_event("clarify", "completed", "missing information requested")],
    }


def tool_node(state: AgentState) -> dict:
    """Call a mock tool."""
    attempt = int(state.get("attempt", 0))
    scenario_id = state.get("scenario_id", "unknown")
    
    # Idempotent execution log
    action_log = f"[idempotency_key:{scenario_id}_{attempt}]"
    
    if state.get("route") == Route.ERROR.value and attempt < 2:
        result = f"ERROR: transient failure attempt={attempt} scenario={scenario_id} {action_log}"
    else:
        result = f"mock-tool-result for scenario={scenario_id} {action_log}"
        
    return {
        "tool_results": [result],
        "events": [make_event("tool", "completed", f"tool executed attempt={attempt}")],
    }


def risky_action_node(state: AgentState) -> dict:
    """Prepare a risky action for approval."""
    query = state.get("query", "")
    action = "Execute sensitive external action"
    if "refund" in query.lower() or "hoàn tiền" in query.lower():
        action = "Issue refund to customer"
    elif "delete" in query.lower() or "remove" in query.lower() or "xóa" in query.lower() or "xoá" in query.lower():
        action = "Delete customer account or data"
        
    proposed_action = f"{action} (Evidence: query='{query}', risk_level='high')"
    return {
        "proposed_action": proposed_action,
        "events": [make_event("risky_action", "pending_approval", "approval required")],
    }


def approval_node(state: AgentState) -> dict:
    """Human approval step with optional LangGraph interrupt()."""
    import os

    if os.getenv("LANGGRAPH_INTERRUPT", "").lower() == "true":
        from langgraph.types import interrupt

        value = interrupt({
            "proposed_action": state.get("proposed_action"),
            "risk_level": state.get("risk_level"),
        })
        if isinstance(value, dict):
            decision = ApprovalDecision(**value)
        else:
            decision = ApprovalDecision(approved=bool(value))
    else:
        # Mock approval
        decision = ApprovalDecision(approved=True, comment="mock approval for lab")

    final_answer = None
    if not decision.approved:
        final_answer = f"Action was rejected by reviewer: {decision.comment or 'No comment provided'}"

    updates: dict = {
        "approval": decision.model_dump(),
        "events": [make_event("approval", "completed", f"approved={decision.approved}", timeout_escalated=False)],
    }
    if final_answer:
        updates["final_answer"] = final_answer
        
    return updates


def retry_or_fallback_node(state: AgentState) -> dict:
    """Record a retry attempt or fallback decision."""
    attempt = int(state.get("attempt", 0)) + 1
    max_attempts = int(state.get("max_attempts", 3))
    
    # Optional backoff calculation
    backoff_ms = (2 ** attempt) * 100
    
    errors = state.get("errors", []) + [f"transient failure attempt={attempt}"]
    return {
        "attempt": attempt,
        "errors": errors,
        "events": [make_event("retry", "completed", "retry attempt recorded", attempt=attempt, backoff_ms=backoff_ms, max_attempts=max_attempts)],
    }


def answer_node(state: AgentState) -> dict:
    """Produce a final response."""
    route = state.get("route")
    approval = state.get("approval") or {}
    
    # Ground the answer based on context
    if route == Route.RISKY.value:
        if approval.get("approved"):
            answer = f"Your requested action has been approved and executed. Details: {state.get('tool_results', [''])[0]}"
        else:
            answer = f"Your requested action was rejected. Reason: {approval.get('comment', '')}"
    elif state.get("tool_results"):
        answer = f"I found the following information: {state['tool_results'][-1]}"
    else:
        answer = "I have processed your request based on the provided details."

    return {
        "final_answer": answer,
        "events": [make_event("answer", "completed", "answer generated")],
    }


def evaluate_node(state: AgentState) -> dict:
    """Evaluate tool results — the 'done?' check that enables retry loops."""
    tool_results = state.get("tool_results", [])
    latest = tool_results[-1] if tool_results else ""
    
    # Structured validation mock
    if "ERROR" in latest:
        return {
            "evaluation_result": "needs_retry",
            "events": [make_event("evaluate", "completed", "tool result indicates failure, retry needed")],
        }
    return {
        "evaluation_result": "success",
        "events": [make_event("evaluate", "completed", "tool result satisfactory")],
    }


def dead_letter_node(state: AgentState) -> dict:
    """Log unresolvable failures for manual review."""
    attempt = state.get("attempt", 0)
    scenario_id = state.get("scenario_id", "unknown")
    
    final_answer = (
        f"Request could not be completed after maximum retry attempts ({attempt}). "
        f"Scenario {scenario_id} has been logged to the dead-letter queue for manual review."
    )
    
    return {
        "final_answer": final_answer,
        "events": [make_event("dead_letter", "completed", f"max retries exceeded, attempt={attempt}")],
    }


def finalize_node(state: AgentState) -> dict:
    """Finalize the run and emit a final audit event."""
    return {"events": [make_event("finalize", "completed", "workflow finished")]}
