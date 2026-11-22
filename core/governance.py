from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
import hashlib
import ipaddress
import re
from threading import Lock
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


class ActionImpact(str, Enum):
    READ_ONLY = "read_only"
    ACTIVE_PROBE = "active_probe"
    STATE_MUTATION = "state_mutation"
    PR_CREATION = "pr_creation"


class ScopePolicy(BaseModel):
    allowed_ips: set[str] = Field(default_factory=set)
    allowed_cidrs: list[str] = Field(default_factory=list)
    allowed_domains: list[str] = Field(default_factory=list)
    allowed_ports: set[int] = Field(default_factory=lambda: {80, 443, 8080, 8443})
    allow_loopback_and_private: bool = False
    max_steps: int = 25
    max_out_of_scope_attempts: int = 2
    max_consecutive_errors: int = 4

    @field_validator("allowed_ports")
    @classmethod
    def validate_ports(cls, ports: set[int]) -> set[int]:
        for p in ports:
            if not (1 <= p <= 65535):
                raise ValueError(f"Puerto fuera de rango válido: {p}")
        return ports


class GovernanceDecision(BaseModel):
    allowed: bool
    code: str
    reason: str
    requires_human_approval: bool = False
    approval_request_id: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ValidatedEvidence(BaseModel):
    """Evidencia técnica observada directamente por herramientas/red (no generada por LLM)."""

    source_tool: str
    target: str
    port: int | None = None
    protocol: str | None = None
    observed_data: dict[str, Any] = Field(default_factory=dict)
    raw_excerpt: str | None = None
    evidence_sha256: str = ""
    observed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def model_post_init(self, __context: Any) -> None:
        if not self.evidence_sha256:
            payload = (
                f"{self.source_tool}|{self.target}|{self.port}|{self.protocol}|"
                f"{self.raw_excerpt or ''}|{sorted(self.observed_data.items())}"
            )
            self.evidence_sha256 = hashlib.sha256(payload.encode("utf-8")).hexdigest()


class LLMTriage(BaseModel):
    """Análisis, hipótesis y priorización producidos por el modelo (requiere validación)."""

    model_name: str
    is_experimental_hypothesis: bool = True
    risk_priority: Literal["info", "low", "medium", "high", "critical"] = "info"
    summary: str
    rationale: str
    recommended_next_step: str
    caveats: list[str] = Field(
        default_factory=lambda: ["Triaje generado por LLM: validar contra evidencia técnica y alcance."]
    )


class AuditRecord(BaseModel):
    record_id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    event_type: str
    actor: str
    target: str | None = None
    decision: GovernanceDecision | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class AuditFindingEnvelope(BaseModel):
    finding_id: str = Field(default_factory=lambda: str(uuid4()))
    scope_verified: bool
    validated_evidence: ValidatedEvidence
    llm_triage: LLMTriage | None = None
    human_approved: bool = False
    approved_by: str | None = None


