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


class FinalReport(BaseModel):
    """Informe final consolidado del ciclo de ejecución de ATOMUM."""

    title: str = Field(..., description="Título ejecutivo del informe")
    directive: str = Field(..., description="Directiva original del ciclo")
    target: str | None = Field(default=None, description="Objetivo evaluado")
    status: Literal["completed", "completed_with_warnings", "blocked_or_escalated"] = Field(
        default="completed",
        description="Estado final de cierre del flujo",
    )
    executive_summary: str = Field(
        default="", description="Resumen claro y directo de lo realizado y hallado"
    )
    key_findings: list[str] = Field(
        default_factory=list,
        description="Puntos clave consolidados de los agentes previos",
    )
    proposed_actions: list[str] = Field(
        default_factory=list,
        description="Acciones recomendadas, cambios sugeridos o siguientes pasos",
    )
    plan_overview: list[str] = Field(
        default_factory=list,
        description="Estado resumido de las tareas del plan",
    )
    markdown_report: str = Field(
        default="",
        description="Informe listo para mostrar en UI, guardar en artefacto o adjuntar",
    )


def _collect_agent_reports(state: AtomumGraphState) -> dict[str, Any]:
    """Recupera las últimas salidas relevantes de cada agente especialista desde `findings`."""
    roles = ("threat_intel", "vuln_analyst", "security_reviewer", "coder", "critic")
    collected: dict[str, Any] = {}
    for role in roles:
        for entry in reversed(state.findings):
            if isinstance(entry, dict) and entry.get("agent") == role:
                if "report" in entry and isinstance(entry["report"], dict):
                    collected[role] = entry["report"]
                else:
                    collected[role] = entry
                break
    return collected


def _render_markdown(
    title: str,
    directive: str,
    target: str | None,
    status: str,
    executive_summary: str,
    key_findings: list[str],
    proposed_actions: list[str],
    plan_overview: list[str],
) -> str:
    """Construye un reporte en Markdown limpio y legible."""
    lines = [
        f"# {title}",
        "",
        f"- **Objetivo (`target`):** `{target or 'no especificado'}`",
        f"- **Estado de cierre:** `{status}`",
        f"- **Directiva:** {directive or 'sin directiva'}",
        "",
        "## Resumen ejecutivo",
        executive_summary,
        "",
        "## Hallazgos clave",
    ]
    if key_findings:
        lines.extend(f"- {item}" for item in key_findings)
    else:
        lines.append("- Sin hallazgos adicionales registrados.")

    lines.extend(["", "## Acciones y siguientes pasos"])
    if proposed_actions:
        lines.extend(f"- {step}" for step in proposed_actions)
    else:
        lines.append("- Sin acciones pendientes adicionales.")

    if plan_overview:
        lines.extend(["", "## Estado del plan"])
        lines.extend(f"- {task_line}" for task_line in plan_overview)

    return "\n".join(lines)


