from __future__ import annotations

import json
from typing import Any

from langgraph.graph import END, START, StateGraph

from autonomous_loop.agents.coding_agent import coding_agent_node
from autonomous_loop.agents.critic import critic_node
from autonomous_loop.agents.planner import (
    AtomumGraphState,
    PlannerTask,
    planner_node,
    route_after_planner,
)
from autonomous_loop.agents.report_agent import report_agent_node
from autonomous_loop.agents.security_reviewer import security_reviewer_node
from autonomous_loop.agents.task_descomposer import task_decomposer_node
from autonomous_loop.agents.threat_Intel import threat_intel_node
from autonomous_loop.agents.vulnerability_analyst import vulnerability_analyst_node

DEFAULT_MAX_ITERATIONS = 12

AGENT_ROUTES: dict[str, str] = {
    "planner": "planner",
    "task_decomposer": "task_decomposer",
    "threat_intel": "threat_intel",
    "vuln_analyst": "vuln_analyst",
    "security_reviewer": "security_reviewer",
    "coder": "coder",
    "critic": "critic",
    "report_agent": "report_agent",
}


def _guarded_route(state: AtomumGraphState) -> str:
    """Enruta al siguiente agente respetando el límite de iteraciones y el estado del grafo."""
    if state.iteration >= DEFAULT_MAX_ITERATIONS:
        return END
    return route_after_planner(state)


def build_atomum_graph():
    """Ensambla y compila el grafo multiagente principal de ATOMUM."""
    graph = StateGraph(AtomumGraphState)

    graph.add_node("planner", planner_node)
    graph.add_node("task_decomposer", task_decomposer_node)
    graph.add_node("threat_intel", threat_intel_node)
    graph.add_node("vuln_analyst", vulnerability_analyst_node)
    graph.add_node("security_reviewer", security_reviewer_node)
    graph.add_node("coder", coding_agent_node)
    graph.add_node("critic", critic_node)
    graph.add_node("report_agent", report_agent_node)

    graph.add_edge(START, "planner")

    branch_map: dict[str, Any] = {**AGENT_ROUTES, END: END}
    for node_name in AGENT_ROUTES:
        graph.add_conditional_edges(node_name, _guarded_route, branch_map)

    return graph.compile()


def run_atomum_cycle(
    directive: str,
    target: str | None = None,
    plan: list[PlannerTask] | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Ejecuta un ciclo completo del grafo de extremo a extremo."""
    app = build_atomum_graph()
    initial_state = AtomumGraphState(
        directive=directive,
        target=target,
        plan=plan or [],
        next_agent="planner",
    )
    return app.invoke(initial_state, config=config or {})


if __name__ == "__main__":
    result = run_atomum_cycle(
        directive="Auditar exposición, proponer endurecimiento y generar informe final",
        target="192.168.1.50",
    )
    print(
        json.dumps(
            result,
            indent=2,
            default=lambda o: o.model_dump() if hasattr(o, "model_dump") else str(o),
            ensure_ascii=False,
        )
    )
