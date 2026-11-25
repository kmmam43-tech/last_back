from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from .agents_service import LearningMaterialAgents
from .models import MaterialAnalysis, MaterialRequest, ReviewResult, VariantBundle


class WorkflowState(TypedDict, total=False):
    request: MaterialRequest
    analysis: MaterialAnalysis
    bundle: VariantBundle
    reviews: list[ReviewResult]


def build_workflow(agents: LearningMaterialAgents):
    async def analyze(state: WorkflowState):
        return {"analysis": await agents.analyze(state["request"])}

    async def differentiate(state: WorkflowState):
        return {"bundle": await agents.generate(state["request"], state["analysis"])}

    async def review(state: WorkflowState):
        return {
            "reviews": await agents.review_all(
                state["request"], state["analysis"], state["bundle"]
            )
        }

    return (
        StateGraph(WorkflowState)
        .add_node("analyze", analyze)
        .add_node("differentiate", differentiate)
        .add_node("review", review)
        .add_edge(START, "analyze")
        .add_edge("analyze", "differentiate")
        .add_edge("differentiate", "review")
        .add_edge("review", END)
        .compile()
    )

