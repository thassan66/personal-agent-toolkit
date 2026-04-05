from __future__ import annotations

import argparse
import asyncio
import json
import os
import platform
import signal
import sys
import tomllib
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from .core.agents import AgentRegistry
from .core.builtin_commands import register_builtin_commands
from .core.builtin_tools import register_builtin_tools
from .core.commands import CommandRegistry
from .core.memory import MemoryStore
from .core.mcp import LocalMcpRegistry
from .core.planning import PlanStore
from .core.plugins import PluginManager
from .core.providers import AnthropicProvider, EchoProvider, OllamaProvider, OpenAICompatibleProvider
from .core.query_engine import QueryEngine
from .core.skills import SkillRegistry
from .core.tasks import TaskManager
from .core.tools import ToolRegistry


OPENAI_COMPATIBLE_PROVIDER_DEFAULTS: dict[str, tuple[str, tuple[str, ...], str]] = {
    "openai": ("https://api.openai.com/v1", ("OPENAI_API_KEY",), ""),
    "openai-compatible": ("http://localhost:11434/v1", (), "dummy"),
    "lm-studio": ("http://localhost:1234/v1", (), "lm-studio"),
    "llama.cpp": ("http://localhost:8080/v1", (), "dummy"),
    "gemini": (
        "https://generativelanguage.googleapis.com/v1beta/openai",
        ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
        "",
    ),
}

OLLAMA_PROVIDER_DEFAULTS: tuple[str, tuple[str, ...], str] = (
    "http://localhost:11434",
    ("OLLAMA_API_KEY",),
    "dummy",
)

OPENAI_COMPATIBLE_PROVIDER_ALIASES: dict[str, str] = {
    "openai": "openai",
    "openai-compatible": "openai-compatible",
    "openai_compatible": "openai-compatible",
    "local-openai": "openai-compatible",
    "ollama": "ollama",
    "lm-studio": "lm-studio",
    "lmstudio": "lm-studio",
    "llama.cpp": "llama.cpp",
    "llamacpp": "llama.cpp",
    "gemini": "gemini",
    "google": "gemini",
    "google-ai": "gemini",
}

LOCAL_MODEL_PROFILES: dict[str, str] = {
    "balanced": "qwen2.5-coder:14b",
    "reasoning": "deepseek-r1:14b",
    "agentic": "devstral:24b",
}

LOCAL_MODEL_PROFILE_CANDIDATES: dict[str, tuple[str, ...]] = {
    "balanced": (
        "qwen2.5-coder:14b",
        "qwen2.5-coder:7b",
        "qwen2.5-coder:3b",
        "qwen2.5-coder:1.5b",
    ),
    "reasoning": (
        "deepseek-r1:14b",
        "deepseek-r1:8b",
        "deepseek-r1:7b",
        "deepseek-r1:1.5b",
        "qwen2.5-coder:14b",
        "qwen2.5-coder:7b",
        "qwen2.5-coder:3b",
    ),
    "agentic": (
        "devstral:24b",
        "qwen2.5-coder:14b",
        "qwen2.5-coder:7b",
        "qwen2.5-coder:3b",
    ),
}

ANSI_RESET = "\033[0m"
ANSI_STYLES = {
    "accent": "\033[96m",
    "muted": "\033[90m",
    "strong": "\033[1m",
    "success": "\033[92m",
    "error": "\033[91m",
}

CONFIG_FILE_NAME = ".personal-agent-toolkit.toml"
HISTORY_FILE_NAME = ".personal_agent_toolkit_history"


def _first_env(*names: str) -> str:
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return ""


def _parse_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _load_config(workspace: Path) -> tuple[dict[str, Any], Path | None]:
    config_path = workspace / CONFIG_FILE_NAME
    if not config_path.exists():
        return {}, None
    with config_path.open("rb") as handle:
        payload = tomllib.load(handle)
    if not isinstance(payload, dict):
        return {}, config_path
    config = dict(payload.get("toolkit", payload))
    if not isinstance(config, dict):
        return {}, config_path
    return config, config_path


def _pick_setting(
    cli_value: Any,
    *,
    env_name: str | None = None,
    config: dict[str, Any] | None = None,
    config_key: str | None = None,
) -> Any:
    if cli_value is not None:
        return cli_value
    if env_name:
        env_value = os.getenv(env_name)
        if env_value not in {None, ""}:
            return env_value
    if config is not None and config_key is not None:
        return config.get(config_key)
    return None


