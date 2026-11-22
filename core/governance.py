"""
core/governance.py
--------------------
Capa de gobernanza, control de alcance, parada de emergencia,
aprobación humana y registro de auditoría inmutable para ATOMUM.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import ipaddress
import json
import threading
from typing import Any, Literal
import uuid

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ScopePolicy(BaseModel):
    """Política declarativa de alcance autorizado y límites operativos."""

    allowed_domains: list[str] = Field(default_factory=list)
    allowed_cidrs: list[str] = Field(default_factory=list)
    allowed_ports: list[int] = Field(default_factory=lambda: [80, 443, 8080, 8443])
    denied_hosts: list[str] = Field(default_factory=list)
    require_human_approval_for: list[str] = Field(
        default_factory=lambda: [
            "exploit_verification",
            "credential_test",
            "state_mutation",
            "write_action",
        ]
    )
    max_steps: int = Field(default=50, ge=1)
    max_consecutive_errors: int = Field(default=4, ge=1)
    max_runtime_seconds: int = Field(default=900, ge=1)


class GovernanceDecision(BaseModel):
    """Decisión formal emitida por el controlador de gobernanza."""

    allowed: bool
    reason: str
    requires_human_approval: bool = False
    approval_request_id: str | None = None
    halt_triggered: bool = False
    timestamp: datetime = Field(default_factory=_utcnow)


class ValidatedEvidence(BaseModel):
    """Evidencia técnica validada y sellada con hash SHA-256 determinista."""

    source_tool: str
    target: str
    command_or_query: str
    observed_data: dict[str, Any] = Field(default_factory=dict)
    raw_excerpt: str = ""
    evidence_sha256: str = ""
    collected_at: datetime = Field(default_factory=_utcnow)

    def model_post_init(self, __context: Any) -> None:
        if not self.evidence_sha256:
            canonical = json.dumps(
                {
                    "source_tool": self.source_tool,
                    "target": self.target,
                    "command_or_query": self.command_or_query,
                    "observed_data": self.observed_data,
                    "raw_excerpt": self.raw_excerpt,
                },
                sort_keys=True,
                separators=(",", ":"),
                default=str,
            )
            self.evidence_sha256 = hashlib.sha256(
                canonical.encode("utf-8")
            ).hexdigest()


class LLMTriage(BaseModel):
    """Clasificación y análisis estructurado producido por el modelo."""

    summary: str
    severity: Literal["critical", "high", "medium", "low", "info"] = "info"
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    recommended_next_step: str = ""
    hallucination_risk_notes: list[str] = Field(default_factory=list)


class AuditRecord(BaseModel):
    """Entrada inmutable del registro de auditoría del sistema."""

    record_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=_utcnow)
    event_type: str
    actor: str
    target: str | None = None
    action: str | None = None
    outcome: Literal["allowed", "blocked", "pending_approval", "halted", "recorded"]
    details: dict[str, Any] = Field(default_factory=dict)


class AuditFindingEnvelope(BaseModel):
    """Envoltorio completo que vincula evidencia verificada con triaje LLM."""

    finding_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    evidence: ValidatedEvidence
    triage: LLMTriage
    human_verified: bool = False
    verified_by: str | None = None
    created_at: datetime = Field(default_factory=_utcnow)


class EmergencyStop:
    """Cortocircuito de seguridad hilo-seguro por pasos, errores o tiempo."""

    def __init__(
        self,
        max_steps: int = 50,
        max_consecutive_errors: int = 4,
        max_runtime_seconds: int = 900,
    ) -> None:
        self._lock = threading.Lock()
        self.max_steps = max_steps
        self.max_consecutive_errors = max_consecutive_errors
        self.max_runtime_seconds = max_runtime_seconds
        self.started_at = _utcnow()
        self.steps_taken = 0
        self.consecutive_errors = 0
        self.halted = False
        self.halt_reason: str | None = None

    def trigger(self, reason: str) -> None:
        with self._lock:
            if not self.halted:
                self.halted = True
                self.halt_reason = reason

    def reset(self) -> None:
        with self._lock:
            self.started_at = _utcnow()
            self.steps_taken = 0
            self.consecutive_errors = 0
            self.halted = False
            self.halt_reason = None

    def record_step(self) -> tuple[bool, str | None]:
        with self._lock:
            if self.halted:
                return False, self.halt_reason

            elapsed = (_utcnow() - self.started_at).total_seconds()
            if elapsed > self.max_runtime_seconds:
                self.halted = True
                self.halt_reason = (
                    f"Tiempo máximo de ejecución excedido ({self.max_runtime_seconds}s)"
                )
                return False, self.halt_reason

            self.steps_taken += 1
            if self.steps_taken > self.max_steps:
                self.halted = True
                self.halt_reason = f"Límite de pasos excedido ({self.max_steps})"
                return False, self.halt_reason

            return True, None

    def record_error(self, is_error: bool) -> tuple[bool, str | None]:
        with self._lock:
            if self.halted:
                return False, self.halt_reason

            if is_error:
                self.consecutive_errors += 1
                if self.consecutive_errors >= self.max_consecutive_errors:
                    self.halted = True
                    self.halt_reason = (
                        f"Límite de errores consecutivos alcanzado ({self.max_consecutive_errors})"
                    )
                    return False, self.halt_reason
            else:
                self.consecutive_errors = 0

            return True, None

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "halted": self.halted,
                "halt_reason": self.halt_reason,
                "steps_taken": self.steps_taken,
                "max_steps": self.max_steps,
                "consecutive_errors": self.consecutive_errors,
                "max_consecutive_errors": self.max_consecutive_errors,
                "elapsed_seconds": round((_utcnow() - self.started_at).total_seconds(), 2),
                "max_runtime_seconds": self.max_runtime_seconds,
            }


class ScopeGuard:
    """Valida hosts, direcciones IP/CIDR y puertos contra una ScopePolicy."""

    def __init__(self, policy: ScopePolicy) -> None:
        self.policy = policy
        self._domains: list[str] = []
        for raw_domain in policy.allowed_domains:
            cleaned = raw_domain.strip().lower().lstrip("*").lstrip(".")
            if cleaned:
                self._domains.append(cleaned)

        self._denied_hosts: set[str] = {
            h.strip().lower() for h in policy.denied_hosts if h.strip()
        }
        self._networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = [
            ipaddress.ip_network(cidr, strict=False) for cidr in policy.allowed_cidrs
        ]

    @staticmethod
    def _parse_ip(candidate: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
        cleaned = candidate.strip().split("%", 1)[0]
        try:
            return ipaddress.ip_address(cleaned)
        except ValueError:
            return None

    def _host_allowed(self, host: str) -> bool:
        normalized_host = host.strip().lower().rstrip(".")
        if not normalized_host or normalized_host in self._denied_hosts:
            return False

        ip_obj = self._parse_ip(normalized_host)
        if ip_obj is not None:
            return any(ip_obj in net for net in self._networks)

        return any(
            normalized_host == domain or normalized_host.endswith(f".{domain}")
            for domain in self._domains
        )

    def _ips_allowed(self, resolved_ips: list[str] | None) -> tuple[bool, str | None]:
        if not resolved_ips:
            return True, None

        for raw_ip in resolved_ips:
            ip_obj = self._parse_ip(raw_ip)
            if ip_obj is None:
                return False, f"IP resuelta inválida: {raw_ip}"
            if raw_ip.strip().lower() in self._denied_hosts:
                return False, f"IP resuelta en lista denegada: {raw_ip}"
            if self._networks and not any(ip_obj in net for net in self._networks):
                return False, f"IP resuelta fuera de CIDR permitido: {raw_ip}"

        return True, None

    def check_target(
        self,
        host: str,
        port: int | None = None,
        resolved_ips: list[str] | None = None,
    ) -> tuple[bool, str]:
        if not self._host_allowed(host):
            return False, f"Objetivo '{host}' fuera de alcance o denegado"

        if port is not None and self.policy.allowed_ports:
            if port not in self.policy.allowed_ports:
                return False, f"Puerto {port} no autorizado por política"

        ips_ok, ip_reason = self._ips_allowed(resolved_ips)
        if not ips_ok:
            return False, ip_reason or "IP resuelta fuera de alcance"

        return True, "Objetivo dentro del alcance autorizado"


class HumanApprovalGate:
    """Gestiona solicitudes de aprobación humana para acciones sensibles."""

    def __init__(self, required_actions: list[str] | None = None) -> None:
        self._lock = threading.Lock()
        self.required_actions: set[str] = set(
            required_actions
            or [
                "exploit_verification",
                "credential_test",
                "state_mutation",
                "write_action",
            ]
        )
        self._requests: dict[str, dict[str, Any]] = {}

    def requires_approval(self, action_type: str) -> bool:
        return action_type in self.required_actions

    def create_request(
        self,
        action_type: str,
        target: str,
        rationale: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        req_id = str(uuid.uuid4())
        with self._lock:
            self._requests[req_id] = {
                "request_id": req_id,
                "action_type": action_type,
                "target": target,
                "rationale": rationale,
                "metadata": dict(metadata or {}),
                "status": "pending",
                "approved_by": None,
                "created_at": _utcnow().isoformat(),
                "decided_at": None,
            }
        return req_id

    def approve(self, request_id: str, approver: str) -> bool:
        with self._lock:
            req = self._requests.get(request_id)
            if not req:
                return False
            req["status"] = "approved"
            req["approved_by"] = approver
            req["decided_at"] = _utcnow().isoformat()
            return True

    def is_approved(self, request_id: str | None) -> bool:
        if not request_id:
            return False
        with self._lock:
            req = self._requests.get(request_id)
            return bool(req and req.get("status") == "approved")

    def get_request(self, request_id: str) -> dict[str, Any] | None:
        with self._lock:
            req = self._requests.get(request_id)
            return dict(req) if req else None

    def pending_requests(self) -> list[dict[str, Any]]:
        with self._lock:
            return [
                dict(req)
                for req in self._requests.values()
                if req.get("status") == "pending"
            ]


class GovernanceController:
    """Coordina alcance, parada de emergencia, aprobación humana y auditoría."""

    def __init__(self, policy: ScopePolicy) -> None:
        self.policy = policy
        self.scope_guard = ScopeGuard(policy)
        self.emergency_stop = EmergencyStop(
            max_steps=policy.max_steps,
            max_consecutive_errors=policy.max_consecutive_errors,
            max_runtime_seconds=policy.max_runtime_seconds,
        )
        self.approval_gate = HumanApprovalGate(
            required_actions=policy.require_human_approval_for
        )
        self._lock = threading.Lock()
        self.audit_log: list[AuditRecord] = []

    def _record(
        self,
        event_type: str,
        actor: str,
        outcome: Literal["allowed", "blocked", "pending_approval", "halted", "recorded"],
        target: str | None = None,
        action: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> AuditRecord:
        rec = AuditRecord(
            event_type=event_type,
            actor=actor,
            target=target,
            action=action,
            outcome=outcome,
            details=details or {},
        )
        with self._lock:
            self.audit_log.append(rec)
        return rec

    def authorize_action(
        self,
        actor: str,
        action_type: str,
        target: str,
        port: int | None = None,
        resolved_ips: list[str] | None = None,
        approval_request_id: str | None = None,
        rationale: str = "",
    ) -> GovernanceDecision:
        step_ok, halt_reason = self.emergency_stop.record_step()
        if not step_ok:
            self._record(
                event_type="emergency_stop",
                actor=actor,
                target=target,
                action=action_type,
                outcome="halted",
                details={"reason": halt_reason},
            )
            return GovernanceDecision(
                allowed=False,
                reason=halt_reason or "Ejecución detenida por parada de emergencia",
                halt_triggered=True,
            )

        scope_ok, scope_reason = self.scope_guard.check_target(
            host=target,
            port=port,
            resolved_ips=resolved_ips,
        )
        if not scope_ok:
            self._record(
                event_type="scope_check",
                actor=actor,
                target=target,
                action=action_type,
                outcome="blocked",
                details={"reason": scope_reason, "port": port},
            )
            return GovernanceDecision(allowed=False, reason=scope_reason)

        if self.approval_gate.requires_approval(action_type):
            if not self.approval_gate.is_approved(approval_request_id):
                req_id = approval_request_id or self.approval_gate.create_request(
                    action_type=action_type,
                    target=target,
                    rationale=rationale or f"Acción '{action_type}' en '{target}'",
                    metadata={"port": port, "actor": actor},
                )
                self._record(
                    event_type="human_approval",
                    actor=actor,
                    target=target,
                    action=action_type,
                    outcome="pending_approval",
                    details={"approval_request_id": req_id},
                )
                return GovernanceDecision(
                    allowed=False,
                    reason="Se requiere aprobación humana explícita antes de ejecutar",
                    requires_human_approval=True,
                    approval_request_id=req_id,
                )

        self._record(
            event_type="action_authorization",
            actor=actor,
            target=target,
            action=action_type,
            outcome="allowed",
            details={"port": port, "approval_request_id": approval_request_id},
        )
        return GovernanceDecision(
            allowed=True,
            reason="Acción autorizada bajo política de gobernanza",
            approval_request_id=approval_request_id,
        )

    def record_execution_result(
        self,
        actor: str,
        action_type: str,
        target: str,
        success: bool,
        error_detail: str | None = None,
    ) -> tuple[bool, str | None]:
        """Registra el resultado de una acción ejecutada y evalúa parada por errores."""
        ok, halt_reason = self.emergency_stop.record_error(is_error=not success)
        details: dict[str, Any] = {"success": success}
        if error_detail:
            details["error"] = error_detail
        if halt_reason:
            details["halt_reason"] = halt_reason

        self._record(
            event_type="execution_outcome",
            actor=actor,
            target=target,
            action=action_type,
            outcome="halted" if not ok else "recorded",
            details=details,
        )
        return ok, halt_reason

    def export_audit_log_json(self) -> str:
        with self._lock:
            return json.dumps(
                [r.model_dump(mode="json") for r in self.audit_log],
                indent=2,
            )
