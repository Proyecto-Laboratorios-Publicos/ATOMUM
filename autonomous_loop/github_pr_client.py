import os
import requests
from typing import Dict, Any

class GitHubPRClient:
    """Implementación del cliente para crear Pull Requests usando la API de GitHub."""

    def __init__(self, token: str | None = None):
        # Intentamos obtener el token del entorno si no se proporciona
        self.token = token or os.getenv("GITHUB_TOKEN")
        if not self.token:
            raise ValueError("Se requiere un GITHUB_TOKEN para autenticar con la API de GitHub.")
        self.base_url = "https://api.github.com"

    def create_pull_request(
        self,
        repo: str,
        head_branch: str,
        base_branch: str,
        title: str,
        body: str,
    ) -> Dict[str, Any]:
        """Crea un Pull Request en el repositorio especificado."""
        url = f"{self.base_url}/repos/{repo}/pulls"
        
        headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        payload = {
            "title": title,
            "head": head_branch,
            "base": base_branch,
            "body": body
        }

        response = requests.post(url, headers=headers, json=payload)
        
        if response.status_code != 201:
            raise Exception(f"Error al crear el PR en GitHub: {response.status_code} - {response.text}")
            
        return response.json()
