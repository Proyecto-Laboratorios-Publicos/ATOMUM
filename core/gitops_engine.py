#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gitops_engine.py
----------------
Automatiza la creación de una rama y la apertura de un Pull Request en GitHub de forma segura,
siguiendo la política GitOps de ATOMUM.
"""
from __future__ import annotations
import os
import sys
import json
import logging
import subprocess
import hashlib
from pathlib import Path
from typing import Dict, Any
import requests
from git import Repo, GitCommandError
from dotenv import load_dotenv

# Carga .env solo en entornos de development
if Path(".env").exists():
    load_dotenv(".env")

GH_TOKEN: str = os.getenv("GH_TOKEN", "")
REPO_URL: str = os.getenv("REPO_URL", "")
BASE_BRANCH: str = os.getenv("BASE_BRANCH", "main")
WORKDIR: Path = Path(os.getenv("WORKDIR", "/tmp/gitops_workdir")).resolve()
IMPROVEMENT_FILE: Path = Path(os.getenv("IMPROVEMENT_FILE", "improvement.json")).resolve()

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s', handlers=[logging.StreamHandler(sys.stdout)])

def log_struct(message: str, **kwargs: Any) -> None:
    payload = {"msg": message, **kwargs}
    logging.info(json.dumps(payload))

def get_github_headers() -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {GH_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }

def load_improvement(file_path: Path) -> Dict[str, Any]:
    if not file_path.is_file():
        raise FileNotFoundError(f"Improvement file not found: {file_path}")
    data = json.loads(file_path.read_text(encoding="utf-8"))
    required = {"ticket_id", "title", "description", "type"}
    missing = required - data.keys()
    if missing:
        raise ValueError(f"Improvement JSON missing fields: {missing}")
    data["ticket_id"] = str(data["ticket_id"]).strip()
    data["title"] = data["title"].strip()
    return data

def clone_repo(repo_url: str, dest: Path) -> Repo:
    if dest.exists():
        try:
            repo = Repo(dest)
            log_struct("Repo already cloned, fetching latest", path=str(dest))
            repo.remotes.origin.fetch()
            return repo
        except Exception as e:
            log_struct("Existing directory not a repo, removing", error=str(e))
            for child in dest.iterdir():
                if child.is_dir():
                    subprocess.run(["rm", "-rf", str(child)], check=False)
                else:
                    child.unlink()
    log_struct("Cloning repository", url=repo_url, dest=str(dest))
    return Repo.clone_from(repo_url, dest, depth=1, branch=BASE_BRANCH, single_branch=True)

def generate_branch_name(improvement: Dict[str, Any]) -> str:
    ticket = improvement["ticket_id"]
    title = improvement["title"]
    slug = "-".join(title.lower().split())[:30]
    hash_part = hashlib.sha1(title.encode()).hexdigest()[:8]
    return f"improve/{ticket}/{slug}-{hash_part}"

def create_and_push_branch(repo: Repo, branch_name: str, improvement: Dict[str, Any]) -> None:
    git = repo.git
    try:
        git.checkout("-b", branch_name)
        log_struct("Created new branch", branch=branch_name)
    except GitCommandError as e:
        if "already exists" in str(e):
            git.checkout(branch_name)
            log_struct("Branch already existed locally, checked out", branch=branch_name)
        else:
            raise

    # Aplicar cambios menores (ej: CHANGELOG y VERSION)
    changelog_path = os.path.join(repo.working_tree_dir, "CHANGELOG.md")
    with open(changelog_path, "a", encoding="utf-8") as f:
        f.write(f"\n## [{improvement['title']}] - {improvement['ticket_id']}\n")
        f.write(f"{improvement['description']}\n")

    version_file = Path(repo.working_tree_dir) / "VERSION"
    if version_file.is_file():
        current = version_file.read_text().strip()
        major, minor, patch = map(int, current.split("."))
        new_version = f"{major}.{minor + 1}.0"
        version_file.write_text(new_version + "\n")
    else:
        version_file.write_text("1.1.0\n")
        new_version = "1.1.0"

    repo.index.add([changelog_path, str(version_file)])
    commit_msg = f"feat({improvement['type']}): {improvement['title']} [{improvement['ticket_id']}]"
    repo.index.commit(commit_msg, author=repo.config_reader().get_value("user", "name", "atomum-bot"))
    
    origin = repo.remote(name="origin")
    origin.push(refspec=f"{branch_name}:{branch_name}", force=True)
    log_struct("Pushed branch to origin", branch=branch_name)

def create_pull_request(repo_owner: str, repo_name: str, head_branch: str, base_branch: str, title: str, body: str, labels: list[str] | None = None) -> Dict[str, Any]:
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/pulls"
    payload = {"title": title, "head": head_branch, "base": base_branch, "body": body, "maintainer_can_modify": True}
    response = requests.post(url, headers=get_github_headers(), json=payload, timeout=15)
    if response.status_code != 201:
        raise RuntimeError(f"PR creation failed: {response.status_code} {response.text}")
    pr = response.json()
    if labels:
        label_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/issues/{pr['number']}/labels"
        requests.post(label_url, headers=get_github_headers(), json=labels, timeout=10)
    return pr

def main() -> int:
    if not GH_TOKEN or not REPO_URL:
        sys.exit("[ERROR] Faltan las variables de entorno GH_TOKEN o REPO_URL.")
    try:
        improvement = load_improvement(IMPROVEMENT_FILE)
        repo_path = REPO_URL.rstrip(".git").split("/")[-2:]
        repo_owner, repo_name = repo_path[0], repo_path[1]
        branch_name = generate_branch_name(improvement)
        
        repo = clone_repo(REPO_URL, WORKDIR)
        create_and_push_branch(repo, branch_name, improvement)
        
        pr = create_pull_request(
            repo_owner=repo_owner, repo_name=repo_name,
            head_branch=branch_name, base_branch=BASE_BRANCH,
            title=f"[{improvement['ticket_id']}] {improvement['title']}",
            body=f"## Descripción\n{improvement['description']}\n\n**Tipo:** {improvement['type']}",
            labels=["auto-generated", "improvement", improvement["type"]]
        )
        log_struct("Workflow completed successfully", pr_url=pr["html_url"])
        return 0
    except Exception as exc:
        log_struct("Fatal error in GitOps engine", error=str(exc))
        return 1

if __name__ == "__main__":
    sys.exit(main())
