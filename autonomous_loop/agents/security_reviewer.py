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

ReviewDecision = Literal["approve", "needs_hardening", "block_or_escalate"]


class SecurityControlCheck(BaseModel):
    """Verificación puntual de control o riesgo de seguridad."""

    check_id: str = Field(..., description="Identificador del control, ej. SEC-1")
    area: str = Field(..., description="Área auditada: alcance, secretos, red, ejecución o trazabilidad")
    status: Literal["pass", "warning", "fail"] = Field(
        default="warning", description="Resultado de la auditoría"
    )
    finding: str = Field(..., description="Observación técnica concreta")
    required_action: str = Field(..., description="Acción recomendada o requisito para avanzar")


class SecurityReviewReport(BaseModel):
    """Dictamen estructurado del agente Security Reviewer."""

    target: str | None = Field(default=None, description="Objetivo bajo revisión")
    decision: ReviewDecision = Field(
        default="needs_hardening",
        description="Decisión de control: approve, needs_hardening o block_or_escalate",
    )
    risk_score: int = Field(
        default=5, ge=0, le=10, description="Nivel de riesgo percibido de 0 a 10"
    )
    checks: list[SecurityControlCheck] = Field(
        default_factory=list,
        description="Controles evaluados durante la revisión",
    )
    guardrails_notes: list[str] = Field(
        default_factory=list,
        description="Notas sobre alcance autorizado, seguridad de agentes o mitigaciones",
    )
    summary: str = Field(default="", description="Síntesis del dictamen de seguridad")


def _extract_prior_findings(state: AtomumGraphState) -> dict[str, Any]:
    """Recupera los últimos reportes de Threat Intel y Vulnerability Analyst desde `findings`."""
    extracted: dict[str, Any] = {}
    for role in ("threat_intel", "vuln_analyst"):
        for entry in reversed(state.findings):
            if isinstance(entry, dict) and entry.get("agent") == role:
                if "report" in entry and isinstance(entry["report"], dict):
                    extracted[role] = entry["report"]
                else:
                    extracted[role] = entry
                break
    return extracted


def _fallback_security_review(
    directive: str,
    target: str | None,
    tasks: list[PlannerTask],
    prior_findings: dict[str, Any],
) -> SecurityReviewReport:
    """Genera una auditoría de seguridad determinista sin depender de un LLM."""
    lowered = directive.lower()
    label = target or "sin objetivo explícito"
    vuln_report = prior_findings.get("vuln_analyst", {})
    exposure = str(vuln_report.get("overall_exposure") or "medium")

    checks: list[SecurityControlCheck] = [
        SecurityControlCheck(
            check_id="SEC-1",
            area="alcance y autorización",
            status="warning" if not target else "pass",
            finding=(
                f"Objetivo evaluado: '{label}'."
                if target
                else "No se especificó un target explícito en el estado; conviene acotar el alcance."
            ),
            required_action=(
                "Confirmar alcance autorizado y entorno antes de ejecutar acciones activas."
            ),
        ),
        SecurityControlCheck(
            check_id="SEC-2",
            area="secretos y superficie de ejecución",
            status="warning",
            finding=(
                "Verificar manejo de API keys/credenciales, sanitización de entradas y límites "
                "en flujos automatizados o comandos."
            ),
            required_action=(
                "Asegurar que secretos vivan en entorno/secretos y nunca se expongan en logs o PRs."
            ),
        ),
        SecurityControlCheck(
            check_id="SEC-3",
            area="mitigación y trazabilidad",
            status="pass" if tasks else "warning",
            finding=(
                f"Exposición reportada por Vulnerability Analyst: '{exposure}' sobre {len(tasks)} tarea(s)."
            ),
            required_action=(
                "Documentar mitigaciones o criterios de validación antes del cierre."
            ),
        ),
    ]

    decision: ReviewDecision = "needs_hardening"
    risk_score = 5

    high_risk_keywords = (
        "exfiltr",
        "exploit",
        "destruir",
        "borrar todo",
        "sin autorización",
        "sin autorizacion",
        "bypass auth",
    )
    if any(k in lowered for k in high_risk_keywords):
        decision = "block_or_escalate"
        risk_score = 9
        checks.append(
            SecurityControlCheck(
                check_id="SEC-4",
                area="guardrails operativos",
                status="fail",
                finding="La directiva contiene patrones de alto riesgo o acción no acotada.",
                required_action="Bloquear ejecución automática y escalar a revisión humana.",
            )
        )
    elif exposure == "high" or any(k in lowered for k in ("producción", "produccion", "prod", "crítico", "critico")):
        decision = "needs_hardening"
        risk_score = 7
    elif not any(c.status == "fail" for c in checks) and target:
        risk_score = 4

    guardrails_notes = [
        "Mantener el principio de mínimo privilegio y alcance acotado en cada paso.",
        "Validar cambios de código o configuraciones antes de aplicar en entornos sensibles.",
    ]
    summary = (
        f"Revisión de seguridad para '{label}': decisión '{decision}' "
        f"(riesgo {risk_score}/10) con {len(checks)} controles auditados."
    )

    return SecurityReviewReport(
        target=target,
        decision=decision,
        risk_score=risk_score,
        checks=checks,
        guardrails_notes=guardrails_notes,
        summary=summary,
    )


