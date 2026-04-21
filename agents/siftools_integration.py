"""Optional semantic tool pruning via the siftools library.

Gated by env var ``SIFTOOLS_PRUNING_ENABLED`` — off by default, no behavior
change until opted in.

When enabled:
    1. A siftools ToolIndex is built once per process from ``.cache/siftools/tools.json``.
    2. On each agent load, the agent's declared MCP tool list is pruned:
       the router ranks ALL indexed tools by similarity to the agent's role
       description, then we intersect with the agent's declared set and keep
       the top ``SIFTOOLS_TOP_K`` MCP tools.
    3. Native tools (Read, Bash, Grep, ...) are preserved verbatim.

Safe failure: any exception in siftools returns the original tool list
unchanged, logged at WARNING level. Production path never fails because
of siftools.

Rebuilding the artifact:
    python -m agents.siftools_integration rebuild

This spawns every configured MCP server and writes ``.cache/siftools/tools.json``
with real server-provided descriptions (falling back to name-derived for
MCPs without credentials).
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger("data_agents.siftools_integration")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = PROJECT_ROOT / ".cache" / "siftools"
TOOLS_ARTIFACT = CACHE_DIR / "tools.json"

_index_singleton: Any = None
_router_singleton: Any = None
_index_failed = False


def is_enabled() -> bool:
    return os.getenv("SIFTOOLS_PRUNING_ENABLED", "").lower() in ("1", "true", "yes")


def _top_k() -> int:
    try:
        return max(1, int(os.getenv("SIFTOOLS_TOP_K", "15")))
    except ValueError:
        return 15


def _get_index() -> Any | None:
    """Load the siftools index lazily. Returns None on any failure."""
    global _index_singleton, _index_failed
    if _index_singleton is not None:
        return _index_singleton
    if _index_failed:
        return None

    try:
        from siftools import ToolIndex
    except ImportError:
        logger.warning("siftools not installed — pruning disabled. pip install siftools")
        _index_failed = True
        return None

    if not TOOLS_ARTIFACT.exists():
        logger.warning(
            "siftools tools artifact missing at %s — run: python -m agents.siftools_integration rebuild",
            TOOLS_ARTIFACT,
        )
        _index_failed = True
        return None

    try:
        tools = json.loads(TOOLS_ARTIFACT.read_text(encoding="utf-8"))
        _index_singleton = ToolIndex.build(tools)
        logger.info("siftools index built: %d tools from %s", len(tools), TOOLS_ARTIFACT)
        return _index_singleton
    except Exception as e:
        logger.warning("siftools index build failed: %s", e)
        _index_failed = True
        return None


def prune_agent_tools(
    tools: list[str],
    agent_description: str,
    top_k: int | None = None,
) -> list[str]:
    """Return a pruned copy of ``tools`` using siftools, or the original on any failure.

    Only MCP tools (``mcp__*`` prefix) are subject to pruning. Native
    tools pass through unchanged. If the declared MCP set is already <= top_k,
    returns the input unchanged (no work to do).
    """
    if not is_enabled():
        return tools

    native = [t for t in tools if not t.startswith("mcp__")]
    mcp_declared = [t for t in tools if t.startswith("mcp__")]

    k = top_k if top_k is not None else _top_k()

    if len(mcp_declared) <= k:
        return tools

    index = _get_index()
    if index is None:
        return tools

    try:
        global _router_singleton
        if _router_singleton is None:
            from siftools import RouterConfig, ToolRouter

            _router_singleton = ToolRouter(
                index,
                RouterConfig(top_k=len(index.tools), min_score=0.0),
            )
        result = _router_singleton.route(agent_description)
        declared_set = set(mcp_declared)
        chosen = [t for t in result.tools if t in declared_set][:k]

        pruned = native + chosen
        logger.info(
            "siftools pruning: %d -> %d tools (%d MCP -> %d); agent_desc=%r",
            len(tools),
            len(pruned),
            len(mcp_declared),
            len(chosen),
            agent_description[:60],
        )
        return pruned
    except Exception as e:
        logger.warning("siftools pruning error (returning full list): %s", e)
        return tools


# --- Rebuild CLI -------------------------------------------------------------
#
# Running ``python -m agents.siftools_integration rebuild`` spawns every MCP
# server and writes tools.json with real descriptions. This keeps the runtime
# path lightweight (just reads the artifact) and makes rebuilds an explicit,
# auditable action.


def _rebuild_tools_artifact() -> None:
    """Spawn every configured MCP server, collect real descriptions, write artifact."""
    import asyncio
    import sys as _sys

    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    from agents.loader import _resolve_tools, preload_registry
    from config.mcp_servers import ALL_MCP_CONFIGS

    TIMEOUT = 30

    def name_to_description(name: str) -> str:
        parts = name.split("__")
        if len(parts) >= 3:
            server = parts[1].replace("_", " ")
            tool = "__".join(parts[2:]).replace("_", " ").replace("-", " ")
            return f"{server}: {tool}"
        return name.replace("_", " ").replace("-", " ")

    async def list_for(server_key: str, cfg: dict) -> list[tuple[str, str]]:
        params = StdioServerParameters(
            command=cfg["command"],
            args=cfg.get("args", []),
            env=cfg.get("env") or None,
        )
        out: list[tuple[str, str]] = []
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                listed = await session.list_tools()
                for t in listed.tools:
                    full = f"mcp__{server_key}__{t.name}"
                    out.append((full, (t.description or "").strip()))
        return out

    async def collect() -> dict[str, str]:
        out: dict[str, str] = {}
        for server_key, factory in ALL_MCP_CONFIGS.items():
            try:
                cfg = factory()
            except Exception as e:
                print(f"  [SKIP]  {server_key}: {e}", file=_sys.stderr)
                continue
            for server_name, server_cfg in cfg.items():
                print(f"  [START] {server_name}", file=_sys.stderr)
                try:
                    pairs = await asyncio.wait_for(
                        list_for(server_name, server_cfg),
                        timeout=TIMEOUT,
                    )
                    for name, desc in pairs:
                        out[name] = desc
                    print(f"  [OK]    {server_name}: {len(pairs)} tools", file=_sys.stderr)
                except asyncio.TimeoutError:
                    print(f"  [TIMEOUT] {server_name}", file=_sys.stderr)
                except Exception as e:
                    print(f"  [FAIL]  {server_name}: {type(e).__name__}: {e}", file=_sys.stderr)
        return out

    print("collecting MCP tools with real descriptions ...", file=_sys.stderr)
    real = asyncio.run(collect())

    registry = preload_registry()
    declared: set[str] = set()
    for meta in registry.values():
        for t in _resolve_tools(meta.tools):
            if t.startswith("mcp__"):
                declared.add(t)

    merged: list[dict[str, str]] = []
    real_hits = 0
    for name in sorted(declared):
        if name in real:
            raw = real[name]
            clean = raw.split("\n\n", 1)[0].strip()
            for marker in ("\nArgs:", "\n    Args:", "\nReturns:"):
                i = clean.find(marker)
                if i != -1:
                    clean = clean[:i]
            clean = " ".join(clean.split())
            hint = name_to_description(name)
            desc = f"{hint}. {clean}" if clean else hint
            merged.append({"name": name, "description": desc, "source": "mcp"})
            real_hits += 1
        else:
            merged.append(
                {
                    "name": name,
                    "description": name_to_description(name),
                    "source": "name",
                }
            )

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    TOOLS_ARTIFACT.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"wrote {len(merged)} tools ({real_hits} real / {len(merged) - real_hits} fallback) "
        f"to {TOOLS_ARTIFACT}",
        file=_sys.stderr,
    )


def _main() -> None:
    import sys

    if len(sys.argv) < 2 or sys.argv[1] != "rebuild":
        print("usage: python -m agents.siftools_integration rebuild", file=sys.stderr)
        sys.exit(2)

    try:
        from dotenv import load_dotenv

        load_dotenv(PROJECT_ROOT / ".env")
    except ImportError:
        pass

    _rebuild_tools_artifact()


if __name__ == "__main__":
    _main()
