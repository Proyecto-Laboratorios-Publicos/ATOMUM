from __future__ import annotations

import ipaddress
import json
import os
import re
from typing import Any, Literal

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

from autonomous_loop.agents.planner import (
    AtomumGraphState,
    PlannerTask,
    route_after_planner,
)


class ThreatIntelReport(BaseModel):
    """Resumen estructurado de inteligencia de amenazas para el objetivo."""

    target_type: Literal["ipv4", "ipv6", "domain_or_url", "repository_or_code", "general"] = (
        Field(default="general", description="Clasificación técnica del objetivo")
    )
    exposure_surface: list[str] = Field(
        default_factory=list,
        description="Superficies o vectores relevantes a considerar",
    )
    risk_level: Literal["low", "medium", "high", "unknown"] = Field(
        default="medium",
        description="Nivel preliminar de exposición/riesgo contextual",
    )
    recommendations: list[str] = Field(
        default_factory=list,
        description="Recomendaciones de enfoque para los siguientes agentes",
    )
    summary: str = Field(
        default="",
        description="Síntesis breve y accionable del relevamiento",
    )


def _classify_target(target: str | None, directive: str) -> str:
    """Clasifica el objetivo de forma liviana y determinista."""
    candidate = (target or "").strip()
    if candidate:
        try:
            ip_obj = ipaddress.ip_address(candidate)
            return "ipv6" if ip_obj.version == 6 else "ipv4"
        except ValueError:
            pass

        if "/" in candidate and any(c.isdigit() for c in candidate):
            return "ipv4"
        if "." in candidate or candidate.startswith(("http://", "https://")):
            return "domain_or_url"
        if any(sep in candidate for sep in ("/", "\\", ".py", ".ts", ".js", ".json")):
            return "repository_or_code"

    lowered = directive.lower()
    if any(k in lowered for k in ("código", "codigo", "repo", "pull request", "pr", "agente", "script")):
        return "repository_or_code"
    if any(k in lowered for k in ("ip", "puerto", "port", "red", "subred", "firewall")):
        return "ipv4"
    if any(k in lowered for k in ("dominio", "web", "api", "endpoint", "url", "websocket")):
        return "domain_or_url"
    return "general"


def _fallback_threat_intel(
    directive: str, target: str | None, tasks: list[PlannerTask]
) -> ThreatIntelReport:
    """Genera un análisis de contexto determinista si no hay LLM o falla la llamada."""
    target_type = _classify_target(target, directive)
    lowered = directive.lower()
    label = target or "alcance general de la directiva"

    surfaces: list[str] = []
    recommendations: list[str] = []
    risk_level: Literal["low", "medium", "high", "unknown"] = "medium"

    if target_type in ("ipv4", "ipv6"):
        surfaces = [
            "Puertos TCP/UDP expuestos y banners de servicios",
            "Reglas de filtrado perimetral / segmentación de red",
            "Posibles servicios de administración o gestión expuestos",
        ]
        recommendations = [
            "Priorizar detección de servicios activos y versiones antes de buscar CVEs.",
            "Verificar autorización explícita y alcance de red antes de cualquier escaneo.",
        ]
    elif target_type == "domain_or_url":
        surfaces = [
            "Endpoints HTTP/HTTPS, cabeceras de seguridad y autenticación",
            "Canales en tiempo real (WebSockets / APIs) y control de acceso",
            "Subdominios o rutas expuestas con validación insuficiente",
        ]
        recommendations = [
            "Revisar puntos de entrada expuestos, manejo de sesiones y validación de datos.",
            "Correlacionar hallazgos con vectores de abuso web y configuración TLS.",
        ]
    elif target_type == "repository_or_code":
        surfaces = [
            "Manejo de secretos, variables de entorno y entradas no confiables",
            "Flujos automatizados (CI/CD, PRs, ejecución de agentes o herramientas)",
            "Dependencias desactualizadas y superfice de ejecución de código",
        ]
        recommendations = [
            "Inspeccionar puntos donde se ejecutan comandos, prompts o consultas externas.",
            "Validar cambios propuestos con pruebas y revisión de seguridad antes de aplicar.",
        ]
    else:
        surfaces = [
            "Contexto operativo y delimitación del objetivo",
            "Dependencias críticas y puntos de fallo o exposición",
        ]
        recommendations = [
            "Precisar un objetivo concreto (host, URL, repo o módulo) para acotar el análisis.",
        ]

    if any(k in lowered for k in ("producción", "produccion", "prod", "crítico", "critico", "expuesto")):
        risk_level = "high"

    task_titles = [t.title for t in tasks[:3]]
    context_note = f" Tareas planificadas: {', '.join(task_titles)}." if task_titles else ""
    summary = (
        f"Relevamiento inicial clasificado como '{target_type}' para '{label}'. "
        f"Nivel preliminar de riesgo: {risk_level}.{context_note}"
    )

    return ThreatIntelReport(
        target_type=target_type,  # type: ignore[arg-type]
        exposure_surface=surfaces,
        risk_level=risk_level,
        recommendations=recommendations,
        summary=summary,
    )


