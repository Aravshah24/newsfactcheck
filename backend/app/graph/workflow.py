from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, START, StateGraph


class ClaimState(TypedDict):
    claim_text: str
    evidence: list[str]
    verdict: str


def claim_analyzer(state: ClaimState) -> ClaimState:
    """Placeholder for the claim-analysis stage.

    This intentionally does not implement agents or retrieval logic yet.
    """
    state["verdict"] = "pending_review"
    return state


def build_graph():
    """Create a placeholder LangGraph workflow for the future verification pipeline."""
    workflow = StateGraph(ClaimState)
    workflow.add_node("claim_analyzer", claim_analyzer)
    workflow.add_edge(START, "claim_analyzer")
    workflow.add_edge("claim_analyzer", END)
    return workflow.compile()
