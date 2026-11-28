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

CriticVerdict = Literal["accept", "revise", "escalate_or_reject"]


class CritiquePoint(BaseModel):
    """Observación crítica puntual sobre el resultado o propuesta actual."""

    point_id: str = Field(..., description="Identificador del punto, ej. CRIT-1")
    dimension: Literal[
        "alignment", "completeness", "safety_and_guardrails", "maintainability"
    ] = Field(default="alignment", description="Dimensión evaluada")
    severity: Literal["minor", "major", "blocker"] = Field(
        default="minor", description="Impacto de la observación"
    )
    observation: str = Field(..., description="Descripción objetiva de lo observado")
    action_required: str = Field(
        ..., description="Ajuste concreto o criterio para cerrar el ciclo"
    )


class CriticReport(BaseModel):
    """Dictamen estructurado del agente Critic."""

    target: str | None = Field(default=None, description="Objetivo evaluado")
    verdict: CriticVerdict = Field(
        default="accept",
        description="Dictamen final: accept, revise o escalate_or_reject",
    )
    quality_score: int = Field(
        default=8, ge=0, le=10, description="Puntaje de calidad y completitud de 0 a 10"
    )
    critiques: list[CritiquePoint] = Field(
        default_factory=list,
        description="Puntos críticos o verificaciones realizadas",
    )
    approved_for_completion: bool = Field(
        default=True,
        description="Indica si el ciclo puede darse por cerrado o pasar a PR/entrega",
    )
    summary: str = Field(default="", description="Síntesis ejecutiva de la crítica")


def _extract_pipeline_context(state: AtomumGraphState) -> dict[str, Any]:
    """Recupera las últimas salidas registradas por los demás agentes en `findings`."""
    roles = ("threat_intel", "vuln_analyst", "security_reviewer", "coder")
    context: dict[str, Any] = {}
    for role in roles:
        for entry in reversed(state.findings):
            if isinstance(entry, dict) and entry.get("agent") == role:
                if "report" in entry and isinstance(entry["report"], dict):
                    context[role] = entry["report"]
                else:
                    context[role] = entry
                break
    return context


def _fallback_critique(
    directive: str,
    target: str | None,
    tasks: list[PlannerTask],
    errors: list[str],
    context: dict[str, Any],
) -> CriticReport:
    """Genera una evaluación crítica determinista si no hay LLM o falla la llamada."""
    label = target or "alcance general"
    sec_ctx = context.get("security_reviewer", {})
    sec_decision = str(sec_ctx.get("decision") or "")
    coder_ctx = context.get("coder", {})
    changes = coder_ctx.get("changes") if isinstance(coder_ctx.get("changes"), list) else []

    critiques: list[CritiquePoint] = []
    verdict: CriticVerdict = "accept"
    quality_score = 8

    if errors or sec_decision == "block_or_escalate":
        verdict = "escalate_or_reject"
        quality_score = 2
        critiques.append(
            CritiquePoint(
                point_id="CRIT-1",
                dimension="safety_and_guardrails",
                severity="blocker",
                observation=(
                    "Se detectaron errores previos o un bloqueo/escalado de seguridad "
                    f"({len(errors)} error(es) registrado(s))."
                ),
                action_required=(
                    "Detener avance automático y resolver condiciones de seguridad o errores antes de continuar."
                ),
            )
        )
    else:
        if not target:
            quality_score -= 1
            critiques.append(
                CritiquePoint(
                    point_id="CRIT-1",
                    dimension="completeness",
                    severity="minor",
                    observation="No se especificó un objetivo (`target`) explícito en el estado.",
                    action_required="Definir el objetivo concreto si se requiere trazabilidad más estricta.",
                )
            )

        if "coder" in context and not changes:
            verdict = "revise"
            quality_score = min(quality_score, 5)
            critiques.append(
                CritiquePoint(
                    point_id="CRIT-2",
                    dimension="completeness",
                    severity="major",
                    observation="El agente Coder se ejecutó sin listar cambios concretos en `changes`.",
                    action_required="Especificar archivos, estrategia y pasos de validación antes de cerrar.",
                )
            )
        elif sec_decision == "needs_hardening":
            critiques.append(
                CritiquePoint(
                    point_id="CRIT-2",
                    dimension="safety_and_guardrails",
                    severity="minor",
                    observation=(
                        "Security Reviewer marcó `needs_hardening`; verificar que las mitigaciones "
                        "queden cubiertas en validación y revisión."
                    ),
                    action_required="Confirmar pruebas y controles antes de aplicar o abrir PR.",
                )
            )

        if not critiques:
            critiques.append(
                CritiquePoint(
                    point_id="CRIT-1",
                    dimension="alignment",
                    severity="minor",
                    observation=(
                        f"Flujo alineado con la directiva '{directive}' y {len(tasks)} tarea(s) en el plan."
                    ),
                    action_required="Proceder con cierre o revisión final según el estado del plan.",
                )
            )

    approved = verdict == "accept"
    summary = (
        f"Evaluación crítica para '{label}': dictamen '{verdict}' "
        f"(calidad {quality_score}/10, aprobado={approved})."
    )

    return CriticReport(
        target=target,
        verdict=verdict,
        quality_score=quality_score,
        critiques=critiques,
        approved_for_completion=approved,
        summary=summary,
    )


