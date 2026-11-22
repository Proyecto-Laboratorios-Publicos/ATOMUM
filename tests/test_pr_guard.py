from __future__ import annotations

from typing import Any, Dict, List

from autonomous_loop.pr_guard import ProtectedPullRequestWorkflow
from core.governance import GovernanceController, ScopePolicy


class _FakePullRequestClient:
    def __init__(self) -> None:
        self.calls: List[Dict[str, Any]] = []

    def create_pull_request(
        self,
        repo: str,
        head_branch: str,
        base_branch: str,
        title: str,
        body: str,
    ) -> Dict[str, Any]:
        call = {
            "repo": repo,
            "head_branch": head_branch,
            "base_branch": base_branch,
            "title": title,
            "body": body,
            "number": 42,
        }
        self.calls.append(call)
        return call


def _make_governance() -> GovernanceController:
    # Permitimos el repositorio lógico en allowed_domains para aislar la prueba
    # al flujo de HumanApprovalGate con ActionImpact.PR_CREATION.
    policy = ScopePolicy(allowed_domains=["atomum-repo.local"])
    return GovernanceController(policy)


class TestProtectedPullRequestWorkflow:
    def test_blocks_pr_creation_without_human_approval(self):
        gov = _make_governance()
        client = _FakePullRequestClient()
        workflow = ProtectedPullRequestWorkflow(
            governance=gov,
            pr_client=client,
            approval_callback=None,  # Sin aprobación humana
        )

        result = workflow.request_and_create_pr(
            actor="atomum_loop",
            repo="atomum-repo.local",
            head_branch="feat/hardening-scan",
            base_branch="main",
            title="Harden TCP scanner states",
            body="Adds explicit FILTERED_OR_AMBIGUOUS handling.",
        )

        assert result.created is False
        assert result.status == "pending_human_approval"
        assert result.decision.requires_human_approval is True
        assert result.decision.approval_request_id is not None
        assert len(client.calls) == 0

    def test_rejects_invalid_ast_before_requesting_approval(self):
        gov = _make_governance()
        client = _FakePullRequestClient()
        callback_invoked = False

        def _callback(_decision) -> bool:
            nonlocal callback_invoked
            callback_invoked = True
            return True

        workflow = ProtectedPullRequestWorkflow(
            governance=gov,
            pr_client=client,
            approval_callback=_callback,
        )

        # Bloque except sin cuerpo válido -> falla de sintaxis/AST
        broken_code = "try:\n    x = 1\nexcept Exception:\n"

        result = workflow.request_and_create_pr(
            actor="atomum_loop",
            repo="atomum-repo.local",
            head_branch="fix/broken-planner",
            base_branch="main",
            title="Fix planner exception block",
            body="Attempts to patch planner.py",
            candidate_python_code=broken_code,
        )

        assert result.created is False
        assert result.status == "rejected_ast"
        assert result.decision.code == "PR_PATCH_AST_INVALID"
        assert callback_invoked is False
        assert len(client.calls) == 0

    def test_creates_pr_after_explicit_human_approval(self):
        gov = _make_governance()
        client = _FakePullRequestClient()
        workflow = ProtectedPullRequestWorkflow(
            governance=gov,
            pr_client=client,
            approval_callback=lambda _decision: True,
        )

        valid_code = "result = 2 + 2\n"

        result = workflow.request_and_create_pr(
            actor="atomum_loop",
            repo="atomum-repo.local",
            head_branch="feat/governance-audit",
            base_branch="main",
            title="Add governance audit trail",
            body="Includes ValidatedEvidence and HumanApprovalGate.",
            candidate_python_code=valid_code,
            approver="lucas_reviewer",
        )

        assert result.created is True
        assert result.status == "created_with_approval"
        assert result.pr_info is not None
        assert result.pr_info["number"] == 42
        assert len(client.calls) == 1
        assert client.calls[0]["head_branch"] == "feat/governance-audit"
        assert any(rec.event_type == "pr_created" for rec in gov.audit_log)
