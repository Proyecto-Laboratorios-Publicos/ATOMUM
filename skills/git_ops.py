import os
import git

class GitOperations:
    def __init__(self, repo_path="."):
        self.repo_path = repo_path
        try:
            self.repo = git.Repo(self.repo_path)
            print("🦾 [Skills: Git] Repositorio vinculado exitosamente.")
        except Exception as e:
            print(f"❌ [Skills: Git Error] No se pudo inicializar el repositorio: {e}")
            self.repo = None

    def get_status(self):
        """Devuelve los archivos modificados o pendientes en el repositorio."""
        if not self.repo:
            return "Repositorio no disponible."
        
        unstaged_files = [item.a_path for item in self.repo.index.diff(None)]
        untracked_files = self.repo.untracked_files
        
        status_info = {
            "active_branch": self.repo.active_branch.name,
            "modified": unstaged_files,
            "untracked": untracked_files
        }
        print(f"📂 [Skills: Git] Estado actual obtenido: {status_info}")
        return status_info

if __name__ == "__main__":
    # Prueba rápida del módulo de Git
    git_tool = GitOperations()
    git_tool.get_status()
