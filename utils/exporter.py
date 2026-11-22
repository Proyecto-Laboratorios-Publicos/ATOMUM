from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
import pathlib
from typing import Any, Dict, List, Optional, Union

from docx import Document
from docx.shared import Inches, Pt

log = logging.getLogger(__name__)


def _add_heading(doc: Document, text: str, level: int = 1) -> None:
    heading = doc.add_heading(text, level=level)
    if heading.runs:
        heading.runs[0].font.size = Pt(14 if level == 1 else 12)


def _add_table(doc: Document, findings: List[Dict[str, Any]]) -> None:
    """Crea una tabla con columnas: ID, Severidad, Archivo, Línea, Descripción, Remediación."""
    table = doc.add_table(rows=1, cols=6)
    hdr_cells = table.rows[0].cells
    headers = ["ID", "Severidad", "Archivo", "Línea", "Descripción", "Remediación"]
    for i, h in enumerate(headers):
        hdr_cells[i].text = h
        if hdr_cells[i].paragraphs and hdr_cells[i].paragraphs[0].runs:
            hdr_cells[i].paragraphs[0].runs[0].font.bold = True

    for f in findings:
        row_cells = table.add_row().cells
        row_cells[0].text = str(f.get("id", ""))
        row_cells[1].text = str(f.get("severity", ""))
        row_cells[2].text = str(f.get("file", ""))
        row_cells[3].text = str(f.get("line", ""))
        row_cells[4].text = str(f.get("title", ""))
        row_cells[5].text = str(f.get("remediation", "N/A"))


def export_security_report_to_word(
    report_json: Dict[str, Any],
    alerts: List[Dict[str, Any]],
    output_path: pathlib.Path,
) -> None:
    """
    Genera un documento .docx con:
    • Resumen ejecutivo (total de hallazgos, críticos, altos, medios, bajos)
    • Tabla detallada de los hallazgos críticos/alto riesgo (incluye remediación)
    • Anexos opcionales (lista completa de hallazgos si se desea)

    Parameters
    ----------
    report_json : dict
        JSON completo devuelto por core.security_analyzer.
    alerts : list[dict]
        Subconjunto filtrado por severidad (CRITICAL/HIGH) ya enriquecido.
    output_path : pathlib.Path
        Ruta destino del archivo .docx.
    """
    doc = Document()

    # ------------------------------------------------------------------ #
    # Portada / Título
    # ------------------------------------------------------------------ #
    doc.add_heading("Informe de Seguridad – Análisis Automático", level=0)
    doc.add_paragraph(f"Fecha de generación: {output_path.stem.split('_')[-1]}")
    doc.add_page_break()

    # ------------------------------------------------------------------ #
    # Resumen ejecutivo
    # ------------------------------------------------------------------ #
    total = sum(len(entry.get("issues", [])) for entry in report_json.get("results", []))
    severity_counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for entry in report_json.get("results", []):
        for issue in entry.get("issues", []):
            sev = issue.get("severity", "LOW")
            severity_counts[sev] = severity_counts.get(sev, 0) + 1

    _add_heading(doc, "Resumen Ejecutivo", level=1)
    doc.add_paragraph(f"Total de hallazgos detectados: {total}")
    for sev in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
        doc.add_paragraph(f"- {sev}: {severity_counts.get(sev, 0)}")

    # ------------------------------------------------------------------ #
    # Tabla de alertas críticas/alto riesgo
    # ------------------------------------------------------------------ #
    if alerts:
        _add_heading(doc, "Hallazgos Críticos / Alto Riesgo", level=2)
        _add_table(doc, alerts)
    else:
        doc.add_paragraph("No se encontraron vulnerabilidades críticas ni de alto riesgo.")

    # ------------------------------------------------------------------ #
    # Anexo completo (opcional)
    # ------------------------------------------------------------------ #
    _add_heading(doc, "Anexo – Lista completa de hallazgos", level=2)
    for entry in report_json.get("results", []):
        file_path = entry.get("file", "")
        for issue in entry.get("issues", []):
            p = doc.add_paragraph()
            run_title = p.add_run(f"[{issue.get('severity')}] {issue.get('id')} – ")
            run_title.bold = True
            p.add_run(f"{issue.get('title')} ({file_path}:{issue.get('line')})")

    out_path = pathlib.Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(out_path))
    log.info(f"Reporte Word exportado en: {out_path}")


