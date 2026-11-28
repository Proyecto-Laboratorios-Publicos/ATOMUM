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

PatchStrategy = Literal["patch_proposal", "hardening", "refactor", "test_only"]


class CodeChangeItem(BaseModel):
    """Propuesta acotada de cambio sobre un archivo o módulo."""

    change_id: str = Field(..., description="Identificador del cambio, ej. CODE-1")
    file_path: str = Field(..., description="Ruta relativa del archivo objetivo")
    strategy: PatchStrategy = Field(
        default="patch_proposal", description="Tipo de intervención propuesta"
    )
    summary: str = Field(..., description="Descripción clara del cambio propuesto")
    diff_preview: str = Field(
        default="",
        description="Fragmento ilustrativo de cambio o pseudo-diff para revisión",
    )
    validation_step: str = Field(
        ..., description="Cómo verificar que el cambio funciona sin romper el flujo"
    )


class CodingAgentReport(BaseModel):
    """Reporte estructurado generado por el agente Coder."""

    target: str | None = Field(default=None, description="Objetivo o componente asociado")
    changes: list[CodeChangeItem] = Field(
        default_factory=list,
        description="Lista de cambios propuestos o parches sugeridos",
    )
    ready_for_pr: bool = Field(
        default=False,
        description="Indica si la propuesta está lista para revisión/PR tras validaciones",
    )
    summary: str = Field(default="", description="Síntesis del trabajo de codificación")


def _extract_prior_context(state: AtomumGraphState) -> dict[str, Any]:
    """Recupera las últimas salidas relevantes de `findings` para orientar el código."""
    roles = ("threat_intel", "vuln_analyst", "security_reviewer", "task_decomposer")
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


def _fallback_coding_plan(
    directive: str,
    target: str | None,
    tasks: list[PlannerTask],
    prior_context: dict[str, Any],
) -> CodingAgentReport:
    """Genera propuestas de código deterministas sin depender de un LLM."""
    reviewer_ctx = prior_context.get("security_reviewer", {})
    decision = str(reviewer_ctx.get("decision") or "needs_hardening")
    lowered = directive.lower()

    default_file = (
        target.strip()
        if target and any(ext in target for ext in (".py", ".ts", ".js", ".json", ".yml", ".yaml"))
        else "autonomous_loop/core/autonomous_loop.py"
    )

    strategy: PatchStrategy = "patch_proposal"
    if decision == "needs_hardening" or any(
        k in lowered for k in ("seguridad", "hardening", "secret", "auth", "cve", "vulnerab")
    ):
        strategy = "hardening"
    elif any(k in lowered for k in ("refactor", "limpiar", "modular", "arquitectura")):
        strategy = "refactor"

    changes: list[CodeChangeItem] = [
        CodeChangeItem(
            change_id="CODE-1",
            file_path=default_file,
            strategy=strategy,
            summary=(
                f"Aplicar mejoras alineadas con '{directive}' y los hallazgos previos "
                f"({len(tasks)} tarea(s) en el plan)."
            ),
            diff_preview=(
                "# Propuesta acotada: validar entradas, evitar exposición de secretos "
                "y mantener retornos tipados en el estado del grafo."
            ),
            validation_step=(
                "Ejecutar pruebas unitarias/flujo del grafo y revisar diff antes de abrir PR."
            ),
        )
    ]

    if strategy == "hardening":
        changes.append(
            CodeChangeItem(
                change_id="CODE-2",
                file_path="autonomous_loop/core/pr_guard.py",
                strategy="hardening",
                summary=(
                    "Verificar guardrails de cambios, límites de alcance y ausencia de "
                    "credenciales hardcodeadas antes de validar el parche."
                ),
                diff_preview=(
                    "# Comprobar política de cambios y restricciones de seguridad antes de PR."
                ),
                validation_step=(
                    "Confirmar que las validaciones de seguridad pasen sin errores ni avisos críticos."
                ),
            )
        )

    ready_for_pr = decision != "block_or_escalate"
    summary = (
        f"Propuesta de código ({strategy}) sobre '{default_file}' con {len(changes)} "
        f"cambio(s) planificado(s). Lista para revisión/PR: {ready_for_pr}."
    )

    return CodingAgentReport(
        target=target or default_file,
        changes=changes,
        ready_for_pr=ready_for_pr,
        summary=summary,
    )