def _fallback_report(
    directive: str,
    target: str | None,
    tasks: list[PlannerTask],
    errors: list[str],
    reports: dict[str, Any],
) -> FinalReport:
    """Genera un informe final determinista sin depender de un LLM."""
    label = target or "alcance general"
    key_findings: list[str] = []
    proposed_actions: list[str] = []

    if "threat_intel" in reports:
        ti = reports["threat_intel"]
        key_findings.append(
            f"[Threat Intel] Tipo `{ti.get('target_type', 'general')}`, "
            f"riesgo `{ti.get('risk_level', 'medium')}`: {ti.get('summary', '')}".strip()
        )
        for rec in ti.get("recommendations", [])[:2]:
            proposed_actions.append(str(rec))

    if "vuln_analyst" in reports:
        va = reports["vuln_analyst"]
        v_count = len(va.get("findings_list", [])) if isinstance(va.get("findings_list"), list) else 0
        key_findings.append(
            f"[Vulnerability Analyst] Exposición `{va.get('overall_exposure', 'medium')}` "
            f"con {v_count} punto(s): {va.get('summary', '')}".strip()
        )
        for step in va.get("next_steps", [])[:2]:
            proposed_actions.append(str(step))

    if "security_reviewer" in reports:
        sr = reports["security_reviewer"]
        key_findings.append(
            f"[Security Reviewer] Decisión `{sr.get('decision', 'needs_hardening')}` "
            f"(score {sr.get('risk_score', 'N/A')}/10): {sr.get('summary', '')}".strip()
        )
        for note in sr.get("guardrails_notes", [])[:2]:
            proposed_actions.append(str(note))

    if "coder" in reports:
        cd = reports["coder"]
        c_count = len(cd.get("changes", [])) if isinstance(cd.get("changes"), list) else 0
        key_findings.append(
            f"[Coder] {c_count} cambio(s) propuesto(s), listo para PR={cd.get('ready_for_pr', False)}: "
            f"{cd.get('summary', '')}".strip()
        )
        for chg in cd.get("changes", [])[:2]:
            if isinstance(chg, dict) and chg.get("validation_step"):
                proposed_actions.append(str(chg["validation_step"]))

    if "critic" in reports:
        cr = reports["critic"]
        key_findings.append(
            f"[Critic] Veredicto `{cr.get('verdict', 'accept')}` "
            f"(calidad {cr.get('quality_score', 'N/A')}/10): {cr.get('summary', '')}".strip()
        )
        for crit in cr.get("critiques", [])[:2]:
            if isinstance(crit, dict) and crit.get("action_required"):
                proposed_actions.append(str(crit["action_required"]))

    # Deduplicar preservando orden
    proposed_actions = list(dict.fromkeys(proposed_actions))

    status: Literal["completed", "completed_with_warnings", "blocked_or_escalated"] = "completed"
    if (
        errors
        or reports.get("security_reviewer", {}).get("decision") == "block_or_escalate"
        or reports.get("critic", {}).get("verdict") == "escalate_or_reject"
    ):
        status = "blocked_or_escalated"
    elif (
        errors
        or reports.get("critic", {}).get("verdict") == "revise"
        or reports.get("security_reviewer", {}).get("decision") == "needs_hardening"
    ):
        status = "completed_with_warnings"

    plan_overview = [f"[{t.status}] {t.id}: {t.title} ({t.assigned_agent})" for t in tasks]
    title = f"Informe ATOMUM — {label}"
    executive_summary = (
        f"Ciclo finalizado con estado '{status}' para '{label}', consolidando "
        f"{len(reports)} reporte(s) de agentes y {len(tasks)} tarea(s) planificadas."
    )
    markdown_report = _render_markdown(
        title=title,
        directive=directive,
        target=target,
        status=status,
        executive_summary=executive_summary,
        key_findings=key_findings,
        proposed_actions=proposed_actions,
        plan_overview=plan_overview,
    )

    return FinalReport(
        title=title,
        directive=directive,
        target=target,
        status=status,
        executive_summary=executive_summary,
        key_findings=key_findings,
        proposed_actions=proposed_actions,
        plan_overview=plan_overview,
        markdown_report=markdown_report,
    )


