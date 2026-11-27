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
            denied = GovernanceDecision(
                allowed=False,
                code="PR_PATCH_AST_INVALID",
                reason=f"Código candidato rechazado antes de solicitar PR: {exc}",
            )
            self.governance._log("pr_patch_rejected", actor, repo, denied)
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
        if self.governance.emergency_stop.halted:
            reason = self.governance.emergency_stop.status.get("reason") or "Parada activa"
            blocked = GovernanceDecision(
                allowed=False,
                code="EMERGENCY_STOP_ACTIVE",
                reason=f"Creación de PR bloqueada por EmergencyStop: {reason}",
            )
            self.governance._log("pr_blocked_emergency_stop", actor, repo, blocked)
            return PRGuardResult(created=False, status="blocked_emergency_stop", decision=blocked)

        ast_rejection = self._validate_candidate_patch(
            actor=actor,
            repo=repo,
            candidate_python_code=candidate_python_code,
        )
        if ast_rejection is not None:
            return PRGuardResult(created=False, status="rejected_ast", decision=ast_rejection)

        decision = self.governance.authorize_action(
            actor=actor,
            action_name="create_pull_request",
            impact=ActionImpact.PR_CREATION,
            host=repo,
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
                        action_name="create_pull_request",
                        impact=ActionImpact.PR_CREATION,
                        host=repo,
                        approval_request_id=decision.approval_request_id,
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
            self.governance._log(
                "pr_created",
                actor,
                repo,
                decision,
                details={"branch": head_branch, "pr_number": pr_info.get("number")},
            )
            return PRGuardResult(
                created=True,
                status="created_with_approval",
                decision=decision,
                pr_info=pr_info,
            )
        except Exception as exc:
            self.governance.emergency_stop.record_error(is_error=True)
            err_dec = GovernanceDecision(
                allowed=False,
                code="PR_CREATION_ERROR",
                reason=f"Fallo al crear PR en {repo}: {exc}",
            )
            self.governance._log("pr_creation_error", actor, repo, err_dec)
            return PRGuardResult(created=False, status="error", decision=err_dec)