def _supports_color(stream: object) -> bool:
    if os.getenv("NO_COLOR"):
        return False
    isatty = getattr(stream, "isatty", None)
    return callable(isatty) and bool(isatty())


def _paint(text: str, style: str, *, enabled: bool) -> str:
    if not enabled:
        return text
    return f"{ANSI_STYLES[style]}{text}{ANSI_RESET}"


def _resolve_provider_label(provider_name: str | None, provider: object) -> str:
    if provider_name:
        return provider_name
    configured = os.getenv("PERSONAL_AGENT_TOOLKIT_PROVIDER", "").strip()
    if configured:
        return configured
    if isinstance(provider, AnthropicProvider):
        return "anthropic"
    if isinstance(provider, OpenAICompatibleProvider):
        return "openai-compatible"
    return "echo"


def _is_echo_provider(provider: object) -> bool:
    return isinstance(provider, EchoProvider)


def _render_repl_welcome(
    *,
    engine: QueryEngine,
    provider_label: str,
    workspace: Path,
    color_enabled: bool,
) -> str:
    title = _paint("Personal Agent Toolkit", "strong", enabled=color_enabled)
    divider = _paint("=" * 24, "muted", enabled=color_enabled)
    label_style = "accent" if color_enabled else "strong"
    workspace_name = workspace.name or str(workspace)
    lines = [
        title,
        divider,
        f"{_paint('Session', label_style, enabled=color_enabled)} : {engine.active_agent_name} | {provider_label} | {engine.model}",
        f"{_paint('Workspace', label_style, enabled=color_enabled)} : {workspace_name}",
        f"{_paint('Reasoning', label_style, enabled=color_enabled)} : {'public summaries on' if engine.public_reasoning else 'standard'}",
        "",
        _paint("Try this first:", "success", enabled=color_enabled),
        "  /help    command guide",
        "  /status  session snapshot",
        "  /clear   clean terminal view",
        "  /agents  switch persona/profile",
        "  /skills  inspect available skills",
        "  /plan    review the current plan",
        "",
    ]
    if _is_echo_provider(engine.provider):
        lines.extend(
            [
                _paint("Mock mode is active.", "error", enabled=color_enabled),
                "  Replies will echo your input instead of calling a real model.",
                "  Use --provider anthropic, --provider openai, or --provider ollama for real completions.",
                "",
            ]
        )
    lines.append(_paint("Enter a prompt or slash command. Use /quit to exit.", "muted", enabled=color_enabled))
    return "\n".join(lines)


def _build_prompt(agent_name: str, *, color_enabled: bool) -> str:
    prompt = f"[{agent_name}] > "
    return _paint(prompt, "accent", enabled=color_enabled)


def _build_prompt_with_context(
    *,
    agent_name: str,
    model: str,
    public_reasoning: bool,
    color_enabled: bool,
) -> str:
    compact_model = model if len(model) <= 18 else model[:15] + "..."
    reasoning_marker = "+r" if public_reasoning else ""
    prompt = f"[{agent_name}|{compact_model}{reasoning_marker}] > "
    return _paint(prompt, "accent", enabled=color_enabled)


def _render_statusline(*, engine: QueryEngine, provider_label: str, workspace: Path, color_enabled: bool) -> str:
    task_count = len(engine.tasks.all())
    plan = engine.plan_store.get() if getattr(engine, "plan_store", None) is not None else {"steps": []}
    plan_steps = len(plan.get("steps") or [])
    text = (
        f"{provider_label} | {engine.model} | {engine.active_agent_name} | "
        f"reasoning={'public' if engine.public_reasoning else 'std'} | "
        f"stream={'on' if getattr(engine, 'stream_enabled', True) else 'off'} | "
        f"timeout={getattr(engine, 'request_timeout', getattr(engine.provider, 'timeout', '?'))} | "
        f"tasks={task_count} | plan={plan_steps} | ws={workspace.name or workspace}"
    )
    return _paint(text, "muted", enabled=color_enabled)


