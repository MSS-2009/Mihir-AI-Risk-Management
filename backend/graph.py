"""The agent graph.

CP1 spine (preserved from the monolith):
    intake -> modeling -> interpretation

Later checkpoints extend this to
    intake -> document -> modeling -> correlation -> interpretation
           -> recommendation -> delivery
"""
from langgraph.graph import END, StateGraph

from agents.intake import intake_node
from agents.interpretation import interpretation_node
from agents.modeling import modeling_node
from agents.state import RiskState


def build_graph():
    b = StateGraph(RiskState)
    b.add_node("intake", intake_node)
    b.add_node("modeling", modeling_node)
    b.add_node("interpretation", interpretation_node)
    b.set_entry_point("intake")
    b.add_edge("intake", "modeling")
    b.add_edge("modeling", "interpretation")
    b.add_edge("interpretation", END)
    return b.compile()


GRAPH = build_graph()
