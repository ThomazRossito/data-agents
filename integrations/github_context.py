"""Busca arquivos de repos GitHub externos para injetar como contexto nos agentes.

Atualmente usado para:
  - alisonpezzott/fabric-ci-cd → scripts PowerShell + pipelines YAML Azure DevOps
    injetados no devops_engineer quando a tarefa envolve CI/CD no Fabric
"""

from __future__ import annotations

import base64
import logging

import requests

logger = logging.getLogger(__name__)

_GITHUB_API = "https://api.github.com"
_TIMEOUT = 10  # segundos por request

FABRIC_CICD_REPO = "alisonpezzott/fabric-ci-cd"
# Paths a buscar dentro do repo (em ordem de prioridade)
_FABRIC_CICD_PATHS = ["scripts", "pipelines", "config.json"]
# Cap por arquivo para não explodir o contexto
_MAX_FILE_CHARS = 6_000
# Cap total do contexto injetado
_MAX_TOTAL_CHARS = 20_000


def _headers(token: str) -> dict:
    h = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def _fetch_path(repo: str, path: str, token: str, depth: int = 0) -> str | None:
    """Busca um arquivo ou diretório do GitHub. Recursão limitada a 1 nível."""
    if depth > 1:
        return None

    url = f"{_GITHUB_API}/repos/{repo}/contents/{path}"
    try:
        resp = requests.get(url, headers=_headers(token), timeout=_TIMEOUT)
    except requests.RequestException as exc:
        logger.warning("GitHub API error para %s/%s: %s", repo, path, exc)
        return None

    if resp.status_code == 404:
        return None
    if resp.status_code == 403:
        logger.warning("GitHub API 403 — verifique GITHUB_PERSONAL_ACCESS_TOKEN")
        return None
    if not resp.ok:
        return None

    data = resp.json()

    # Diretório → fetcha cada arquivo
    if isinstance(data, list):
        parts = []
        for item in data:
            if item["type"] != "file":
                continue
            if item.get("size", 0) > 100_000:
                continue  # ignora arquivos grandes
            content = _fetch_path(repo, item["path"], token, depth + 1)
            if content:
                parts.append(f"### {item['path']}\n```\n{content}\n```")
        return "\n\n".join(parts) if parts else None

    # Arquivo com conteúdo base64
    if isinstance(data, dict) and data.get("encoding") == "base64":
        raw = base64.b64decode(data["content"]).decode("utf-8", errors="replace")
        return raw[:_MAX_FILE_CHARS]

    return None


def fetch_fabric_cicd_context(token: str = "") -> str:
    """Retorna scripts e pipelines do repo fabric-ci-cd como bloco de contexto.

    Usa GITHUB_PERSONAL_ACCESS_TOKEN do settings se token não for passado.
    Retorna string vazia se o fetch falhar (não bloqueia o agente).
    """
    from config.settings import settings

    _token = token or settings.github_personal_access_token
    if not _token:
        logger.debug("GITHUB_PERSONAL_ACCESS_TOKEN não configurado — pulando fetch fabric-ci-cd")
        return ""

    parts = []
    total_chars = 0

    for path in _FABRIC_CICD_PATHS:
        content = _fetch_path(FABRIC_CICD_REPO, path, _token)
        if not content:
            continue
        block = f"## {FABRIC_CICD_REPO}/{path}\n\n{content}"
        total_chars += len(block)
        if total_chars > _MAX_TOTAL_CHARS:
            logger.debug("fabric-ci-cd context cap atingido em %s", path)
            break
        parts.append(block)

    if not parts:
        return ""

    return (
        "## Referência Externa: fabric-ci-cd\n"
        "Scripts e pipelines de CI/CD no Microsoft Fabric "
        f"(fonte: github.com/{FABRIC_CICD_REPO}):\n\n"
        + "\n\n---\n\n".join(parts)
    )
