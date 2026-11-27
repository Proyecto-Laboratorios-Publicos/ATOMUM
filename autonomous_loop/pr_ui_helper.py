from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, Optional

import streamlit as st

from autonomous_loop.pr_guard import PRGuardResult, ProtectedPullRequestWorkflow, PullRequestClient
from core.governance import GovernanceController, ScopePolicy
from core.guardrails import validate_user_code


def get_or_init_governance(allowed_domains: Optional[list[str]] = None) -> GovernanceController:
    if "atomum_governance" not in st.session_state:
        domains = allowed_domains or ["github.com", "Proyecto-Laboratorios-Publicos/ATOMUM"]
        st.session_state["atomum_governance"] = GovernanceController(
            ScopePolicy(allowed_domains=domains)
        )
    return st.session_state["atomum_governance"]


def validate_pr_candidate_code(code: str) -> tuple[bool, Optional[str]]:
    if not code.strip():
        return True, None
    try:
        validate_user_code(code)
        return True, None
    except Exception as exc:
        return False, str(exc)


def stage_pr_proposal(
    governance: GovernanceController,
    repo: str,
    head_branch: str,
    base_branch: str,
    title: str,
    body: str,
    candidate_code: str,
    actor: str = "atomum_ui",
) -> tuple[bool, str]:
    """Valida AST y deja preparada la propuesta en session_state a la espera de aprobación humana."""
    if governance.emergency_stop.halted:
        reason = governance.emergency_stop.status.get("reason") or "EmergencyStop activo"
        return False, f"Bloqueado por EmergencyStop: {reason}"

    ast_ok, ast_err = validate_pr_candidate_code(candidate_code)
    if not ast_ok:
        return False, f"Código rechazado por validación AST: {ast_err}"

    st.session_state["pending_pr_proposal"] = {
        "actor": actor,
        "repo": repo.strip(),
        "head_branch": head_branch.strip(),
        "base_branch": base_branch.strip(),
        "title": title.strip(),
        "body": body.strip(),
        "candidate_code": candidate_code,
    }
    return True, "Propuesta validada con AST. Requiere aprobación humana explicita para crear el PR."


def execute_staged_pr_with_approval(
    governance: GovernanceController,
    pr_client: PullRequestClient,
    approver: str,
    approved: bool,
) -> Optional[PRGuardResult]:
    proposal: Optional[Dict[str, Any]] = st.session_state.get("pending_pr_proposal")
    if not proposal:
        return None

    if not approved:
        st.session_state.pop("pending_pr_proposal", None)
        return None

    workflow = ProtectedPullRequestWorkflow(
        governance=governance,
        pr_client=pr_client,
        approval_callback=lambda _decision: True,
    )
    result = workflow.request_and_create_pr(
        actor=proposal["actor"],
        repo=proposal["repo"],
        head_branch=proposal["head_branch"],
        base_branch=proposal["base_branch"],
        title=proposal["title"],
        body=proposal["body"],
        candidate_python_code=proposal["candidate_code"],
        approver=approver.strip() or "human_reviewer",
    )

    history = st.session_state.setdefault("pr_guard_history", [])
    history.append(
        {
            "created": result.created,
            "status": result.status,
            "code": result.decision.code,
            "reason": result.decision.reason,
            "pr_info": result.pr_info,
        }
    )
    st.session_state.pop("pending_pr_proposal", None)
    return result


def render_protected_pr_section(pr_client: PullRequestClient) -> None:
    """Renderiza el bloque de creación de PRs protegido por AST + HumanApprovalGate."""
    st.subheader("Creación Protegida de Pull Request (Human-in-the-Loop)")
    governance = get_or_init_governance()

    if governance.emergency_stop.halted:
        st.error(
            f"EmergencyStop activo: {governance.emergency_stop.status.get('reason', 'Detenido')}"
        )

    with st.form("atomum_protected_pr_form"):
        repo = st.text_input("Repositorio / Target", value="Proyecto-Laboratorios-Publicos/ATOMUM")
        col1, col2 = st.columns(2)
        with col1:
            head_branch = st.text_input("Rama origen (head)", value="feat/hardening-governance")
        with col2:
            base_branch = st.text_input("Rama destino (base)", value="main")

        title = st.text_input("Título del PR", value="Harden governance and PR guardrails")
        body = st.text_area("Descripción del cambio", value="Validates AST and requires explicit approval.")
        candidate_code = st.text_area(
            "Código candidato a validar con AST (opcional)",
            value="x = 1\nresult = x + 1\n",
            height=120,
        )
        submitted = st.form_submit_button("1. Validar AST y preparar aprobación")

    if submitted:
        ok, msg = stage_pr_proposal(
            governance=governance,
            repo=repo,
            head_branch=head_branch,
            base_branch=base_branch,
            title=title,
            body=body,
            candidate_code=candidate_code,
        )
        if ok:
            st.info(msg)
        else:
            st.warning(msg)

    pending = st.session_state.get("pending_pr_proposal")
    if pending:
        st.markdown("**Propuesta lista para revisión humana:**")
        st.caption(
            f"Repo: `{pending['repo']}` | `{pending['head_branch']}` -> `{pending['base_branch']}` | "
            f"Título: `{pending['title']}`"
        )
        approver = st.text_input("Aprobado por (revisor humano)", value="totem_reviewer")
        c_app, c_rej = st.columns(2)
        with c_app:
            if st.button("2. Aprobar y crear PR", type="primary"):
                res = execute_staged_pr_with_approval(
                    governance=governance,
                    pr_client=pr_client,
                    approver=approver,
                    approved=True,
                )
                if res and res.created:
                    st.success(f"PR creado (#{res.pr_info.get('number') if res.pr_info else 'ok'}).")
                elif res:
                    st.warning(f"PR no creado ({res.status}): {res.decision.reason}")
        with c_rej:
            if st.button("Rechazar propuesta"):
                execute_staged_pr_with_approval(
                    governance=governance,
                    pr_client=pr_client,
                    approver=approver,
                    approved=False,
                )
                st.info("Propuesta descartada antes de crear el PR.")

    history = st.session_state.get("pr_guard_history", [])
    if history:
        st.markdown("**Historial de intentos de PR en esta sesión:**")
        for item in reversed(history[-5:]):
            st.write(asdict_like(item))


def asdict_like(item: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "created": item.get("created"),
        "status": item.get("status"),
        "decision_code": item.get("code"),
        "pr_number": (item.get("pr_info") or {}).get("number"),
    }
