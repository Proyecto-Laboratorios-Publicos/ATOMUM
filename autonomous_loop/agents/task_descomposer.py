from __future__ import annotations

import json
import os
from typing import Any, Literal

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

from autonomous_loop.agents.planner import (
    AtomumGraphState,
    PlannerTask,
    route_after_planner,
)

AgentRole = Literal[
    "threat_intel",
    "vuln_analyst",
    "security_reviewer",
    "coder",
    "critic",
]


class AtomicAction(BaseModel):
    """Paso atómico y ejecutable derivado de una tarea del plan."""

    id: str = Field(..., description="Identificador único, ej. T1.1")
    parent_task_id: str = Field(..., description="ID de la PlannerTask de origen")
    agent: AgentRole = Field(..., description="Agente encargado de ejecutar la acción")
    action_type: Literal[
        "recon",
        "scan",
        "code_edit",
        "review",
        "verify",
    ] = Field(default="verify", description="Categoría técnica de ejecución")
    instruction: str = Field(..., description="Instrucción concreta y acotada")
    tool_hint: str | None = Field(
        default=None,
        description="Herramienta o módulo sugerido (ej. port_scanner, cve_feed, git_diff)",
    )
    status: Literal["pending", "in_progress", "completed", "failed"] = Field(
        default="pending"
    )


def _infer_action_type(task: PlannerTask) -> Literal["recon", "scan", "code_edit", "review", "verify"]:
    """Clasifica el tipo de acción técnica a partir del agente asignado y el título."""
    text = f"{task.title} {task.rationale}".lower()
    if task.assigned_agent == "threat_intel":
        return "recon"
    if task.assigned_agent == "vuln_analyst":
        return "scan"
    if task.assigned_agent == "coder":
        return "code_edit"
    if task.assigned_agent == "security_reviewer":
        return "review"
    if "escaneo" in text or "puerto" in text or "cve" in text:
        return "scan"
    return "verify"


def _fallback_decompose(
    tasks: list[PlannerTask], target: str | None
) -> list[AtomicAction]:
    """Descompone cada tarea en subpasos deterministas sin depender de un LLM."""
    actions: list[AtomicAction] = []
    target_suffix = f" sobre objetivo '{target}'" if target else ""

    for task in tasks:
        action_type = _infer_action_type(task)
        if action_type == "recon":
            actions.extend(
                [
                    AtomicAction(
                        id=f"{task.id}.1",
                        parent_task_id=task.id,
                        agent=task.assigned_agent,
                        action_type="recon",
                        instruction=f"Delimitar alcance y contexto operativo{target_suffix}.",
                        tool_hint="context_scope",
                    ),
                    AtomicAction(
                        id=f"{task.id}.2",
                        parent_task_id=task.id,
                        agent=task.assigned_agent,
                        action_type="recon",
                        instruction=f"Relevar vectores relevantes para: {task.title}.",
                        tool_hint="threat_feed",
                    ),
                ]
            )
        elif action_type == "scan":
            actions.extend(
                [
                    AtomicAction(
                        id=f"{task.id}.1",
                        parent_task_id=task.id,
                        agent=task.assigned_agent,
                        action_type="scan",
                        instruction=f"Verificar puertos/servicios activos y exposición{target_suffix}.",
                        tool_hint="port_scanner",
                    ),
                    AtomicAction(
                        id=f"{task.id}.2",
                        parent_task_id=task.id,
                        agent=task.assigned_agent,
                        action_type="scan",
                        instruction="Cruzar hallazgos detectados con referencias CPE/CVE.",
                        tool_hint="cve_lookup",
                    ),
                ]
            )
        elif action_type == "code_edit":
            actions.extend(
                [
                    AtomicAction(
                        id=f"{task.id}.1",
                        parent_task_id=task.id,
                        agent=task.assigned_agent,
                        action_type="code_edit",
                        instruction=f"Diseñar cambio modular para: {task.title}.",
                        tool_hint="repo_inspect",
                    ),
                    AtomicAction(
                        id=f"{task.id}.2",
                        parent_task_id=task.id,
                        agent=task.assigned_agent,
                        action_type="code_edit",
                        instruction="Generar parche o pull request mínimo y comprobable.",
                        tool_hint="patch_builder",
                    ),
                ]
            )
        else:
            actions.extend(
                [
                    AtomicAction(
                        id=f"{task.id}.1",
                        parent_task_id=task.id,
                        agent=task.assigned_agent,
                        action_type=action_type,
                        instruction=f"Auditar riesgos y efectos colaterales de: {task.title}.",
                        tool_hint="risk_check",
                    ),
                    AtomicAction(
                        id=f"{task.id}.2",
                        parent_task_id=task.id,
                        agent=task.assigned_agent,
                        action_type="verify",
                        instruction="Emitir dictamen de validación y criterios de cierre.",
                        tool_hint="gate_check",
                    ),
                ]
            )

    return actions