def _llm_security_review(
    directive: str,
    target: str | None,
    tasks: list[PlannerTask],
    prior_findings: dict[str, Any],
) -> SecurityReviewReport | None:
    """Usa Groq para realizar la revisión de seguridad si hay API key configurada."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return None

    try:
        from groq import Groq  # type: ignore

        client = Groq(api_key=api_key)
        model = os.getenv("GROQ_SECURITY_REVIEWER_MODEL", "openai/gpt-oss-120b")
        system_prompt = (
            "Eres el agente Security Reviewer de ATOMUM. Auditas directiva, target, tareas "
            "y hallazgos previos de Threat Intel y Vulnerability Analyst. "
            "Devuelve ÚNICAMENTE un JSON válido con: "
            "'target' (string o null), "
            "'decision' (approve | needs_hardening | block_or_escalate), "
            "'risk_score' (entero 0 a 10), "
            "'checks' (lista de objetos con 'check_id', 'area', 'status' [pass|warning|fail], "
            "'finding', 'required_action'), "
            "'guardrails_notes' (lista de strings) y 'summary' (string)."
        )
        payload = json.dumps(
            {
                "directive": directive,
                "target": target,
                "tasks": [t.model_dump() for t in tasks],
                "prior_findings": prior_findings,
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
        return SecurityReviewReport.model_validate(parsed)
    except Exception:
        return None


def _select_next_agent(state: AtomumGraphState, decision: ReviewDecision) -> str | None:
    """Determina el próximo agente según el dictamen y las tareas pendientes."""
    if decision == "block_or_escalate":
        return None
    for task in state.plan:
        if task.status == "pending" and task.assigned_agent != "security_reviewer":
            return task.assigned_agent
    for task in state.plan:
        if task.status == "pending":
            return task.assigned_agent
    return None


def security_reviewer_node(state: AtomumGraphState) -> dict[str, Any]:
    """Nodo de LangGraph para el agente Security Reviewer."""
    directive = state.directive.strip()
    if not directive and not state.target:
        return {
            "errors": [
                *state.errors,
                "Security Reviewer recibió estado sin directiva ni objetivo.",
            ],
            "next_agent": None,
        }

    prior_findings = _extract_prior_findings(state)
    report = _llm_security_review(directive, state.target, state.plan, prior_findings)
    source = "groq_llm"
    if not report:
        report = _fallback_security_review(directive, state.target, state.plan, prior_findings)
        source = "deterministic_fallback"

    updated_plan: list[PlannerTask] = []
    for task in state.plan:
        if task.assigned_agent == "security_reviewer" and task.status == "pending":
            updated_plan.append(task.model_copy(update={"status": "completed"}))
        else:
            updated_plan.append(task)

    temp_state = state.model_copy(update={"plan": updated_plan})
    next_agent = _select_next_agent(temp_state, report.decision)

    finding_entry = {
        "agent": "security_reviewer",
        "source": source,
        "target": state.target,
        "decision": report.decision,
        "risk_score": report.risk_score,
        "report": report.model_dump(),
    }

    errors = list(state.errors)
    if report.decision == "block_or_escalate":
        errors.append(f"Security Reviewer bloqueó/escaló la ejecución: {report.summary}")

    return {
        "plan": updated_plan,
        "next_agent": next_agent,
        "findings": [*state.findings, finding_entry],
        "errors": errors,
        "iteration": state.iteration + 1,
    }


def build_security_reviewer_graph():
    """Compila un grafo de prueba centrado en el nodo `security_reviewer`."""
    graph = StateGraph(AtomumGraphState)
    graph.add_node("security_reviewer", security_reviewer_node)

    for agent_name in (
        "planner",
        "threat_intel",
        "vuln_analyst",
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

    graph.add_edge(START, "security_reviewer")
    graph.add_conditional_edges(
        "security_reviewer",
        route_after_planner,
        {
            "planner": "planner",
            "threat_intel": "threat_intel",
            "vuln_analyst": "vuln_analyst",
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
            title="Revisión de controles y exposición",
            assigned_agent="security_reviewer",
            rationale="Auditar riesgos antes de aplicar cambios.",
            status="pending",
        ),
        PlannerTask(
            id="T2",
            title="Implementar endurecimiento y parches",
            assigned_agent="coder",
            rationale="Aplicar mejoras recomendadas.",
            status="pending",
        ),
    ]
    state = AtomumGraphState(
        directive="Auditar exposición y endurecer servicio en producción",
        target="192.168.1.50",
        plan=sample_plan,
        next_agent="security_reviewer",
    )
    graph_app = build_security_reviewer_graph()
    output = graph_app.invoke(state)
    print(
        json.dumps(
            output,
            indent=2,
            default=lambda o: o.model_dump() if hasattr(o, "model_dump") else str(o),
            ensure_ascii=False,
        )
    )
