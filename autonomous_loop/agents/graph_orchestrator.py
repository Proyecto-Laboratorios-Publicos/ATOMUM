from __future__ import annotations

import json
from typing import Any

from langgraph.checkpoint.memory import MemorySaver
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
from autonomous_loop.agents.vulnerability_analyst import vuln_analyst_node

DEFAULT_MAX_ITERATIONS = 12
DEFAULT_THREAD_ID = "atomum-default-thread"

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


def _normalize_config(config: dict[str, Any] | None) -> dict[str, Any]:
    """Garantiza que `configurable.thread_id` exista para el checkpointer."""
    normalized: dict[str, Any] = dict(config) if config else {}
    configurable = dict(normalized.get("configurable") or {})
    configurable.setdefault("thread_id", DEFAULT_THREAD_ID)
    normalized["configurable"] = configurable
    return normalized


def build_atomum_graph(checkpointer: Any | None = None):
    """Ensambla y compila el grafo multiagente principal de ATOMUM con memoria persistente."""
    graph = StateGraph(AtomumGraphState)

    graph.add_node("planner", planner_node)
    graph.add_node("task_decomposer", task_decomposer_node)
    graph.add_node("threat_intel", threat_intel_node)
    graph.add_node("vuln_analyst", vuln_analyst_node)
    graph.add_node("security_reviewer", security_reviewer_node)
    graph.add_node("coder", coding_agent_node)
    graph.add_node("critic", critic_node)
    graph.add_node("report_agent", report_agent_node)

    graph.add_edge(START, "planner")

    branch_map: dict[str, Any] = {**AGENT_ROUTES, END: END}
    for node_name in AGENT_ROUTES:
        graph.add_conditional_edges(node_name, _guarded_route, branch_map)

    effective_checkpointer = checkpointer if checkpointer is not None else MemorySaver()
    return graph.compile(checkpointer=effective_checkpointer)


def run_atomum_cycle(
    directive: str,
    target: str | None = None,
    plan: list[PlannerTask] | None = None,
    config: dict[str, Any] | None = None,
    checkpointer: Any | None = None,
) -> dict[str, Any]:
    """Ejecuta un ciclo completo del grafo de extremo a extremo con checkpointer."""
    app = build_atomum_graph(checkpointer=checkpointer)
    effective_config = _normalize_config(config)
    initial_state = AtomumGraphState(
        directive=directive,
        target=target,
        plan=plan or [],
        next_agent="planner",
    )
    return app.invoke(initial_state, config=effective_config)


if __name__ == "__main__":
    result = run_atomum_cycle(
        directive="Auditar exposición, proponer endurecimiento y generar informe final",
        target="192.168.1.50",
        config={"configurable": {"thread_id": "e2e-192-168-1-50"}},
    )
    print(
        json.dumps(
            result,
            indent=2,
            default=lambda o: o.model_dump() if hasattr(o, "model_dump") else str(o),
            ensure_ascii=False,
        )
    )