def _llm_decompose(
    tasks: list[PlannerTask], target: str | None
) -> list[AtomicAction] | None:
    """Usa Groq para descomponer tareas en acciones atómicas si hay API key."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key or not tasks:
        return None

    try:
        from groq import Groq  # type: ignore

        client = Groq(api_key=api_key)
        model = os.getenv("GROQ_DECOMPOSER_MODEL", "openai/gpt-oss-120b")
        system_prompt = (
            "Eres el Task Decomposer de ATOMUM. Recibes una lista de tareas y un target opcional. "
            "Devuelve ÚNICAMENTE un JSON válido con la clave 'actions' (lista de objetos). "
            "Cada objeto debe incluir: 'id', 'parent_task_id', "
            "'agent' (threat_intel, vuln_analyst, security_reviewer, coder, critic), "
            "'action_type' (recon, scan, code_edit, review, verify), "
            "'instruction' (breve y accionable) y 'tool_hint' (string o null)."
        )
        payload = json.dumps(
            {
                "target": target,
                "tasks": [t.model_dump() for t in tasks],
            },
            ensure_ascii=False,
        )

        completion = client.chat.completions.create(
            model=model,
            temperature=0.2,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": payload},
            ],
        )
        raw_content = completion.choices[0].message.content or "{}"
        parsed = json.loads(raw_content)
        raw_actions = parsed.get("actions", [])
        if not isinstance(raw_actions, list) or not raw_actions:
            return None

        return [AtomicAction.model_validate(item) for item in raw_actions]
    except Exception:
        return None


def task_decomposer_node(state: AtomumGraphState) -> dict[str, Any]:
    """Nodo de LangGraph que transforma `state.plan` en acciones atómicas."""
    if not state.plan:
        return {
            "errors": [
                *state.errors,
                "Task Decomposer recibió un plan vacío; no hay tareas que descomponer.",
            ],
            "next_agent": None,
        }

    actions = _llm_decompose(state.plan, state.target)
    source = "groq_llm"
    if not actions:
        actions = _fallback_decompose(state.plan, state.target)
        source = "deterministic_fallback"

    first_action = actions[0] if actions else None
    decomposed_payload = [a.model_dump() for a in actions]

    finding_entry = {
        "agent": "task_decomposer",
        "source": source,
        "input_tasks": len(state.plan),
        "atomic_actions_created": len(actions),
        "first_action_id": first_action.id if first_action else None,
        "atomic_actions": decomposed_payload,
    }

    return {
        "next_agent": first_action.agent if first_action else state.next_agent,
        "findings": [*state.findings, finding_entry],
        "iteration": state.iteration + 1,
    }


def build_decomposer_graph():
    """Compila un grafo de prueba conectando `planner` -> `task_decomposer` -> agente."""
    graph = StateGraph(AtomumGraphState)
    graph.add_node("task_decomposer", task_decomposer_node)

    for agent_name in (
        "threat_intel",
        "vuln_analyst",
        "security_reviewer",
        "coder",
        "critic",
    ):
        graph.add_node(
            agent_name,
            lambda s, name=agent_name: {
                "findings": [
                    *s.findings,
                    {"agent": name, "status": "placeholder_ready"},
                ]
            },
        )
        graph.add_edge(agent_name, END)

    graph.add_edge(START, "task_decomposer")
    graph.add_conditional_edges(
        "task_decomposer",
        route_after_planner,
        {
            "threat_intel": "threat_intel",
            "vuln_analyst": "vuln_analyst",
            "security_reviewer": "security_reviewer",
            "coder": "coder",
            "critic": "critic",
            END: END,
        },
    )
    return graph.compile()


if __name__ == "__main__":
    sample_plan = [
        PlannerTask(
            id="T1",
            title="Análisis de superficie expuesta",
            assigned_agent="threat_intel",
            rationale="Identificar contexto y alcance inicial.",
        ),
        PlannerTask(
            id="T2",
            title="Escaneo de puertos y vulnerabilidades",
            assigned_agent="vuln_analyst",
            rationale="Detectar servicios expuestos y posibles CVEs.",
        ),
    ]
    state = AtomumGraphState(
        directive="Auditar exposición de puertos y preparar mitigaciones",
        target="192.168.1.10",
        plan=sample_plan,
        next_agent="threat_intel",
    )
    app_graph = build_decomposer_graph()
    out = app_graph.invoke(state)
    print(
        json.dumps(
            out,
            indent=2,
            default=lambda o: o.model_dump() if hasattr(o, "model_dump") else str(o),
            ensure_ascii=False,
        )
    )