def _serialize_value(value: Any) -> Any:
    """Convierte objetos Pydantic, enums, datetimes o sets en estructuras JSON-seguras."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "value") and isinstance(getattr(value, "value"), str):
        return value.value
    if hasattr(value, "model_dump"):
        return _serialize_value(value.model_dump(mode="json"))
    if isinstance(value, dict):
        return {str(k): _serialize_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_serialize_value(item) for item in value]
    return str(value)


def _normalize_envelope(envelope: Any) -> Dict[str, Any]:
    """Normaliza un AuditFindingEnvelope o dict manteniendo separadas evidencia y triaje."""
    raw = _serialize_value(envelope)
    if not isinstance(raw, dict):
        raw = {"validated_evidence": {"raw_excerpt": str(raw)}, "llm_triage": None}

    evidence = raw.get("validated_evidence") or {}
    triage = raw.get("llm_triage")

    return {
        "finding_id": raw.get("finding_id"),
        "governance_state": {
            "scope_verified": bool(raw.get("scope_verified", False)),
            "human_approved": bool(raw.get("human_approved", False)),
            "approved_by": raw.get("approved_by"),
        },
        "validated_evidence": {
            "source_tool": evidence.get("source_tool"),
            "target": evidence.get("target"),
            "port": evidence.get("port"),
            "protocol": evidence.get("protocol"),
            "observed_at": evidence.get("observed_at"),
            "evidence_sha256": evidence.get("evidence_sha256"),
            "raw_excerpt": evidence.get("raw_excerpt"),
            "observed_data": evidence.get("observed_data") or {},
        },
        "llm_triage": (
            {
                "model_name": triage.get("model_name"),
                "is_experimental_hypothesis": bool(
                    triage.get("is_experimental_hypothesis", True)
                ),
                "risk_priority": triage.get("risk_priority", "info"),
                "summary": triage.get("summary"),
                "rationale": triage.get("rationale"),
                "recommended_next_step": triage.get("recommended_next_step"),
                "caveats": triage.get("caveats") or [],
            }
            if isinstance(triage, dict)
            else None
        ),
    }


def _normalize_audit_record(record: Any) -> Dict[str, Any]:
    """Normaliza un AuditRecord o dict para el rastro de auditoría."""
    raw = _serialize_value(record)
    if not isinstance(raw, dict):
        return {"raw_record": str(raw)}

    decision = raw.get("decision") or {}
    return {
        "record_id": raw.get("record_id"),
        "timestamp": raw.get("timestamp"),
        "event_type": raw.get("event_type"),
        "actor": raw.get("actor"),
        "target": raw.get("target"),
        "decision": (
            {
                "allowed": decision.get("allowed"),
                "code": decision.get("code"),
                "reason": decision.get("reason"),
                "requires_human_approval": decision.get("requires_human_approval"),
                "approval_request_id": decision.get("approval_request_id"),
            }
            if isinstance(decision, dict) and decision
            else None
        ),
        "details": raw.get("details") or {},
    }


class AuditReportExporter:
    """Exporta reportes con separación estricta de evidencia y rastro de auditoría."""

    def __init__(
        self,
        tool_name: str = "ATOMUM",
        tool_version: str = "v3.0-devsecops",
    ) -> None:
        self.tool_name = tool_name
        self.tool_version = tool_version

    def build_report_payload(
        self,
        envelopes: List[Any],
        audit_log: Optional[List[Any]] = None,
        emergency_stop_status: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        normalized_findings = [_normalize_envelope(env) for env in (envelopes or [])]
        normalized_audit = [_normalize_audit_record(rec) for rec in (audit_log or [])]

        return {
            "report_metadata": {
                "generator": self.tool_name,
                "version": self.tool_version,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "total_findings": len(normalized_findings),
                "total_audit_events": len(normalized_audit),
                "extra": _serialize_value(metadata or {}),
            },
            "governance_summary": {
                "emergency_stop": _serialize_value(emergency_stop_status or {}),
                "findings_requiring_review": sum(
                    1
                    for f in normalized_findings
                    if f["llm_triage"] is not None
                    and not f["governance_state"]["human_approved"]
                ),
            },
            "findings": normalized_findings,
            "audit_trail": normalized_audit,
        }

    def to_json(
        self,
        envelopes: List[Any],
        audit_log: Optional[List[Any]] = None,
        emergency_stop_status: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        indent: int = 2,
    ) -> str:
        payload = self.build_report_payload(
            envelopes=envelopes,
            audit_log=audit_log,
            emergency_stop_status=emergency_stop_status,
            metadata=metadata,
        )
        return json.dumps(payload, indent=indent, ensure_ascii=False)

    def to_markdown(
        self,
        envelopes: List[Any],
        audit_log: Optional[List[Any]] = None,
        emergency_stop_status: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        payload = self.build_report_payload(
            envelopes=envelopes,
            audit_log=audit_log,
            emergency_stop_status=emergency_stop_status,
            metadata=metadata,
        )
        meta = payload["report_metadata"]
        estop = payload["governance_summary"]["emergency_stop"]

        lines: List[str] = [
            f"# Reporte de Auditoría y Hallazgos — {meta['generator']} ({meta['version']})",
            "",
            f"- **Generado (UTC):** {meta['generated_at']}",
            f"- **Total de sobres de hallazgos:** {meta['total_findings']}",
            f"- **Eventos en rastro de auditoría:** {meta['total_audit_events']}",
            f"- **EmergencyStop activo:** {estop.get('triggered', False)}"
            + (f" ({estop.get('reason')})" if estop.get("reason") else ""),
            "",
            "## 1. Hallazgos (Evidencia Validada separada de Triaje LLM)",
            "",
        ]

        if not payload["findings"]:
            lines.append("_No se registraron sobres de hallazgos en esta ejecución._")
            lines.append("")
        else:
            for idx, item in enumerate(payload["findings"], start=1):
                ev = item["validated_evidence"]
                tr = item["llm_triage"]
                gov = item["governance_state"]

                lines.extend(
                    [
                        f"### Hallazgo {idx}: `{ev.get('target')}`"
                        + (f":{ev.get('port')}" if ev.get("port") is not None else ""),
                        f"- **Scope verificado:** `{gov.get('scope_verified')}` | "
                        f"**Aprobación humana:** `{gov.get('human_approved')}`",
                        "#### Evidencia Técnica Observada (`validated_evidence`)",
                        f"- **Herramienta:** `{ev.get('source_tool')}` | **Protocolo:** `{ev.get('protocol')}`",
                        f"- **SHA-256 de evidencia:** `{ev.get('evidence_sha256')}`",
                        f"- **Observado en:** `{ev.get('observed_at')}`",
                        f"- **Datos observados:** `{json.dumps(ev.get('observed_data', {}), ensure_ascii=False)}`",
                    ]
                )
                if ev.get("raw_excerpt"):
                    lines.append(f"- **Extracto crudo:** `{ev.get('raw_excerpt')}`")

                lines.append("#### Hipótesis y Triaje del Modelo (`llm_triage`)")
                if tr is None:
                    lines.append("- _Sin triaje LLM asociado._")
                else:
                    lines.extend(
                        [
                            f"- **Modelo:** `{tr.get('model_name')}` | "
                            f"**Prioridad hipotética:** `{tr.get('risk_priority')}` | "
                            f"**Hipótesis experimental:** `{tr.get('is_experimental_hypothesis')}`",
                            f"- **Resumen:** {tr.get('summary')}",
                            f"- **Justificación:** {tr.get('rationale')}",
                            f"- **Próximo paso sugerido:** {tr.get('recommended_next_step')}",
                        ]
                    )
                lines.append("")

        lines.extend(["## 2. Rastro de Auditoría (`audit_trail`)", ""])
        if not payload["audit_trail"]:
            lines.append("_Sin eventos de auditoría registrados._")
        else:
            for rec in payload["audit_trail"]:
                dec = rec.get("decision") or {}
                dec_txt = (
                    f" -> `{dec.get('code')}` (allowed=`{dec.get('allowed')}`): {dec.get('reason')}"
                    if dec
                    else ""
                )
                lines.append(
                    f"- `[{rec.get('timestamp')}]` **{rec.get('event_type')}** "
                    f"(actor: `{rec.get('actor')}`, target: `{rec.get('target')}`){dec_txt}"
                )

        return "\n".join(lines).strip() + "\n"

    def export_file(
        self,
        output_path: Union[str, Path],
        envelopes: List[Any],
        audit_log: Optional[List[Any]] = None,
        emergency_stop_status: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        fmt: str = "json",
    ) -> pathlib.Path:
        path = pathlib.Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        fmt_clean = fmt.lower().strip()

        if fmt_clean == "json":
            content = self.to_json(
                envelopes=envelopes,
                audit_log=audit_log,
                emergency_stop_status=emergency_stop_status,
                metadata=metadata,
            )
        elif fmt_clean in {"md", "markdown"}:
            content = self.to_markdown(
                envelopes=envelopes,
                audit_log=audit_log,
                emergency_stop_status=emergency_stop_status,
                metadata=metadata,
            )
        else:
            raise ValueError(
                f"Formato de exportación no soportado: '{fmt}'. Use 'json' o 'markdown'."
            )

        path.write_text(content, encoding="utf-8")
        return path