def _setup_line_editing(engine: QueryEngine) -> tuple[object | None, Path | None]:
    try:
        import readline  # type: ignore
    except Exception:  # pragma: no cover
        return None, None
    history_path = Path.home() / HISTORY_FILE_NAME
    try:
        if history_path.exists():
            readline.read_history_file(str(history_path))
    except Exception:  # pragma: no cover
        history_path = None

    def completer(text: str, state: int) -> str | None:
        buffer = readline.get_line_buffer()
        if not buffer.startswith("/"):
            return None
        prefix = buffer[1:]
        options = [f"/{name}" for name in engine.commands.names() if name.startswith(prefix)]
        return options[state] if state < len(options) else None

    try:
        readline.set_completer(completer)
        readline.parse_and_bind("tab: complete")
        readline.set_history_length(500)
    except Exception:  # pragma: no cover
        pass
    return readline, history_path


def _truncate(text: str, limit: int = 56) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def _render_rich_text(text: str, *, color_enabled: bool) -> str:
    lines = text.splitlines()
    rendered: list[str] = []
    in_code_block = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code_block = not in_code_block
            if in_code_block:
                language = stripped[3:].strip()
                header = f"Code{f' ({language})' if language else ''}:"
                rendered.append(_paint(header, "accent", enabled=color_enabled))
            continue

        if in_code_block:
            rendered.append(_paint(f"    {line}", "muted", enabled=color_enabled))
            continue

        if stripped.startswith("### "):
            rendered.append("")
            rendered.append(_paint(stripped[4:].upper(), "strong", enabled=color_enabled))
            continue
        if stripped.startswith("## "):
            rendered.append("")
            rendered.append(_paint(stripped[3:].upper(), "strong", enabled=color_enabled))
            continue
        if stripped.startswith("# "):
            rendered.append("")
            rendered.append(_paint(stripped[2:].upper(), "strong", enabled=color_enabled))
            continue
        if stripped.startswith(("- ", "* ")):
            rendered.append(f"  • {stripped[2:]}")
            continue
        if stripped and stripped[0].isdigit() and ". " in stripped:
            rendered.append(f"  {stripped}")
            continue
        if stripped.endswith(":") and len(stripped) < 60:
            rendered.append(_paint(line, "accent", enabled=color_enabled))
            continue
        rendered.append(line)

    result = "\n".join(rendered).strip("\n")
    return result or text


def _preview_mapping(payload: dict[str, Any]) -> str:
    keys = ("path", "root", "pattern", "query", "command", "name", "agent", "uri", "task_id")
    parts: list[str] = []
    for key in keys:
        value = payload.get(key)
        if value in (None, "", [], {}):
            continue
        parts.append(f"{key}={_truncate(str(value))}")
        if len(parts) == 2:
            break
    return ", ".join(parts)


def _render_progress_event(event: dict[str, Any], *, color_enabled: bool) -> str | None:
    kind = event.get("kind")
    if kind == "submission_started":
        if event.get("provider") == "echo":
            return _paint(
                "[mock] echo provider active; no real model call will be made",
                "error",
                enabled=color_enabled,
            )
        preview = str(event.get("prompt_preview", "")).strip()
        if preview:
            return (
                _paint(
                    f"[thinking] {event['agent']} is planning with {event['model']}",
                    "muted",
                    enabled=color_enabled,
                )
                + "\n"
                + _paint(f"[goal] {_truncate(preview, limit=72)}", "accent", enabled=color_enabled)
            )
        return _paint(
            f"[thinking] {event['agent']} is planning with {event['model']}",
            "muted",
            enabled=color_enabled,
        )
    if kind == "model_round_started":
        return _paint(
            f"[step {event['round']}] checking context and deciding next action",
            "muted",
            enabled=color_enabled,
        )
    if kind == "tool_batch_started":
        count = int(event.get("count", 0))
        noun = "tool" if count == 1 else "tools"
        return _paint(f"[plan] using {count} {noun}", "accent", enabled=color_enabled)
    if kind == "tools_disabled_fallback":
        return _paint(
            "[fallback] model does not support tool calling; retrying without tools",
            "error",
            enabled=color_enabled,
        )
    if kind == "interactive_model_warning":
        suggestion = str(event.get("suggestion", "")).strip()
        if suggestion:
            return _paint(f"[hint] {suggestion}", "error", enabled=color_enabled)
        return _paint("[hint] current model may be a poor fit for interactive use", "error", enabled=color_enabled)
    if kind == "model_waiting":
        seconds = int(round(float(event.get("elapsed_seconds", 0))))
        return _paint(
            f"[wait] model is still generating after {seconds}s",
            "muted",
            enabled=color_enabled,
        )
    if kind == "tool_started":
        details = _preview_mapping(dict(event.get("arguments", {})))
        suffix = f" ({details})" if details else ""
        return _paint(f"[tool] {event['name']}{suffix}", "accent", enabled=color_enabled)
    if kind == "tool_finished":
        result = dict(event.get("result", {}))
        status = "ok" if result.get("ok") else "failed"
        elapsed_ms = int(event.get("elapsed_ms", 0))
        detail_payload = result.get("result") if result.get("ok") else {"error": result.get("error", "")}
        details = _preview_mapping(detail_payload if isinstance(detail_payload, dict) else {})
        suffix = f" ({details})" if details else ""
        style = "success" if status == "ok" else "error"
        return _paint(
            f"[done] {event['name']} {status} in {elapsed_ms}ms{suffix}",
            style,
            enabled=color_enabled,
        )
    if kind == "assistant_completed":
        preview = str(event.get("content_preview", "")).strip()
        if preview:
            return _paint(f"[answer] {_truncate(preview, limit=72)}", "success", enabled=color_enabled)
        return _paint("[answer] response ready", "success", enabled=color_enabled)
    if kind == "tool_loop_limit_reached":
        return _paint("[warning] tool loop limit reached", "error", enabled=color_enabled)
    return None