class EmergencyStop:
    """Corte duro de ejecución ante anomalías, exceso de pasos o señales de abuso."""

    _INJECTION_PATTERNS = [
        re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.IGNORECASE),
        re.compile(r"override\s+(scope|guardrail|constitution|kill\s*switch)", re.IGNORECASE),
        re.compile(r"(dump|exfiltrate|print)\s+(env|secrets|api_key|token|credentials)", re.IGNORECASE),
    ]

    def __init__(self, policy: ScopePolicy) -> None:
        self._policy = policy
        self._lock = Lock()
        self._triggered = False
        self._reason: str | None = None
        self._triggered_at: datetime | None = None
        self._steps = 0
        self._out_of_scope_count = 0
        self._error_count = 0

    @property
    def is_triggered(self) -> bool:
        with self._lock:
            return self._triggered

    @property
    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "triggered": self._triggered,
                "reason": self._reason,
                "triggered_at": self._triggered_at.isoformat() if self._triggered_at else None,
                "steps": self._steps,
                "out_of_scope_count": self._out_of_scope_count,
                "error_count": self._error_count,
            }

    def trip(self, reason: str) -> None:
        with self._lock:
            if not self._triggered:
                self._triggered = True
                self._reason = reason
                self._triggered_at = datetime.now(timezone.utc)

    def reset(self, operator_note: str) -> None:
        with self._lock:
            if not operator_note.strip():
                raise ValueError("Se requiere un motivo explícito para rearmar tras EmergencyStop.")
            self._triggered = False
            self._reason = None
            self._triggered_at = None
            self._steps = 0
            self._out_of_scope_count = 0
            self._error_count = 0

    def record_step(self) -> None:
        with self._lock:
            self._steps += 1
            if self._steps > self._policy.max_steps:
                self._triggered = True
                self._reason = f"Límite máximo de pasos excedido ({self._policy.max_steps})."
                self._triggered_at = datetime.now(timezone.utc)

    def record_out_of_scope(self) -> None:
        with self._lock:
            self._out_of_scope_count += 1
            if self._out_of_scope_count >= self._policy.max_out_of_scope_attempts:
                self._triggered = True
                self._reason = (
                    f"Umbral de intentos fuera de scope alcanzado ({self._out_of_scope_count})."
                )
                self._triggered_at = datetime.now(timezone.utc)

    def record_error(self, is_error: bool) -> None:
        with self._lock:
            if not is_error:
                self._error_count = 0
                return
            self._error_count += 1
            if self._error_count >= self._policy.max_consecutive_errors:
                self._triggered = True
                self._reason = (
                    f"Demasiados errores consecutivos ({self._error_count})."
                )
                self._triggered_at = datetime.now(timezone.utc)

    def inspect_text_for_injection(self, text: str | None) -> str | None:
        if not text:
            return None
        for pattern in self._INJECTION_PATTERNS:
            if pattern.search(text):
                reason = f"Patrón sospechoso de prompt injection/override detectado: {pattern.pattern}"
                self.trip(reason)
                return reason
        return None