def _llm_coding_plan(
    directive: str,
    target: str | None,
    tasks: list[PlannerTask],
    prior_context: dict[str, Any],
) -> CodingAgentReport | None:
    """Usa Groq para proponer cambios de código estructurados si hay API key."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return None

    try:
        from groq import Groq  # type: ignore

        client = Groq(api_key=api_key)
        model = os.getenv("GROQ_CODER_MODEL", "openai/gpt-oss-120b")
        system_prompt = (
            "Eres el agente Coder de ATOMUM. Recibes directiva, target, tareas y contexto "
            "previo (Threat Intel, Vulnerability Analyst, Security Reviewer, Task Decomposer). "
            "Devuelve ÚNICAMENTE un JSON válido con: "
            "'target' (string o null), "
            "'changes' (lista de objetos con 'change_id', 'file_path', "
            "'strategy' [patch_proposal|hardening|refactor|test_only], 'summary', "
            "'diff_preview', 'validation_step'), "
            "'ready_for_pr' (booleano) y 'summary' (string)."
        )
        payload = json.dumps(
            {
                "directive": directive,
                "target": target,
                "tasks": [t.model_dump() for t in tasks],
                "prior_context": prior_context,
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
        return CodingAgentReport.model_validate(parsed)
    except Exception:
        return None


def _select_next_agent(state: AtomumGraphState) -> str | None:
    """Selecciona el siguiente agente pendiente en el plan tras Coder."""
    for task in state.plan:
        if task.status == "pending" and task.assigned_agent != "coder":
            return task.assigned_agent
    for task in state.plan:
        if task.status == "pending":
            return task.assigned_agent
    return None


def coding_agent_node(state: AtomumGraphState) -> dict[str, Any]:
    """Nodo de LangGraph para el agente Coder."""
    directive = state.directive.strip()
    if not directive and not state.target:
        return {
            "errors": [
                *state.errors,
                "Coder recibió estado sin directiva ni objetivo.",
            ],
            "next_agent": None,
        }

    prior_context = _extract_prior_context(state)
    report = _llm_coding_plan(directive, state.target, state.plan, prior_context)
    source = "groq_llm"
    if not report:
        report = _fallback_coding_plan(directive, state.target, state.plan, prior_context)
        source = "deterministic_fallback"

    updated_plan: list[PlannerTask] = []
    for task in state.plan:
        if task.assigned_agent == "coder" and task.status == "pending":
            updated_plan.append(task.model_copy(update={"status": "completed"}))
        else:
            updated_plan.append(task)

    temp_state = state.model_copy(update={"plan": updated_plan})
    next_agent = _select_next_agent(temp_state)

    finding_entry = {
        "agent": "coder",
        "source": source,
        "target": report.target,
        "changes_count": len(report.changes),
        "ready_for_pr": report.ready_for_pr,
        "report": report.model_dump(),
    }

    return {
        "plan": updated_plan,
        "next_agent": next_agent,
        "findings": [*state.findings, finding_entry],
        "iteration": state.iteration + 1,
    }


def build_coding_agent_graph():
    """Compila un grafo de prueba centrado en el nodo `coder`."""
    graph = StateGraph(AtomumGraphState)
    graph.add_node("coder", coding_agent_node)

    for agent_name in (
        "planner",
        "threat_intel",
        "vuln_analyst",
        "security_reviewer",
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

    graph.add_edge(START, "coder")
    graph.add_conditional_edges(
        "coder",
        route_after_planner,
        {
            "planner": "planner",
            "threat_intel": "threat_intel",
            "vuln_analyst": "vuln_analyst",
            "security_reviewer": "security_reviewer",
            "critic": "critic",
            END: END,
        },
    )
    return graph.compile()


if __name__ == "__main__":
    sample_plan = [
        PlannerTask(
            id="T1",
            title="Implementar endurecimiento y parches en el módulo",
            assigned_agent="coder",
            rationale="Resolver debilidades señaladas en el análisis y revisión.",
            status="pending",
        ),
        PlannerTask(
            id="T2",
            title="Evaluación crítica final del cambio",
            assigned_agent="critic",
            rationale="Verificar calidad, alcance y criterios de cierre.",
            status="pending",
        ),
    ]
    state = AtomumGraphState(
        directive="Endurecer manejo de entradas y preparar propuesta de cambio",
        target="autonomous_loop/core/autonomous_loop.py",
        plan=sample_plan,
        next_agent="coder",
    )
    graph_app = build_coding_agent_graph()
    output = graph_app.invoke(state)
    print(
        json.dumps(
            output,
            indent=2,
            default=lambda o: o.model_dump() if hasattr(o, "model_dump") else str(o),
            ensure_ascii=False,
        )
    )
