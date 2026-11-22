#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gitops_engine.py - ATOMUM Core v1.1
------------------------------------
Automatiza la creación de ramas y Pull Requests respetando GITHUB_WORKSPACE
y aplicando validaciones de ruta, nombres de rama, manejo de errores y logging.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path
import re
import shutil
import sys
from typing import Any

from dotenv import load_dotenv
from git import GitCommandError, Repo
import requests

if Path(".env").is_file():
    load_dotenv(".env")

GH_TOKEN: str = os.getenv("GH_TOKEN", "").strip()
REPO_URL: str = os.getenv("REPO_URL", "").strip()
BASE_BRANCH: str = os.getenv("BASE_BRANCH", "main").strip() or "main"
WORKDIR: Path = Path(os.getenv("WORKDIR", "/tmp/gitops_workdir")).resolve()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)

_SLUG_SANITIZER: re.Pattern[str] = re.compile(r"[^a-z0-9-]+")
_MULTI_DASH: re.Pattern[str] = re.compile(r"-{2,}")


def log_struct(message: str, **kwargs: Any) -> None:
    """Emite un registro estructurado en JSON a través del logger del módulo."""
    payload: dict[str, Any] = {"msg": message, **kwargs}
    log.info(json.dumps(payload, ensure_ascii=False, default=str))


def sanitize_remote_url(url: str) -> str:
    """Oculta credenciales embebidas si existieran en una URL HTTPS."""
    return re.sub(r"(https?://)([^/@]+)@", r"\1***@", url)