class ScopeGuard:
    """Validador determinista de objetivos (IP, CIDR, dominio) y puertos."""

    def __init__(self, policy: ScopePolicy) -> None:
        self.policy = policy
        self._cidrs = [ipaddress.ip_network(c, strict=False) for c in policy.allowed_cidrs]
        self._domains = [d.lower().lstrip("*.") for d in policy.allowed_domains]

    def _ip_allowed(self, ip_obj: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
        if not self.policy.allow_loopback_and_private and (ip_obj.is_private or ip_obj.is_loopback):
            return False
        if str(ip_obj) in self.policy.allowed_ips:
            return True
        return any(ip_obj in net for net in self._cidrs)

    def _domain_allowed(self, host: str) -> bool:
        h = host.lower().rstrip(".")
        return any(h == dom or h.endswith(f".{dom}") for dom in self._domains)

    def check_target(
        self,
        host: str,
        port: int | None = None,
        resolved_ips: list[str] | None = None,
    ) -> GovernanceDecision:
        if port is not None and port not in self.policy.allowed_ports:
            return GovernanceDecision(
                allowed=False,
                code="PORT_OUT_OF_SCOPE",
                reason=f"Puerto {port} no autorizado en la política actual.",
            )

        clean_host = host.strip()
        try:
            ip_obj = ipaddress.ip_address(clean_host)
            if not self._ip_allowed(ip_obj):
                return GovernanceDecision(
                    allowed=False,
                    code="IP_OUT_OF_SCOPE",
                    reason=f"IP {clean_host} fuera del alcance permitido.",
                )
        except ValueError:
            if not self._domain_allowed(clean_host):
                return GovernanceDecision(
                    allowed=False,
                    code="DOMAIN_OUT_OF_SCOPE",
                    reason=f"Dominio '{clean_host}' fuera del alcance permitido.",
                )

        if resolved_ips:
            for raw_ip in resolved_ips:
                try:
                    rip = ipaddress.ip_address(raw_ip)
                    if not self._ip_allowed(rip):
                        return GovernanceDecision(
                            allowed=False,
                            code="RESOLVED_IP_OUT_OF_SCOPE",
                            reason=f"IP resuelta {raw_ip} para '{clean_host}' viola el scope.",
                        )
                except ValueError:
                    continue

        return GovernanceDecision(
            allowed=True,
            code="SCOPE_OK",
            reason="Objetivo y puerto dentro del alcance autorizado.",
        )


class HumanApprovalGate:
    """Puerta de revisión humana para acciones con impacto en estado, red activa o PRs."""

    def __init__(self, required_impacts: set[ActionImpact] | None = None) -> None:
        self.required_impacts = required_impacts or {
            ActionImpact.STATE_MUTATION,
            ActionImpact.PR_CREATION,
        }
        self._lock = Lock()
        self._requests: dict[str, dict[str, Any]] = {}

    def evaluate(
        self,
        action_name: str,
        impact: ActionImpact,
        target: str,
        context: dict[str, Any] | None = None,
    ) -> GovernanceDecision:
        if impact not in self.required_impacts:
            return GovernanceDecision(
                allowed=True,
                code="AUTO_PERMITTED",
                reason=f"Impacto '{impact.value}' permitido sin bloqueo manual.",
            )

        req_id = str(uuid4())
        with self._lock:
            self._requests[req_id] = {
                "request_id": req_id,
                "action_name": action_name,
                "impact": impact.value,
                "target": target,
                "context": context or {},
                "status": "pending",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "approved_by": None,
            }

        return GovernanceDecision(
            allowed=False,
            code="HUMAN_APPROVAL_REQUIRED",
            reason=f"Acción '{action_name}' ({impact.value}) requiere aprobación humana.",
            requires_human_approval=True,
            approval_request_id=req_id,
        )

    def approve(self, request_id: str, approver: str) -> bool:
        with self._lock:
            req = self._requests.get(request_id)
            if not req or req["status"] != "pending":
                return False
            req["status"] = "approved"
            req["approved_by"] = approver
            req["approved_at"] = datetime.now(timezone.utc).isoformat()
            return True

    def is_approved(self, request_id: str | None) -> bool:
        if not request_id:
            return False
        with self._lock:
            req = self._requests.get(request_id)
            return bool(req and req["status"] == "approved")


class GovernanceController:
    """Orquestador unificado de contención y auditoría para el motor de ATOMUM."""

    def __init__(self, policy: ScopePolicy) -> None:
        self.policy = policy
        self.scope_guard = ScopeGuard(policy)
        self.emergency_stop = EmergencyStop(policy)
        self.approval_gate = HumanApprovalGate()
        self.audit_log: list[AuditRecord] = []

    def _log(self, event_type: str, actor: str, target: str | None, decision: GovernanceDecision | None, details: dict[str, Any] | None = None) -> None:
        self.audit_log.append(
            AuditRecord(
                event_type=event_type,
                actor=actor,
                target=target,
                decision=decision,
                details=details or {},
            )
        )

    def authorize_action(
        self,
        actor: str,
        action_name: str,
        impact: ActionImpact,
        host: str,
        port: int | None = None,
        resolved_ips: list[str] | None = None,
        untrusted_text: str | None = None,
        approval_request_id: str | None = None,
    ) -> GovernanceDecision:
        if self.emergency_stop.is_triggered:
            dec = GovernanceDecision(
                allowed=False,
                code="EMERGENCY_STOP_ACTIVE",
                reason=f"Ejecución detenida por EmergencyStop: {self.emergency_stop.status['reason']}",
            )
            self._log("action_blocked", actor, host, dec)
            return dec

        injection_hit = self.emergency_stop.inspect_text_for_injection(untrusted_text)
        if injection_hit:
            dec = GovernanceDecision(
                allowed=False,
                code="PROMPT_INJECTION_HALT",
                reason=injection_hit,
            )
            self._log("emergency_stop_tripped", actor, host, dec)
            return dec

        self.emergency_stop.record_step()
        if self.emergency_stop.is_triggered:
            dec = GovernanceDecision(
                allowed=False,
                code="MAX_STEPS_HALT",
                reason=self.emergency_stop.status["reason"] or "Límite de pasos alcanzado.",
            )
            self._log("emergency_stop_tripped", actor, host, dec)
            return dec

        scope_dec = self.scope_guard.check_target(host=host, port=port, resolved_ips=resolved_ips)
        if not scope_dec.allowed:
            self.emergency_stop.record_out_of_scope()
            self._log(
                "scope_violation",
                actor,
                host,
                scope_dec,
                details={"emergency_status": self.emergency_stop.status},
            )
            return scope_dec

        if approval_request_id and self.approval_gate.is_approved(approval_request_id):
            dec = GovernanceDecision(
                allowed=True,
                code="HUMAN_APPROVED",
                reason="Acción aprobada explícitamente por revisor humano.",
                approval_request_id=approval_request_id,
            )
            self._log("action_approved", actor, host, dec)
            return dec

        gate_dec = self.approval_gate.evaluate(
            action_name=action_name,
            impact=impact,
            target=host,
            context={"port": port},
        )
        self._log("action_evaluated", actor, host, gate_dec, details={"action": action_name})
        return gate_dec