def _llm_critique(
    directive: str,
    target: str | None,
    tasks: list[PlannerTask],
    errors: list[str],
    context: dict[str, Any],
) -> CriticReport | None:
    """Usa Groq para generar la evaluación crítica si hay API key configurada."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return None

    try:
        from groq import Groq  # type: ignore

        client = Groq(api_key=api_key)
        model = os.getenv("GROQ_CRITIC_MODEL", "openai/gpt-oss-120b")
        system_prompt = (
            "Eres el agente Critic de ATOMUM. Evalúas directiva, target, plan, errores "
            "y hallazgos de los demás agentes para dar una crítica honesta y accionable. "
            "Devuelve ÚNICAMENTE un JSON válido con: "
            "'target' (string o null), "
            "'verdict' (accept | revise | escalate_or_reject), "
            "'quality_score' (entero 0 a 10), "
            "'critiques' (lista de objetos con 'point_id', "
            "'dimension' [alignment|completeness|safety_and_guardrails|maintainability], "
            "'severity' [minor|major|blocker], 'observation', 'action_required'), "
            "'approved_for_completion' (booleano) y 'summary' (string)."
        )
        payload = json.dumps(
            {
                "directive": directive,
                "target": target,
                "tasks": [t.model_dump() for t in tasks],
                "errors": errors,
                "pipeline_context": context,
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
        if "target" not in parsed:
            parsed["target"] = target
        return CriticReport.model_validate(parsed)
    except Exception:
        return None


def _select_next_agent(state: AtomumGraphState, verdict: CriticVerdict) -> str | None:
    """Determina el siguiente agente según el dictamen crítico y tareas pendientes."""
    if verdict == "escalate_or_reject":
        return None
    if verdict == "revise":
        for task in state.plan:
            if task.assigned_agent == "coder" and task.status != "completed":
                return "coder"
        if any(f.get("agent") == "coder" for f in state.findings if isinstance(f, dict)):
            return "coder"
    for task in state.plan:
        if task.status == "pending" and task.assigned_agent != "critic":
            return task.assigned_agent
    for task in state.plan:
        if task.status == "pending":
            return task.assigned_agent
    return None


def critic_node(state: AtomumGraphState) -> dict[str, Any]:
    """Nodo de LangGraph para el agente Critic."""
    directive = state.directive.strip()
    if not directive and not state.target:
        return {
            "errors": [
                *state.errors,
                "Critic recibió estado sin directiva ni objetivo.",
            ],
            "next_agent": None,
        }

    context = _extract_pipeline_context(state)
    report = _llm_critique(directive, state.target, state.plan, state.errors, context)
    source = "groq_llm"
    if not report:
        report = _fallback_critique(
            directive, state.target, state.plan, state.errors, context
        )
        source = "deterministic_fallback"

    updated_plan: list[PlannerTask] = []
    for task in state.plan:
        if task.assigned_agent == "critic" and task.status == "pending":
            new_status = "completed" if report.verdict == "accept" else "pending"
            updated_plan.append(task.model_copy(update={"status": new_status}))
        else:
            updated_plan.append(task)

    temp_state = state.model_copy(update={"plan": updated_plan})
    next_agent = _select_next_agent(temp_state, report.verdict)

    finding_entry = {
        "agent": "critic",
        "source": source,
        "target": state.target,
        "verdict": report.verdict,
        "quality_score": report.quality_score,
        "approved_for_completion": report.approved_for_completion,
        "report": report.model_dump(),
    }

    errors = list(state.errors)
    if report.verdict == "escalate_or_reject":
        errors.append(f"Critic escaló/rechazó el flujo: {report.summary}")

    return {
        "plan": updated_plan,
        "next_agent": next_agent,
        "findings": [*state.findings, finding_entry],
        "errors": errors,
        "iteration": state.iteration + 1,
    }


def build_critic_graph():
    """Compila un grafo de prueba centrado en el nodo `critic`."""
    graph = StateGraph(AtomumGraphState)
    graph.add_node("critic", critic_node)

    for agent_name in (
        "planner",
        "threat_intel",
        "vuln_analyst",
        "security_reviewer",
        "coder",
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

    graph.add_edge(START, "critic")
    graph.add_conditional_edges(
        "critic",
        route_after_planner,
        {
            "planner": "planner",
            "threat_intel": "threat_intel",
            "vuln_analyst": "vuln_analyst",
            "security_reviewer": "security_reviewer",
            "coder": "coder",
            END: END,
        },
    )
    return graph.compile()


if __name__ == "__main__":
    sample_plan = [
        PlannerTask(
            id="T1",
            title="Revisión crítica final del cambio",
            assigned_agent="critic",
            rationale="Evaluar calidad, seguridad y completitud antes de cerrar.",
            status="pending",
        ),
    ]
    state = AtomumGraphState(
        directive="Validar calidad y seguridad del cambio propuesto",
        target="autonomous_loop/core/autonomous_loop.py",
        plan=sample_plan,
        next_agent="critic",
    )
    graph_app = build_critic_graph()
    output = graph_app.invoke(state)
    print(
        json.dumps(
            output,
            indent=2,
            default=lambda o: o.model_dump() if hasattr(o, "model_dump") else str(o),
            ensure_ascii=False,
        )
    )