def _llm_report(
    directive: str,
    target: str | None,
    tasks: list[PlannerTask],
    errors: list[str],
    reports: dict[str, Any],
) -> FinalReport | None:
    """Usa Groq para redactar el informe final consolidado si hay API key configurada."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return None

    try:
        from groq import Groq  # type: ignore

        client = Groq(api_key=api_key)
        model = os.getenv("GROQ_REPORT_AGENT_MODEL", "llama-3.3-70b-versatile")
        system_prompt = (
            "Eres el Report Agent de ATOMUM. Consolidas directiva, target, plan, errores "
            "y reportes de los demás agentes en un informe final claro y accionable. "
            "Devuelve ÚNICAMENTE un JSON válido con: "
            "'title' (string), "
            "'directive' (string), "
            "'target' (string o null), "
            "'status' (completed | completed_with_warnings | blocked_or_escalated), "
            "'executive_summary' (string), "
            "'key_findings' (lista de strings), "
            "'proposed_actions' (lista de strings), "
            "'plan_overview' (lista de strings) y "
            "'markdown_report' (string en Markdown)."
        )
        payload = json.dumps(
            {
                "directive": directive,
                "target": target,
                "tasks": [t.model_dump() for t in tasks],
                "errors": errors,
                "agent_reports": reports,
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
        parsed.setdefault("directive", directive)
        parsed.setdefault("target", target)
        if not parsed.get("markdown_report"):
            parsed["markdown_report"] = _render_markdown(
                title=str(parsed.get("title") or f"Informe ATOMUM — {target or 'general'}"),
                directive=str(parsed.get("directive") or directive),
                target=parsed.get("target"),
                status=str(parsed.get("status") or "completed"),
                executive_summary=str(parsed.get("executive_summary") or ""),
                key_findings=[str(x) for x in parsed.get("key_findings", [])],
                proposed_actions=[str(x) for x in parsed.get("proposed_actions", [])],
                plan_overview=[str(x) for x in parsed.get("plan_overview", [])],
            )
        return FinalReport.model_validate(parsed)
    except Exception:
        return None


def _select_next_agent(state: AtomumGraphState) -> str | None:
    """Selecciona el siguiente agente pendiente si quedara alguno, o None para cerrar."""
    for task in state.plan:
        if task.status == "pending" and task.assigned_agent != "report_agent":
            return task.assigned_agent
    return None


def report_agent_node(state: AtomumGraphState) -> dict[str, Any]:
    """Nodo de LangGraph para el Report Agent."""
    directive = state.directive.strip()
    if not directive and not state.target and not state.findings:
        return {
            "errors": [
                *state.errors,
                "Report Agent recibió estado vacío sin directiva, objetivo ni hallazgos.",
            ],
            "next_agent": None,
        }

    updated_plan: list[PlannerTask] = []
    for task in state.plan:
        if task.assigned_agent == "report_agent" and task.status == "pending":
            updated_plan.append(task.model_copy(update={"status": "completed"}))
        else:
            updated_plan.append(task)

    reports = _collect_agent_reports(state)
    report = _llm_report(directive, state.target, updated_plan, state.errors, reports)
    source = "groq_llm"
    if not report:
        report = _fallback_report(directive, state.target, updated_plan, state.errors, reports)
        source = "deterministic_fallback"

    temp_state = state.model_copy(update={"plan": updated_plan})
    next_agent = _select_next_agent(temp_state)

    finding_entry = {
        "agent": "report_agent",
        "source": source,
        "target": state.target,
        "status": report.status,
        "report": report.model_dump(),
    }

    return {
        "plan": updated_plan,
        "next_agent": next_agent,
        "findings": [*state.findings, finding_entry],
        "iteration": state.iteration + 1,
    }


def build_report_agent_graph():
    """Compila un grafo de prueba centrado en el nodo `report_agent`."""
    graph = StateGraph(AtomumGraphState)
    graph.add_node("report_agent", report_agent_node)

    for agent_name in (
        "planner",
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

    graph.add_edge(START, "report_agent")
    graph.add_conditional_edges(
        "report_agent",
        route_after_planner,
        {
            "planner": "planner",
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
            title="Generar informe final consolidado",
            assigned_agent="report_agent",
            rationale="Sintetizar hallazgos, acciones y estado de cierre.",
            status="pending",
        ),
    ]
    state = AtomumGraphState(
        directive="Consolidar resultados de la auditoría y cierre del ciclo",
        target="192.168.1.50",
        plan=sample_plan,
        next_agent="report_agent",
    )
    graph_app = build_report_agent_graph()
    output = graph_app.invoke(state)
    print(
        json.dumps(
            output,
            indent=2,
            default=lambda o: o.model_dump() if hasattr(o, "model_dump") else str(o),
            ensure_ascii=False,
        )
    )
