from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Protocol

from core.governance import (
    ActionImpact,
    GovernanceController,
    GovernanceDecision,
)
from core.guardrails import validate_user_code


class PullRequestClient(Protocol):
    """Adaptador para crear un Pull Request en VCS (GitHub API, Git CLI, etc.)."""

    def create_pull_request(
        self,
        repo: str,
        head_branch: str,
        base_branch: str,
        title: str,
        body: str,
    ) -> Dict[str, Any]:
        ...


@dataclass
class PRGuardResult:
    created: bool
    status: str
    decision: GovernanceDecision
    pr_info: Optional[Dict[str, Any]] = None
    error_code: Optional[str] = None


class ProtectedPullRequestWorkflow:
    """Coordina validación previa, HumanApprovalGate y creación de PR con ActionImpact.PR_CREATION."""

    def __init__(
        self,
        governance: GovernanceController,
        pr_client: PullRequestClient,
        approval_callback: Optional[Callable[[GovernanceDecision], bool]] = None,
    ) -> None:
        self.governance = governance
        self.pr_client = pr_client
        self.approval_callback = approval_callback

    @staticmethod
    def _resolve_target_host(repo: str) -> str:
        cleaned = repo.strip()
        if not cleaned:
            return "github.com"
        if "/" in cleaned and not cleaned.startswith("http"):
            # Si viene en formato "org/repo", el host de gobernanza es github.com
            return "github.com"
        return cleaned

    def _validate_candidate_patch(
        self,
        actor: str,
        repo: str,
        candidate_python_code: Optional[str],
    ) -> Optional[GovernanceDecision]:
        if not candidate_python_code:
            return None
        try:
            validate_user_code(candidate_python_code)
            return None
        except Exception as exc:
            reason = f"Código candidato rechazado antes de solicitar PR: {exc}"
            denied = GovernanceDecision(
                allowed=False,
                reason=reason,
            )
            self.governance._record(
                event_type="pr_patch_rejected",
                actor=actor,
                target=repo,
                action=ActionImpact.PR_CREATION.value,
                outcome="blocked",
                details={"code": "PR_PATCH_AST_INVALID", "reason": reason},
            )
            return denied

    def request_and_create_pr(
        self,
        actor: str,
        repo: str,
        head_branch: str,
        base_branch: str,
        title: str,
        body: str,
        candidate_python_code: Optional[str] = None,
        approver: str = "human_reviewer",
    ) -> PRGuardResult:
        target_host = self._resolve_target_host(repo)

        if self.governance.emergency_stop.halted:
            status_info = self.governance.emergency_stop.status()
            reason = (
                status_info.get("halt_reason")
                or status_info.get("reason")
                or self.governance.emergency_stop.halt_reason
                or "Parada activa"
            )
            blocked_reason = f"Creación de PR bloqueada por EmergencyStop: {reason}"
            blocked = GovernanceDecision(
                allowed=False,
                reason=blocked_reason,
                halt_triggered=True,
            )
            self.governance._record(
                event_type="pr_blocked_emergency_stop",
                actor=actor,
                target=target_host,
                action=ActionImpact.PR_CREATION.value,
                outcome="halted",
                details={"code": "EMERGENCY_STOP_ACTIVE", "repo": repo, "reason": blocked_reason},
            )
            return PRGuardResult(
                created=False,
                status="blocked_emergency_stop",
                decision=blocked,
                error_code="EMERGENCY_STOP_ACTIVE",
            )

        ast_rejection = self._validate_candidate_patch(
            actor=actor,
            repo=target_host,
            candidate_python_code=candidate_python_code,
        )
        if ast_rejection is not None:
            return PRGuardResult(
                created=False,
                status="rejected_ast",
                decision=ast_rejection,
                error_code="PR_PATCH_AST_INVALID",
            )

        rationale = f"Crear PR '{title}' ({head_branch} -> {base_branch}) en {repo}"

        decision = self.governance.authorize_action(
            actor=actor,
            action_type=ActionImpact.PR_CREATION,
            target=target_host,
            rationale=rationale,
            impact=ActionImpact.PR_CREATION,
        )

        if decision.requires_human_approval and decision.approval_request_id:
            approved_by_user = (
                bool(self.approval_callback(decision))
                if self.approval_callback is not None
                else False
            )
            if approved_by_user:
                ok = self.governance.approval_gate.approve(
                    decision.approval_request_id,
                    approver=approver,
                )
                if ok:
                    decision = self.governance.authorize_action(
                        actor=actor,
                        action_type=ActionImpact.PR_CREATION,
                        target=target_host,
                        approval_request_id=decision.approval_request_id,
                        rationale=rationale,
                        impact=ActionImpact.PR_CREATION,
                    )

        if not decision.allowed:
            status = (
                "pending_human_approval"
                if decision.requires_human_approval
                else "denied_by_governance"
            )
            return PRGuardResult(created=False, status=status, decision=decision)

        try:
            pr_info = self.pr_client.create_pull_request(
                repo=repo,
                head_branch=head_branch,
                base_branch=base_branch,
                title=title,
                body=body,
            )
            self.governance.emergency_stop.record_error(is_error=False)
            self.governance._record(
                event_type="pr_created",
                actor=actor,
                target=target_host,
                action=ActionImpact.PR_CREATION.value,
                outcome="allowed",
                details={
                    "repo": repo,
                    "branch": head_branch,
                    "pr_number": pr_info.get("number"),
                },
            )
            return PRGuardResult(
                created=True,
                status="created_with_approval",
                decision=decision,
                pr_info=pr_info,
            )
        except Exception as exc:
            self.governance.emergency_stop.record_error(is_error=True)
            err_reason = f"Fallo al crear PR en {repo}: {exc}"
            err_dec = GovernanceDecision(
                allowed=False,
                reason=err_reason,
            )
            self.governance._record(
                event_type="pr_creation_error",
                actor=actor,
                target=target_host,
                action=ActionImpact.PR_CREATION.value,
                outcome="recorded",
                details={"code": "PR_CREATION_ERROR", "repo": repo, "reason": err_reason},
            )
            return PRGuardResult(
                created=False,
                status="error",
                decision=err_dec,
                error_code="PR_CREATION_ERROR",
            )
