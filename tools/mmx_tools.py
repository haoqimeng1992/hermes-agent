#!/usr/bin/env python3
"""
MMX CLI Tool - MiniMax mmx-cli integration for Hermes Agent.

Provides tools for interacting with MiniMax's mmx-cli (v1.0.7):
  - mmx_text_chat    : Text chat with MiniMax models
  - mmx_image_gen    : Image generation (Native model)
  - mmx_speech_tts   : Text-to-Speech
  - mmx_speech_stt    : Speech-to-Text transcription
  - mmx_search       : Web search
  - mmx_agents       : List/create/manage agents
  - mmx_files        : File management
  - mmx_quota        : Show quota usage

All tools use the mmx-cli binary at: ~/.hermes/node/bin/mmx
Authentication: ~/.mmx/config.json (set up via `mmx auth login`)

Trigger: "use mmx", "minimax agent", "tts voice", "transcribe audio"
"""
import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Requirements check ─────────────────────────────────────────────────

REQUIRED_BINARY = str(Path.home() / ".hermes" / "node" / "bin" / "mmx")
CONFIG_FILE = Path.home() / ".mmx" / "config.json"


def _check_requirements() -> bool:
    """mmx-cli installed and authenticated."""
    if not os.path.exists(REQUIRED_BINARY):
        logger.warning("mmx binary not found at %s", REQUIRED_BINARY)
        return False
    if not CONFIG_FILE.exists():
        logger.warning("mmx config not found at %s", CONFIG_FILE)
        return False
    # Quick auth check
    try:
        result = subprocess.run(
            [REQUIRED_BINARY, "auth", "status"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            logger.warning("mmx auth check failed (exit %d): %s", result.returncode, result.stdout[:200])
            return False
        try:
            status = json.loads(result.stdout)
            if status.get("method") != "api-key":
                logger.warning("mmx auth check: not api-key method, got %s", status)
                return False
        except json.JSONDecodeError:
            logger.warning("mmx auth status not JSON: %s", result.stdout[:200])
            return False
    except Exception as e:
        logger.warning("mmx auth check error: %s", e)
        return False
    return True


def _run_mmx(args: List[str], timeout: int = 60, input_text: str = None) -> Dict[str, Any]:
    """Run mmx-cli command and return parsed JSON result."""
    cmd = [REQUIRED_BINARY] + args
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            input=input_text,
            env={**os.environ, "NO_COLOR": "1"},
        )
        output = result.stdout.strip()
        # Try JSON parse first
        try:
            return {"ok": True, "data": json.loads(output), "raw": output[:500]}
        except json.JSONDecodeError:
            return {
                "ok": result.returncode == 0,
                "data": output,
                "raw": output[:500],
                "stderr": result.stderr[:200] if result.stderr else "",
            }
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"Command timed out after {timeout}s"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ── Tool Handlers ──────────────────────────────────────────────────────

def mmx_text_chat(message: str, model: str = "MiniMax-M2.7", non_interactive: bool = True, **kwargs) -> str:
    """Chat with MiniMax models via mmx-cli text command."""
    args = ["text", "chat", "--message", message, "--model", model]
    if non_interactive:
        args.append("--non-interactive")
    result = _run_mmx(args, timeout=120, input_text=message + "\n")
    if result.get("ok"):
        data = result.get("data", {})
        if isinstance(data, dict):
            content = data.get("content", [])
            texts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    texts.append(item.get("text", ""))
                elif isinstance(item, dict) and item.get("type") == "thinking":
                    texts.append(f"[思考] {item.get('text', '')[:200]}")
            if texts:
                return "\n".join(texts)
            return str(data)
        return str(data)
    return f"mmx chat failed: {result.get('error', result.get('raw', 'unknown'))}"


def mmx_search(query: str, num_results: int = 5, **kwargs) -> str:
    """Search the web using mmx search command."""
    args = ["search", "query", query, "--num", str(num_results)]
    result = _run_mmx(args, timeout=30)
    if result.get("ok"):
        data = result.get("data", {})
        if isinstance(data, list):
            lines = []
            for i, item in enumerate(data[:num_results], 1):
                if isinstance(item, dict):
                    title = item.get("title", item.get("name", ""))
                    url = item.get("url", item.get("link", ""))
                    snippet = item.get("snippet", item.get("description", ""))
                    lines.append(f"{i}. **{title}**\n   {snippet}\n   🔗 {url}")
                else:
                    lines.append(f"{i}. {item}")
            return "\n\n".join(lines) if lines else str(data)
        return str(data)
    return f"mmx search failed: {result.get('error', result.get('raw', 'unknown'))}"


def mmx_speech_tts(text: str, voice: str = "female-tianmei", output: str = None, **kwargs) -> str:
    """Convert text to speech using mmx speech tts command."""
    if not output:
        output = str(Path.home() / ".hermes" / "audio_cache" / f"mmx_tts_{Path.home().name}_{Path.home().time.time()}.mp3")
    args = ["speech", "tts", "--text", text, "--voice", voice, "--output", output]
    result = _run_mmx(args, timeout=30)
    if result.get("ok"):
        return f"✅ TTS生成成功\n   文件: {output}\n   音色: {voice}\n   文本: {text[:100]}{'...' if len(text) > 100 else ''}"
    return f"mmx TTS failed: {result.get('error', result.get('raw', 'unknown'))}"


def mmx_speech_stt(file_path: str, language: str = "zh", **kwargs) -> str:
    """Transcribe speech to text using mmx speech stt command."""
    if not os.path.exists(file_path):
        return f"文件不存在: {file_path}"
    args = ["speech", "stt", "--file", file_path, "--language", language]
    result = _run_mmx(args, timeout=60)
    if result.get("ok"):
        data = result.get("data", {})
        if isinstance(data, dict):
            text = data.get("text", data.get("transcript", ""))
            language_detected = data.get("language", language)
            return f"📝 **转写结果**\n   语言: {language_detected}\n   内容: {text}"
        return str(data)
    return f"mmx STT failed: {result.get('error', result.get('raw', 'unknown'))}"


def mmx_image_gen(prompt: str, aspect_ratio: str = "1:1", resolution: str = "1K", **kwargs) -> str:
    """Generate image using mmx image gen command."""
    args = ["image", "gen", "--prompt", prompt, "--aspect-ratio", aspect_ratio, "--resolution", resolution]
    result = _run_mmx(args, timeout=60)
    if result.get("ok"):
        data = result.get("data", {})
        if isinstance(data, dict):
            image_url = data.get("image_url", data.get("url", ""))
            if image_url:
                return f"🎨 **图片生成成功**\n   ![image]({image_url})\n   Prompt: {prompt}\n   比例: {aspect_ratio} | 分辨率: {resolution}"
            return str(data)
        return str(data)
    return f"mmx image gen failed: {result.get('error', result.get('raw', 'unknown'))}"


def mmx_list_agents(**kwargs) -> str:
    """List all mmx agents."""
    args = ["agents", "list"]
    result = _run_mmx(args, timeout=15)
    if result.get("ok"):
        data = result.get("data", {})
        if isinstance(data, list):
            if not data:
                return "暂无 agents，使用 `mmx agents create` 创建一个"
            lines = ["🤖 **MMX Agents**\n"]
            for agent in data:
                if isinstance(agent, dict):
                    name = agent.get("name", "unknown")
                    desc = agent.get("description", agent.get("model", ""))
                    agent_id = agent.get("id", "")
                    lines.append(f"  • **{name}** (`{agent_id}`) - {desc}")
                else:
                    lines.append(f"  • {agent}")
            return "\n".join(lines)
        return str(data)
    return f"mmx agents list failed: {result.get('error', result.get('raw', 'unknown'))}"


def mmx_quota_show(**kwargs) -> str:
    """Show current MiniMax API quota usage."""
    args = ["quota", "show"]
    result = _run_mmx(args, timeout=15)
    if result.get("ok"):
        data = result.get("data", {})
        if isinstance(data, dict):
            model_remains = data.get("model_remains", [])
            lines = ["📊 **MiniMax Quota**\n"]
            if isinstance(model_remains, list):
                for item in model_remains:
                    if isinstance(item, dict):
                        name = item.get("model_name", "?")
                        remaining = item.get("current_interval_usage_count", 0)
                        total = item.get("current_interval_total_count", 0)
                        used = total - remaining
                        pct = (used / total * 100) if total > 0 else 0
                        lines.append(f"  • {name}: {remaining}/{total} ({pct:.0f}%)")
            else:
                lines.append(f"  {model_remains}")
            return "\n".join(lines)
        return str(data)
    return f"mmx quota show failed: {result.get('error', result.get('raw', 'unknown'))}"


def mmx_files_list(path: str = "/", **kwargs) -> str:
    """List files in mmx workspace."""
    args = ["files", "list", path]
    result = _run_mmx(args, timeout=15)
    if result.get("ok"):
        data = result.get("data", {})
        if isinstance(data, list):
            if not data:
                return f"目录为空: {path}"
            lines = [f"📁 **MMX Files** `{path}`\n"]
            for item in data:
                if isinstance(item, dict):
                    name = item.get("name", item.get("key", "?"))
                    size = item.get("size", item.get("type", ""))
                    lines.append(f"  • {name} ({size})")
                else:
                    lines.append(f"  • {item}")
            return "\n".join(lines)
        return str(data)
    return f"mmx files list failed: {result.get('error', result.get('raw', 'unknown'))}"


# ── Registry ───────────────────────────────────────────────────────────

TOOL_MODULE = sys.modules[__name__]
_TOOLS = [
    # Text
    ("mmx_text_chat", mmx_text_chat, "Text chat with MiniMax models via mmx-cli"),
    # Search
    ("mmx_search", mmx_search, "Search the web using mmx search"),
    # Speech
    ("mmx_speech_tts", mmx_speech_tts, "Convert text to speech with MiniMax TTS"),
    ("mmx_speech_stt", mmx_speech_stt, "Transcribe audio file to text"),
    # Image
    ("mmx_image_gen", mmx_image_gen, "Generate image using MiniMax native model"),
    # Agents
    ("mmx_list_agents", mmx_list_agents, "List all mmx CLI agents"),
    # Quota
    ("mmx_quota_show", mmx_quota_show, "Show MiniMax API quota usage"),
    # Files
    ("mmx_files_list", mmx_files_list, "List files in mmx workspace"),
]


def _register_all():
    from tools.registry import registry
    for tool_name, handler, description in _TOOLS:
        registry.register(
            name=tool_name,
            toolset="mmx",
            schema={
                "name": tool_name,
                "description": description,
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
            handler=lambda args, handler=handler, name=tool_name: handler(**args),
            check_fn=_check_requirements,
            requires_env=[],
            is_async=False,
            description=description,
            emoji="🧠",
        )


# Auto-register when imported
try:
    _register_all()
except Exception as e:
    logger.warning("mmx_tools auto-register failed: %s", e)