def get_github_headers() -> dict[str, str]:
    """Construye cabeceras autenticadas para la API REST de GitHub."""
    return {
        "Authorization": f"Bearer {GH_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def parse_repo_slug(repo_url: str) -> tuple[str, str]:
    """Extrae (owner, repo_name) de URLs HTTPS o SSH de GitHub."""
    cleaned = repo_url.strip()
    if cleaned.endswith("/"):
        cleaned = cleaned.rstrip("/")
    if cleaned.endswith(".git"):
        cleaned = cleaned[:-4]

    if cleaned.startswith("git@github.com:"):
        slug_part = cleaned.split(":", 1)[1]
    else:
        parts = cleaned.split("/")
        slug_part = "/".join(parts[-2:]) if len(parts) >= 2 else ""

    segments = [seg.strip() for seg in slug_part.split("/") if seg.strip()]
    if len(segments) != 2:
        raise ValueError(f"No se pudo extraer owner/repo válido desde REPO_URL: '{sanitize_remote_url(repo_url)}'")
    return segments[0], segments[1]


def _project_root() -> Path:
    """
    Devuelve la ruta absoluta al directorio raíz del repositorio.
    1. Prioriza GITHUB_WORKSPACE si está definido.
    2. Busca improvement.json subiendo desde la ubicación del archivo actual.
    3. Recurre al directorio de trabajo actual si existe improvement.json.
    """
    gh_workspace = os.getenv("GITHUB_WORKSPACE", "").strip()
    if gh_workspace:
        return Path(gh_workspace).resolve()

    cur = Path(__file__).resolve()
    for parent in [cur.parent, *cur.parents]:
        if (parent / "improvement.json").is_file():
            return parent

    cwd_candidate = Path.cwd() / "improvement.json"
    if cwd_candidate.is_file():
        return Path.cwd().resolve()

    raise FileNotFoundError(
        "No se pudo determinar la raíz del proyecto. "
        "Define GITHUB_WORKSPACE o ubica improvement.json en el repositorio."
    )


def load_improvement(root_dir: Path | None = None) -> dict[str, Any]:
    """Carga y valida improvement.json desde la raíz del workspace."""
    base_dir = root_dir.resolve() if root_dir is not None else _project_root()
    file_path = base_dir / "improvement.json"
    log.info("Cargando improvement.json desde %s", file_path)

    if not file_path.is_file():
        raise FileNotFoundError(f"No se encontró improvement.json en: {file_path}")

    try:
        raw_data = json.loads(file_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"improvement.json contiene JSON inválido: {exc.msg}") from exc

    if not isinstance(raw_data, dict):
        raise ValueError("improvement.json debe contener un objeto JSON en la raíz.")

    required = {"ticket_id", "title", "description", "type"}
    missing = required - raw_data.keys()
    if missing:
        raise ValueError(f"improvement.json no contiene los campos obligatorios: {sorted(missing)}")

    ticket_id = str(raw_data["ticket_id"]).strip()
    title = str(raw_data["title"]).strip()
    description = str(raw_data["description"]).strip()
    imp_type = str(raw_data["type"]).strip()

    if not ticket_id or not title:
        raise ValueError("Los campos 'ticket_id' y 'title' no pueden estar vacíos.")

    data: dict[str, Any] = dict(raw_data)
    data["ticket_id"] = ticket_id
    data["title"] = title
    data["description"] = description
    data["type"] = imp_type
    return data


def _clean_directory_contents(directory: Path) -> None:
    """Elimina de forma segura el contenido de un directorio existente dentro de WORKDIR."""
    resolved_dir = directory.resolve()
    if not resolved_dir.is_dir():
        return
    for child in resolved_dir.iterdir():
        resolved_child = child.resolve()
        if resolved_dir not in resolved_child.parents:
            continue
        if child.is_symlink() or child.is_file():
            child.unlink(missing_ok=True)
        elif child.is_dir():
            shutil.rmtree(resolved_child)


def clone_repo(repo_url: str, dest: Path) -> Repo:
    """Clona el repositorio objetivo o actualiza la copia local existente."""
    resolved_dest = dest.resolve()
    resolved_dest.parent.mkdir(parents=True, exist_ok=True)

    if resolved_dest.exists():
        try:
            repo = Repo(resolved_dest)
            log_struct("Repo already cloned, fetching latest", path=str(resolved_dest))
            repo.remotes.origin.fetch()
            return repo
        except Exception as exc:
            log_struct(
                "Existing directory not clean, re-cloning",
                path=str(resolved_dest),
                error=str(exc),
            )
            _clean_directory_contents(resolved_dest)
    else:
        resolved_dest.mkdir(parents=True, exist_ok=True)

    log_struct(
        "Cloning repository",
        url=sanitize_remote_url(repo_url),
        dest=str(resolved_dest),
    )
    return Repo.clone_from(
        repo_url,
        resolved_dest,
        depth=1,
        branch=BASE_BRANCH,
        single_branch=True,
    )


def _slugify_git_ref(text: str, max_len: int = 30) -> str:
    """Convierte texto libre en un segmento seguro para nombres de rama Git."""
    lowered = text.lower().strip()
    cleaned = _SLUG_SANITIZER.sub("-", lowered)
    collapsed = _MULTI_DASH.sub("-", cleaned).strip("-")
    return (collapsed[:max_len].strip("-")) or "item"


def generate_branch_name(improvement: dict[str, Any]) -> str:
    """Genera un nombre de rama Git determinista y válido."""
    ticket = _slugify_git_ref(str(improvement["ticket_id"]), max_len=20)
    title = str(improvement["title"])
    slug = _slugify_git_ref(title, max_len=30)
    hash_part = hashlib.sha1(title.encode("utf-8")).hexdigest()[:8]
    return f"improve/{ticket}/{slug}-{hash_part}"


def _bump_minor_version(current_raw: str) -> str:
    """Incrementa el componente minor de una versión semántica X.Y.Z."""
    parts = [p.strip() for p in current_raw.strip().split(".")]
    if len(parts) < 2 or not all(p.isdigit() for p in parts[:2]):
        return "1.1.0"
    major = int(parts[0])
    minor = int(parts[1]) + 1
    patch = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
    return f"{major}.{minor}.{patch}"


def create_and_push_branch(
    repo: Repo,
    branch_name: str,
    improvement: dict[str, Any],
    *,
    force_push: bool = False,
) -> None:
    """Crea o selecciona la rama, actualiza CHANGELOG.md y VERSION, comitea y hace push."""
    if not repo.working_tree_dir:
        raise RuntimeError("El repositorio no tiene un directorio de trabajo activo.")

    work_tree = Path(repo.working_tree_dir)
    git = repo.git

    try:
        git.checkout("-b", branch_name)
        log_struct("Created new branch", branch=branch_name)
    except GitCommandError as exc:
        if "already exists" in str(exc).lower():
            git.checkout(branch_name)
            log_struct("Branch already existed locally, checked out", branch=branch_name)
        else:
            raise

    changelog_path = work_tree / "CHANGELOG.md"
    with changelog_path.open("a", encoding="utf-8") as f:
        f.write(f"\n## [{improvement['title']}] - {improvement['ticket_id']}\n")
        f.write(f"{improvement['description']}\n")

    version_file = work_tree / "VERSION"
    if version_file.is_file():
        new_version = _bump_minor_version(version_file.read_text(encoding="utf-8"))
    else:
        new_version = "1.1.0"
    version_file.write_text(f"{new_version}\n", encoding="utf-8")

    repo.index.add([str(changelog_path), str(version_file)])

    imp_type = _slugify_git_ref(str(improvement["type"]), max_len=20)
    commit_msg = f"feat({imp_type}): {improvement['title']} [{improvement['ticket_id']}]"
    author_name = repo.config_reader().get_value("user", "name", "atomum-bot")
    author_email = repo.config_reader().get_value("user", "email", "bot@atomum.local")
    repo.index.commit(commit_msg, author=f"{author_name} <{author_email}>")

    origin = repo.remote(name="origin")
    refspec = f"{branch_name}:{branch_name}"
    if force_push:
        origin.push(refspec=refspec, force=True)
    else:
        origin.push(refspec=refspec)
    log_struct("Pushed branch to origin", branch=branch_name, version=new_version)


def create_pull_request(
    repo_owner: str,
    repo_name: str,
    head_branch: str,
    base_branch: str,
    title: str,
    body: str,
    labels: list[str] | None = None,
) -> dict[str, Any]:
    """Crea un Pull Request en GitHub y asigna etiquetas opcionales."""
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/pulls"
    payload = {
        "title": title,
        "head": head_branch,
        "base": base_branch,
        "body": body,
        "maintainer_can_modify": True,
    }
    response = requests.post(url, headers=get_github_headers(), json=payload, timeout=15)
    if response.status_code != 201:
        raise RuntimeError(f"PR creation failed: {response.status_code} {response.text}")

    pr: dict[str, Any] = response.json()
    if labels and "number" in pr:
        label_url = (
            f"https://api.github.com/repos/{repo_owner}/{repo_name}/issues/{pr['number']}/labels"
        )
        label_resp = requests.post(
            label_url,
            headers=get_github_headers(),
            json=labels,
            timeout=10,
        )
        if label_resp.status_code >= 400:
            log_struct(
                "Failed to attach labels to PR",
                pr_number=pr["number"],
                status=label_resp.status_code,
            )
    return pr


def main() -> int:
    if not GH_TOKEN or not REPO_URL:
        log.error("Faltan las variables de entorno GH_TOKEN o REPO_URL.")
        return 1

    try:
        project_root = _project_root()
        improvement = load_improvement(project_root)
        repo_owner, repo_name = parse_repo_slug(REPO_URL)
        branch_name = generate_branch_name(improvement)

        repo = clone_repo(REPO_URL, WORKDIR)
        create_and_push_branch(repo, branch_name, improvement)

        pr = create_pull_request(
            repo_owner=repo_owner,
            repo_name=repo_name,
            head_branch=branch_name,
            base_branch=BASE_BRANCH,
            title=f"[{improvement['ticket_id']}] {improvement['title']}",
            body=(
                f"## Descripción\n{improvement['description']}\n\n"
                f"**Tipo:** {improvement['type']}"
            ),
            labels=["auto-generated", "improvement", str(improvement["type"])],
        )
        log_struct("Workflow completed successfully", pr_url=pr.get("html_url", ""))
        return 0
    except Exception as exc:
        log_struct("Fatal error in GitOps engine", error=str(exc))
        return 1


if __name__ == "__main__":
    sys.exit(main())