def _llm_threat_intel(
    directive: str, target: str | None, tasks: list[PlannerTask]
) -> ThreatIntelReport | None:
    """Enriquece el relevamiento de Threat Intel usando Groq si está disponible."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return None

    try:
        from groq import Groq  # type: ignore

        client = Groq(api_key=api_key)
        model = os.getenv("GROQ_THREAT_INTEL_MODEL", "llama-3.3-70b-versatile")
        system_prompt = (
            "Eres el agente de Threat Intel de ATOMUM. Analiza directiva, target y tareas planificadas. "
            "Devuelve ÚNICAMENTE un JSON válido con las claves: "
            "'target_type' (ipv4, ipv6, domain_or_url, repository_or_code, general), "
            "'exposure_surface' (lista de strings concisos), "
            "'risk_level' (low, medium, high, unknown), "
            "'recommendations' (lista de strings accionables) y "
            "'summary' (string breve)."
        )
        payload = json.dumps(
            {
                "directive": directive,
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
        return ThreatIntelReport.model_validate(parsed)
    except Exception:
        return None


def _select_next_agent(state: AtomumGraphState) -> str | None:
    """Elige el siguiente agente pendiente en el plan tras completar Threat Intel."""
    for task in state.plan:
        if task.status == "pending" and task.assigned_agent != "threat_intel":
            return task.assigned_agent
    for task in state.plan:
        if task.status == "pending":
            return task.assigned_agent
    return None


def threat_intel_node(state: AtomumGraphState) -> dict[str, Any]:
    """Nodo de LangGraph para el agente de inteligencia de amenazas."""
    directive = state.directive.strip()
    if not directive and not state.target:
        return {
            "errors": [
                *state.errors,
                "Threat Intel recibió estado sin directiva ni objetivo.",
            ],
            "next_agent": None,
        }

    report = _llm_threat_intel(directive, state.target, state.plan)
    source = "groq_llm"
    if not report:
        report = _fallback_threat_intel(directive, state.target, state.plan)
        source = "deterministic_fallback"

    updated_plan: list[PlannerTask] = []
    for task in state.plan:
        if task.assigned_agent == "threat_intel" and task.status == "pending":
            updated_plan.append(task.model_copy(update={"status": "completed"}))
        else:
            updated_plan.append(task)

    temp_state = state.model_copy(update={"plan": updated_plan})
    next_agent = _select_next_agent(temp_state)

    finding_entry = {
        "agent": "threat_intel",
        "source": source,
        "target": state.target,
        "report": report.model_dump(),
    }

    return {
        "plan": updated_plan,
        "next_agent": next_agent,
        "findings": [*state.findings, finding_entry],
        "iteration": state.iteration + 1,
    }


def build_threat_intel_graph():
    """Compila un grafo de prueba centrado en el nodo `threat_intel`."""
    graph = StateGraph(AtomumGraphState)
    graph.add_node("threat_intel", threat_intel_node)

    for agent_name in (
        "planner",
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

    graph.add_edge(START, "threat_intel")
    graph.add_conditional_edges(
        "threat_intel",
        route_after_planner,
        {
            "planner": "planner",
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
            title="Análisis inicial de contexto y superficie",
            assigned_agent="threat_intel",
            rationale="Delimitar alcance y vectores relevantes.",
        ),
        PlannerTask(
            id="T2",
            title="Evaluación de vulnerabilidades y servicios",
            assigned_agent="vuln_analyst",
            rationale="Identificar exposiciones relevantes.",
        ),
    ]
    state = AtomumGraphState(
        directive="Auditar exposición de red y proponer mejoras en producción",
        target="192.168.1.25",
        plan=sample_plan,
        next_agent="threat_intel",
    )
    graph_app = build_threat_intel_graph()
    output = graph_app.invoke(state)
    print(
        json.dumps(
            output,
            indent=2,
            default=lambda o: o.model_dump() if hasattr(o, "model_dump") else str(o),
            ensure_ascii=False,
        )
    )
