import os
import git
from skills.web_tools import WebTools


class GitOperations:
    def __init__(self, repo_path="."):
        self.repo_path = repo_path
        self.web = WebTools()
        try:
            self.repo = git.Repo(self.repo_path)
            print("🦾 [Skills: Git] Repositorio vinculado y listo para operaciones avanzadas.")
        except Exception as e:
            print(f"❌ [Skills: Git Error] No se pudo inicializar el repositorio: {e}")
            self.repo = None

    def get_status(self):
        """Devuelve los archivos modificados, pendientes o no rastreados en el repositorio."""
        if not self.repo:
            return "Repositorio no disponible."
        try:
            unstaged_files = [item.a_path for item in self.repo.index.diff(None)]
            untracked_files = self.repo.untracked_files
            status_info = {
                "active_branch": self.repo.active_branch.name,
                "modified": unstaged_files,
                "untracked": untracked_files,
            }
            print(f"📂 [Skills: Git] Estado actual obtenido: {status_info}")
            return status_info
        except Exception as e:
            return f"❌ Error obteniendo estado de Git: {e}"

    def create_proposal_branch(self, branch_name: str, base_branch: str = "main") -> bool:
        """Crea y cambia a una rama aislada de propuesta (nunca opera directo sobre main)."""
        if not self.repo:
            return False
        if branch_name in ("main", "master"):
            print("🛡️ [Skills: Guardrail] Prohibido usar 'main' o 'master' como rama de propuesta.")
            return False
        try:
            if base_branch in self.repo.heads:
                self.repo.heads[base_branch].checkout()
            if branch_name in self.repo.heads:
                self.repo.heads[branch_name].checkout()
            else:
                new_branch = self.repo.create_head(branch_name)
                new_branch.checkout()
            print(f"🌿 [Skills: Git] Rama de propuesta activa: '{branch_name}'")
            return True
        except Exception as e:
            print(f"❌ [Skills: Git Error] No se pudo crear la rama '{branch_name}': {e}")
            return False

    def commit_changes(self, message: str, add_all: bool = True) -> bool:
        """Agrega los cambios al stage y realiza un commit automático (bloqueado en main)."""
        if not self.repo:
            print("❌ [Skills: Git Error] Repositorio no disponible para commit.")
            return False
        try:
            current_branch = self.repo.active_branch.name
            if current_branch in ("main", "master"):
                print("🛡️ [Skills: Guardrail] Commit directo bloqueado en rama principal.")
                return False
            if add_all:
                self.repo.git.add(A=True)
            if not self.repo.is_dirty(untracked_files=True):
                print("ℹ️ [Skills: Git] No hay cambios pendientes para commitear.")
                return False
            self.repo.index.commit(message)
            print(f"✅ [Skills: Git] Commit realizado con éxito en '{current_branch}': '{message}'")
            return True
        except Exception as e:
            print(f"❌ [Skills: Git Error] No se pudo realizar el commit: {e}")
            return False

    def push_branch(self, branch_name: str, token: str = None) -> bool:
        """Sube la rama de propuesta al remoto origin autenticando mediante GITHUB_TOKEN."""
        if not self.repo or branch_name in ("main", "master"):
            return False
        gh_token = token or os.getenv("GITHUB_TOKEN", "")
        try:
            origin = self.repo.remote(name="origin")
            original_url = origin.url
            if gh_token and original_url.startswith("https://") and "@" not in original_url:
                auth_url = original_url.replace("https://", f"https://x-access-token:{gh_token}@", 1)
                origin.set_url(auth_url)
                try:
                    origin.push(refspec=f"{branch_name}:{branch_name}")
                finally:
                    origin.set_url(original_url)
            else:
                origin.push(refspec=f"{branch_name}:{branch_name}")
            print(f"🚀 [Skills: Git] Rama '{branch_name}' subida a origin.")
            return True
        except Exception as e:
            print(f"❌ [Skills: Git Error] Falló el push de '{branch_name}': {type(e).__name__}")
            return False

    def create_pull_request(
        self,
        title: str,
        body: str,
        head_branch: str,
        base_branch: str = "main",
        repo_slug: str = "Proyecto-Laboratorios-Publicos/ATOMUM",
        token: str = None,
    ) -> dict:
        """Abre un Pull Request en GitHub mediante la API REST oficial."""
        gh_token = token or os.getenv("GITHUB_TOKEN", "")
        if not gh_token:
            return {"status": "error", "error": "GITHUB_TOKEN no configurado."}

        api_url = f"https://api.github.com/repos/{repo_slug}/pulls"
        headers = {"Authorization": f"Bearer {gh_token}"}
        payload = {
            "title": title,
            "body": body,
            "head": head_branch,
            "base": base_branch,
        }
        res = self.web.post_url_json(api_url, payload=payload, headers=headers)
        if res.get("status") == "ok":
            pr_url = res["data"].get("html_url", "")
            print(f"🎉 [Skills: Git] Pull Request creado: {pr_url}")
            return {"status": "ok", "pr_url": pr_url, "number": res["data"].get("number")}
        return res

    def get_latest_log(self, max_count: int = 1):
        """Obtiene información de los últimos commits realizados."""
        if not self.repo:
            return "Repositorio no disponible."
        try:
            commits = list(self.repo.iter_commits(max_count=max_count))
            return [
                {"sha": c.hexsha[:7], "message": c.message.strip(), "author": str(c.author)}
                for c in commits
            ]
        except Exception as e:
            return f"❌ Error obteniendo log de Git: {e}"
