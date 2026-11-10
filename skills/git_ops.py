import os
import git

class GitOperations:
    def __init__(self, repo_path="."):
        self.repo_path = repo_path
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
                "untracked": untracked_files
            }
            print(f"📂 [Skills: Git] Estado actual obtenido: {status_info}")
            return status_info
        except Exception as e:
            return f"❌ Error obteniendo estado de Git: {e}"

    def commit_changes(self, message: str, add_all: bool = True) -> bool:
        """Agrega los cambios al stage y realiza un commit automático."""
        if not self.repo:
            print("❌ [Skills: Git Error] Repositorio no disponible para commit.")
            return False
        try:
            if add_all:
                self.repo.git.add(A=True)
            
            self.repo.index.commit(message)
            print(f"✅ [Skills: Git] Commit realizado con éxito: '{message}'")
            return True
        except Exception as e:
            print(f"❌ [Skills: Git Error] No se pudo realizar el commit: {e}")
            return False

    def get_latest_log(self, max_count: int = 1):
        """Obtiene información de los últimos commits realizados."""
        if not self.repo:
            return "Repositorio no disponible."
        try:
            commits = list(self.repo.iter_commits(max_count=max_count))
            log_list = [{"sha": c.hexsha[:7], "message": c.message.strip(), "author": str(c.author)} for c in commits]
            return log_list
        except Exception as e:
            return f"❌ Error obteniendo log de Git: {e}"

if __name__ == "__main__":
    # Prueba rápida del módulo Git mejorado
    git_tool = GitOperations()
    print(git_tool.get_status())
