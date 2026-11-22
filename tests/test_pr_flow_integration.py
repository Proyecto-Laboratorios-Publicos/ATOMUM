from __future__ import annotations

from typing import Any, Dict, List

from autonomous_loop.pr_guard import ProtectedPullRequestWorkflow
from core.governance import ActionImpact, GovernanceController, ScopePolicy


class _RecordingPRClient:
    def __init__(self) -> None:
        self.created_prs: List[Dict[str, Any]] = []

    def create_pull_request(
        self,
        repo: str,
        head_branch: str,
        base_branch: str,
        title: str,
        body: str,
    ) -> Dict[str, Any]:
        pr = {
            "number": len(self.created_prs) + 101,
            "repo": repo,
            "head_branch": head_branch,
            "base_branch": base_branch,
            "title": title,
            "body": body,
            "state": "open",
        }
        self.created_prs.append(pr)
        return pr


def _build_controller() -> GovernanceController:
    policy = ScopePolicy(allowed_domains=["atomum-repo.local"])
    return GovernanceController(policy)


class TestPRWorkflowEndToEnd:
    def test_reviewer_rejection_blocks_pr_creation(self):
        gov = _build_controller()
        client = _RecordingPRClient()
        workflow = ProtectedPullRequestWorkflow(
            governance=gov,
            pr_client=client,
            approval_callback=lambda _decision: False,
        )

        res = workflow.request_and_create_pr(
            actor="atomum_autonomous_loop",
            repo="atomum-repo.local",
            head_branch="fix/ast-guardrail-check",
            base_branch="main",
            title="Harden AST check before PR",
            body="Validates candidate code before requesting review.",
            candidate_python_code="x = 10\nresult = x * 2\n",
        )

        assert res.created is False
        assert res.status == "pending_human_approval"
        assert len(client.created_prs) == 0

    def test_emergency_stop_halts_pr_creation_immediately(self):
        gov = _build_controller()
        client = _RecordingPRClient()
        gov.emergency_stop.trip("Bucle autónomo detenido por umbral de prueba")

        workflow = ProtectedPullRequestWorkflow(
            governance=gov,
            pr_client=client,
            approval_callback=lambda _decision: True,
        )

        res = workflow.request_and_create_pr(
            actor="atomum_autonomous_loop",
            repo="atomum-repo.local",
            head_branch="feat/post-stop-pr",
            base_branch="main",
            title="Should not run when stopped",
            body="Emergency stop must block PR creation.",
            candidate_python_code="result = True\n",
        )

        assert res.created is False
        assert res.status == "blocked_emergency_stop"
        assert res.decision.code == "EMERGENCY_STOP_ACTIVE"
        assert len(client.created_prs) == 0

    def test_approved_pr_generates_audit_record_and_pr_metadata(self):
        gov = _build_controller()
        client = _RecordingPRClient()
        workflow = ProtectedPullRequestWorkflow(
            governance=gov,
            pr_client=client,
            approval_callback=lambda _decision: True,
        )

        res = workflow.request_and_create_pr(
            actor="atomum_autonomous_loop",
            repo="atomum-repo.local",
            head_branch="feat/audit-trail-export",
            base_branch="main",
            title="Export audit trail with evidence separation",
            body="Separates validated_evidence from llm_triage.",
            candidate_python_code="items = [1, 2, 3]\nresult = sum(items)\n",
            approver="totem_lead",
        )

        assert res.created is True
        assert res.status == "created_with_approval"
        assert res.pr_info is not None
        assert res.pr_info["number"] == 101
        assert len(client.created_prs) == 1
        assert any(
            getattr(ev, "event_type", None) == "pr_created"
            for ev in gov.audit_log
        )