def _create_openai_compatible_provider(provider_key: str, *, base_url: str, api_key: str, timeout: float) -> OpenAICompatibleProvider:
    default_base_url, fallback_env_vars, default_api_key = OPENAI_COMPATIBLE_PROVIDER_DEFAULTS[provider_key]
    resolved_base_url = base_url or default_base_url
    resolved_api_key = api_key or _first_env(*fallback_env_vars) or default_api_key
    return OpenAICompatibleProvider(
        base_url=resolved_base_url,
        api_key=resolved_api_key,
        timeout=timeout,
        provider_label=provider_key,
    )


def _create_ollama_provider(*, base_url: str, api_key: str, timeout: float) -> OllamaProvider:
    default_base_url, fallback_env_vars, default_api_key = OLLAMA_PROVIDER_DEFAULTS
    resolved_base_url = base_url or default_base_url
    resolved_api_key = api_key or _first_env(*fallback_env_vars) or default_api_key
    return OllamaProvider(
        base_url=resolved_base_url,
        api_key=resolved_api_key,
        timeout=timeout,
    )


def _fetch_ollama_models(base_url: str, timeout: float = 2.0) -> set[str]:
    normalized = base_url.rstrip("/")
    if not normalized.endswith("/v1"):
        normalized = normalized + "/v1"
    req = urllib.request.Request(
        url=f"{normalized}/models",
        headers={"Content-Type": "application/json", "Authorization": "Bearer dummy"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            payload = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError):
        return set()
    data = payload.get("data") or []
    return {
        str(item.get("id", "")).strip()
        for item in data
        if str(item.get("id", "")).strip()
    }


def _resolve_local_profile_model(
    profile: str,
    *,
    provider_name: str | None,
    base_url: str | None,
    timeout: float | None,
) -> str:
    default_model = LOCAL_MODEL_PROFILES[profile]
    resolved_provider = (provider_name or os.getenv("PERSONAL_AGENT_TOOLKIT_PROVIDER", "")).strip().lower() or "ollama"
    if resolved_provider != "ollama":
        return default_model

    ollama_base_url = (
        base_url
        or os.getenv("PERSONAL_AGENT_TOOLKIT_BASE_URL", "").strip()
        or OLLAMA_PROVIDER_DEFAULTS[0]
    )
    installed_models = _fetch_ollama_models(ollama_base_url, timeout=timeout or 2.0)
    if not installed_models:
        return default_model
    for candidate in LOCAL_MODEL_PROFILE_CANDIDATES.get(profile, (default_model,)):
        if candidate in installed_models:
            return candidate
    return default_model


def create_provider(
    *,
    provider_name: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    timeout: float | None = None,
) -> object:
    provider_name = (provider_name or os.getenv("PERSONAL_AGENT_TOOLKIT_PROVIDER", "echo")).strip().lower()
    api_key = api_key if api_key is not None else os.getenv("PERSONAL_AGENT_TOOLKIT_API_KEY", "").strip()
    base_url = base_url if base_url is not None else os.getenv("PERSONAL_AGENT_TOOLKIT_BASE_URL", "").strip()
    timeout_env = os.getenv("PERSONAL_AGENT_TOOLKIT_TIMEOUT", "").strip()
    if timeout is not None:
        resolved_timeout = timeout
    elif timeout_env:
        resolved_timeout = float(timeout_env)
    elif provider_name == "ollama":
        resolved_timeout = 300.0
    else:
        resolved_timeout = 120.0

    if provider_name in {"anthropic", "claude"}:
        return AnthropicProvider(
            base_url=base_url or "https://api.anthropic.com/v1",
            api_key=api_key or os.getenv("ANTHROPIC_API_KEY", ""),
            timeout=resolved_timeout,
            anthropic_version=os.getenv("PERSONAL_AGENT_TOOLKIT_ANTHROPIC_VERSION", "2023-06-01"),
            max_tokens=int(os.getenv("PERSONAL_AGENT_TOOLKIT_MAX_TOKENS", "4096")),
        )

    if provider_name == "ollama":
        return _create_ollama_provider(
            base_url=base_url,
            api_key=api_key,
            timeout=resolved_timeout,
        )

    if provider_name in OPENAI_COMPATIBLE_PROVIDER_ALIASES:
        return _create_openai_compatible_provider(
            OPENAI_COMPATIBLE_PROVIDER_ALIASES[provider_name],
            base_url=base_url,
            api_key=api_key,
            timeout=resolved_timeout,
        )
    return EchoProvider()


def create_engine(
    *,
    workspace: Path,
    model: str | None = None,
    provider_name: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    timeout: float | None = None,
    public_reasoning: bool | None = None,
    config_path: Path | None = None,
    stream_enabled: bool | None = None,
) -> QueryEngine:
    tools = ToolRegistry()
    tasks = TaskManager()
    commands = CommandRegistry()
    package_root = Path(__file__).resolve().parent
    project_root = package_root.parent
    agents = AgentRegistry.from_directory(package_root / "agents")
    plugins = PluginManager.from_directory(project_root / "plugins")
    mcp = LocalMcpRegistry.from_directory(project_root, project_root / "mcp_servers")
    memory = MemoryStore(project_root / ".personal_agent_toolkit_memory.jsonl")
    plan_store = PlanStore(project_root / ".personal_agent_toolkit_plan.json")
    skills = SkillRegistry.from_directory(project_root / "skills")

    register_builtin_tools(tools)
    register_builtin_commands(commands)
    plugins.register(tools, commands)

    engine = QueryEngine(
        cwd=workspace,
        provider=create_provider(
            provider_name=provider_name,
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
        ),
        model=model or os.getenv("PERSONAL_AGENT_TOOLKIT_MODEL", "echo-local"),
        tools=tools,
        tasks=tasks,
        commands=commands,
        agents=agents,
        plugins=plugins,
        mcp=mcp,
        memory=memory,
        plan_store=plan_store,
        skills=skills,
        debug=os.getenv("PERSONAL_AGENT_TOOLKIT_DEBUG", "0") in {"1", "true", "yes", "on"},
        public_reasoning=(
            public_reasoning
            if public_reasoning is not None
            else os.getenv("PERSONAL_AGENT_TOOLKIT_PUBLIC_REASONING", "0") in {"1", "true", "yes", "on"}
        ),
    )
    engine.provider_name = provider_name or os.getenv("PERSONAL_AGENT_TOOLKIT_PROVIDER", "echo").strip().lower()
    engine.request_timeout = getattr(engine.provider, "timeout", timeout if timeout is not None else None)
    engine.stream_enabled = (
        stream_enabled
        if stream_enabled is not None
        else _parse_bool(os.getenv("PERSONAL_AGENT_TOOLKIT_STREAM", "1"), default=True)
    )
    engine.config_path = config_path
    return engine


async def run_repl(
    *,
    workspace: Path,
    model: str | None = None,
    provider_name: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    timeout: float | None = None,
    public_reasoning: bool | None = None,
    config_path: Path | None = None,
    stream_enabled: bool | None = None,
) -> None:
    engine = create_engine(
        workspace=workspace,
        model=model,
        provider_name=provider_name,
        api_key=api_key,
        base_url=base_url,
        timeout=timeout,
        public_reasoning=public_reasoning,
        config_path=config_path,
        stream_enabled=stream_enabled,
    )
    color_enabled = _supports_color(sys.stdout)
    def current_provider_label() -> str:
        return _resolve_provider_label(getattr(engine, "provider_name", provider_name), engine.provider)
    stream_state = {
        "thinking_started": False,
        "content_started": False,
        "streamed_content": False,
    }
    active_request_task: asyncio.Task[str] | None = None
    readline_module, history_path = _setup_line_editing(engine)

    def progress_printer(event: dict[str, Any]) -> None:
        kind = event.get("kind")
        if kind == "model_stream_thinking":
            text = str(event.get("text", ""))
            if not text:
                return
            if not stream_state["thinking_started"]:
                print(_paint("Thinking:", "muted", enabled=color_enabled))
                stream_state["thinking_started"] = True
            print(text, end="", flush=True)
            return
        if kind == "model_stream_content":
            text = str(event.get("text", ""))
            if not text:
                return
            if stream_state["thinking_started"] and not stream_state["content_started"]:
                print()
                print()
            if not stream_state["content_started"]:
                print(_paint("Answer:", "success", enabled=color_enabled))
                stream_state["content_started"] = True
            print(_render_rich_text(text, color_enabled=color_enabled), end="", flush=True)
            stream_state["streamed_content"] = True
            return
        if kind == "assistant_completed" and (
            stream_state["thinking_started"] or stream_state["content_started"]
        ):
            print()
            return
        line = _render_progress_event(event, color_enabled=color_enabled)
        if line:
            print(line)

    previous_sigint_handler = signal.getsignal(signal.SIGINT)

    def handle_sigint(signum: int, frame: Any) -> None:  # pragma: no cover - exercised via behavior
        nonlocal active_request_task
        if active_request_task is not None and not active_request_task.done():
            active_request_task.cancel()
            return
        raise KeyboardInterrupt()

    engine.progress_handler = progress_printer
    signal.signal(signal.SIGINT, handle_sigint)
    print(
        _render_repl_welcome(
            engine=engine,
            provider_label=current_provider_label(),
            workspace=workspace,
            color_enabled=color_enabled,
        )
    )
    try:
        while True:
            try:
                print(_render_statusline(engine=engine, provider_label=current_provider_label(), workspace=workspace, color_enabled=color_enabled))
                text = input(
                    _build_prompt_with_context(
                        agent_name=engine.active_agent_name,
                        model=engine.model,
                        public_reasoning=engine.public_reasoning,
                        color_enabled=color_enabled,
                    )
                ).strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not text:
                continue
            if text in {"/exit", "/quit"}:
                break
            stream_state["thinking_started"] = False
            stream_state["content_started"] = False
            stream_state["streamed_content"] = False
            active_request_task = asyncio.create_task(engine.submit(text))
            try:
                result = await active_request_task
            except asyncio.CancelledError:
                print()
                print(_paint("[cancelled] stopped current request", "error", enabled=color_enabled))
                continue
            except Exception as exc:  # pragma: no cover
                message = f"error: {type(exc).__name__}: {exc}"
                print(_paint(message, "error", enabled=color_enabled))
                continue
            finally:
                active_request_task = None
            if result == "__CLEAR_SCREEN__":
                print("\033[2J\033[H", end="")
                print(
                    _render_repl_welcome(
                        engine=engine,
                        provider_label=current_provider_label(),
                        workspace=workspace,
                        color_enabled=color_enabled,
                    )
                )
                continue
            if result and not stream_state["streamed_content"]:
                print(_render_rich_text(result, color_enabled=color_enabled))
    finally:
        if readline_module is not None and history_path is not None:
            try:
                readline_module.write_history_file(str(history_path))
            except Exception:  # pragma: no cover
                pass
        signal.signal(signal.SIGINT, previous_sigint_handler)


async def run_once(
    *,
    workspace: Path,
    prompt: str,
    model: str | None = None,
    provider_name: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    timeout: float | None = None,
    public_reasoning: bool | None = None,
    config_path: Path | None = None,
    stream_enabled: bool | None = None,
) -> None:
    engine = create_engine(
        workspace=workspace,
        model=model,
        provider_name=provider_name,
        api_key=api_key,
        base_url=base_url,
        timeout=timeout,
        public_reasoning=public_reasoning,
        config_path=config_path,
        stream_enabled=stream_enabled,
    )
    result = await engine.submit(prompt)
    if result:
        print(result)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Personal Agent Toolkit",
        epilog=(
            "Examples:\n"
            "  personal-agent-toolkit\n"
            "  personal-agent-toolkit --prompt \"/help\"\n"
            "  personal-agent-toolkit --provider ollama --local-profile balanced"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--prompt", help="Run a single prompt and exit")
    parser.add_argument("--cwd", default=".", help="Workspace directory")
    parser.add_argument("--provider", help="Override the active provider name")
    parser.add_argument("--base-url", help="Override the provider base URL")
    parser.add_argument("--api-key", help="Override the provider API key")
    parser.add_argument("--model", help="Override the active model name")
    parser.add_argument("--timeout", type=float, help="Override the provider timeout in seconds")
    parser.add_argument(
        "--public-reasoning",
        action="store_true",
        help="Ask the model to include concise visible reasoning summaries in answers",
    )
    parser.add_argument(
        "--stream",
        choices=("on", "off"),
        help="Override streaming output in the REPL",
    )
    parser.add_argument(
        "--local-profile",
        choices=sorted(LOCAL_MODEL_PROFILES),
        help="Use a recommended local coding model profile",
    )
    args = parser.parse_args(argv)

    workspace = Path(args.cwd).resolve()
    config, config_path = _load_config(workspace)

    provider_name = _pick_setting(
        args.provider,
        env_name="PERSONAL_AGENT_TOOLKIT_PROVIDER",
        config=config,
        config_key="provider",
    )
    base_url = _pick_setting(
        args.base_url,
        env_name="PERSONAL_AGENT_TOOLKIT_BASE_URL",
        config=config,
        config_key="base_url",
    )
    api_key = _pick_setting(
        args.api_key,
        env_name="PERSONAL_AGENT_TOOLKIT_API_KEY",
        config=config,
        config_key="api_key",
    )
    timeout_value = _pick_setting(
        args.timeout,
        env_name="PERSONAL_AGENT_TOOLKIT_TIMEOUT",
        config=config,
        config_key="timeout",
    )
    timeout = float(timeout_value) if timeout_value not in {None, ""} else None
    model = _pick_setting(
        args.model,
        env_name="PERSONAL_AGENT_TOOLKIT_MODEL",
        config=config,
        config_key="model",
    )
    config_public_reasoning = _parse_bool(config.get("public_reasoning"), default=False) if config else False
    env_public_reasoning = _parse_bool(os.getenv("PERSONAL_AGENT_TOOLKIT_PUBLIC_REASONING"), default=False)
    public_reasoning = args.public_reasoning or env_public_reasoning or config_public_reasoning
    local_profile = _pick_setting(
        args.local_profile,
        config=config,
        config_key="local_profile",
    )
    stream_choice = _pick_setting(
        args.stream,
        env_name="PERSONAL_AGENT_TOOLKIT_STREAM",
        config=config,
        config_key="stream",
    )
    stream_enabled = None if stream_choice is None else _parse_bool(stream_choice, default=True)

    if local_profile:
        provider_name = provider_name or "ollama"
        model = model or _resolve_local_profile_model(
            str(local_profile),
            provider_name=provider_name,
            base_url=str(base_url) if base_url else None,
            timeout=timeout,
        )

    if args.prompt:
        asyncio.run(
            run_once(
                workspace=workspace,
                prompt=args.prompt,
                model=model,
                provider_name=provider_name,
                api_key=str(api_key) if api_key is not None else None,
                base_url=str(base_url) if base_url is not None else None,
                timeout=timeout,
                public_reasoning=public_reasoning,
                config_path=config_path,
                stream_enabled=stream_enabled,
            )
        )
        return
    asyncio.run(
        run_repl(
            workspace=workspace,
            model=model,
            provider_name=provider_name,
            api_key=str(api_key) if api_key is not None else None,
            base_url=str(base_url) if base_url is not None else None,
            timeout=timeout,
            public_reasoning=public_reasoning,
            config_path=config_path,
            stream_enabled=stream_enabled,
        )
    )


if __name__ == "__main__":
    main()
