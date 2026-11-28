from __future__ import annotations

import json
import os
from typing import Any, Literal

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field


class PlannerTask(BaseModel):
    """Representa una subtarea concreta derivada de la directiva principal."""

    id: str = Field(..., description="Identificador único de la tarea, ej. T1")
    title: str = Field(..., description="Título breve de la tarea")
    assigned_agent: Literal[
        "threat_intel",
        "vuln_analyst",
        "security_reviewer",
        "coder",
        "critic",
        "report_agent",
    ] = Field(..., description="Agente especialista al que se delega la tarea")
    rationale: str = Field(..., description="Motivo por el cual se requiere este paso")
    status: Literal["pending", "in_progress", "completed", "skipped"] = Field(
        default="pending"
    )


class AtomumGraphState(BaseModel):
    """Estado compartido que fluye entre los nodos del grafo en LangGraph."""

    directive: str = Field(..., description="Instrucción o objetivo inicial del usuario")
    target: str | None = Field(
        default=None,
        description="Objetivo técnico opcional (host, IP, rango, repo o módulo)",
    )
    plan: list[PlannerTask] = Field(
        default_factory=list,
        description="Lista ordenada de tareas generadas por el Planner",
    )
    next_agent: str | None = Field(
        default=None,
        description="Próximo agente sugerido para ejecutar el siguiente paso",
    )
    findings: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Hallazgos acumulados por los agentes especializados",
    )
    errors: list[str] = Field(
        default_factory=list,
        description="Registro de errores no fatales o advertencias de ejecución",
    )
    iteration: int = Field(default=0, description="Contador de ciclos de ejecución")


def _fallback_plan(directive: str, target: str | None) -> list[PlannerTask]:
    """Genera un plan determinista si no hay LLM configurado o falla la respuesta."""
    lowered = directive.lower()
    tasks: list[PlannerTask] = [
        PlannerTask(
            id="T1",
            title="Análisis inicial de contexto y superficie",
            assigned_agent="threat_intel",
            rationale=f"Evaluar alcance y contexto para: {target or directive[:60]}",
        )
    ]

    if any(k in lowered for k in ("puerto", "port", "scan", "red", "escaneo", "cve", "vuln")):
        tasks.append(
            PlannerTask(
                id="T2",
                title="Detección de servicios y evaluación de vulnerabilidades",
                assigned_agent="vuln_analyst",
                rationale="Identificar servicios expuestos y posibles puntos de exposición.",
            )
        )

    if any(k in lowered for k in ("código", "codigo", "refactor", "bug", "test", "agente", "pr")):
        tasks.append(
            PlannerTask(
                id=f"T{len(tasks) + 1}",
                title="Propuesta de implementación o corrección",
                assigned_agent="coder",
                rationale="Generar cambios modulares alineados con el objetivo.",
            )
        )

    tasks.append(
        PlannerTask(
            id=f"T{len(tasks) + 1}",
            title="Revisión de seguridad y validación técnica",
            assigned_agent="critic",
            rationale="Verificar riesgos, regresiones y coherencia antes de cerrar el ciclo.",
        )
    )

    tasks.append(
        PlannerTask(
            id=f"T{len(tasks) + 1}",
            title="Generación de informe final consolidado",
            assigned_agent="report_agent",
            rationale="Consolidar hallazgos, evaluación crítica y recomendaciones finales.",
        )
    )
    return tasks


def _llm_plan(directive: str, target: str | None) -> list[PlannerTask] | None:
    """Intenta generar el plan usando Groq si GROQ_API_KEY está disponible."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return None

    try:
        from groq import Groq  # type: ignore

        client = Groq(api_key=api_key)
        model = os.getenv("GROQ_PLANNER_MODEL", "openai/gpt-oss-120b")
        system_prompt = (
            "Eres el Planner de ATOMUM. Devuelve ÚNICAMENTE un JSON válido con una lista "
            "'tasks'. Cada elemento debe tener: 'id' (string), 'title' (string), "
            "'assigned_agent' (uno de: threat_intel, vuln_analyst, security_reviewer, coder, critic, report_agent) "
            "y 'rationale' (string). Incluye siempre una tarea final asignada a 'report_agent'."
        )
        user_payload = json.dumps(
            {"directive": directive, "target": target}, ensure_ascii=False
        )

        completion = client.chat.completions.create(
            model=model,
            temperature=0.2,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_payload},
            ],
        )
        raw_content = completion.choices[0].message.content or "{}"
        parsed = json.loads(raw_content)
        raw_tasks = parsed.get("tasks", [])
        if not isinstance(raw_tasks, list) or not raw_tasks:
            return None

        tasks = [PlannerTask.model_validate(item) for item in raw_tasks]
        if not any(t.assigned_agent == "report_agent" for t in tasks):
            tasks.append(
                PlannerTask(
                    id=f"T{len(tasks) + 1}",
                    title="Generación de informe final consolidado",
                    assigned_agent="report_agent",
                    rationale="Consolidar hallazgos, evaluación crítica y recomendaciones finales.",
                )
            )
        return tasks
    except Exception:
        return None


def planner_node(state: AtomumGraphState) -> dict[str, Any]:
    """Nodo principal del Planner dentro de LangGraph."""
    directive = state.directive.strip()
    if not directive:
        return {
            "errors": [*state.errors, "Planner recibió una directiva vacía."],
            "next_agent": None,
        }

    plan = _llm_plan(directive, state.target)
    source = "groq_llm"
    if not plan:
        plan = _fallback_plan(directive, state.target)
        source = "deterministic_fallback"

    first_task = plan[0] if plan else None
    finding_entry = {
        "agent": "planner",
        "source": source,
        "tasks_created": len(plan),
        "first_task_id": first_task.id if first_task else None,
    }

    return {
        "plan": plan,
        "next_agent": first_task.assigned_agent if first_task else None,
        "findings": [*state.findings, finding_entry],
        "iteration": state.iteration + 1,
    }


def route_after_planner(state: AtomumGraphState) -> str:
    """Decide el siguiente paso del grafo según `next_agent`."""
    if not state.next_agent or not state.plan:
        return END
    return state.next_agent


def build_planner_graph():
    """Construye y compila el grafo base con el nodo Planner."""
    graph = StateGraph(AtomumGraphState)
    graph.add_node("planner", planner_node)

    # Placeholders iniciales para los siguientes agentes que iremos agregando
    for agent_name in (
        "threat_intel",
        "vuln_analyst",
        "security_reviewer",
        "coder",
        "critic",
        "report_agent",
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

    graph.add_edge(START, "planner")
    graph.add_conditional_edges(
        "planner",
        route_after_planner,
        {
            "threat_intel": "threat_intel",
            "vuln_analyst": "vuln_analyst",
            "security_reviewer": "security_reviewer",
            "coder": "coder",
            "critic": "critic",
            "report_agent": "report_agent",
            END: END,
        },
    )
    return graph.compile()


if __name__ == "__main__":
    app_graph = build_planner_graph()
    initial_state = AtomumGraphState(
        directive="Auditar exposición de puertos y proponer mejoras de seguridad",
        target="192.168.1.10",
    )
    result = app_graph.invoke(initial_state)
    print(json.dumps(result, indent=2, default=lambda o: o.model_dump() if hasattr(o, "model_dump") else str(o), ensure_ascii=False))
