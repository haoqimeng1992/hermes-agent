"""
Unified Context Engine Plugin

Replaces the built-in ContextCompressor with a unified system that integrates:
- MemGPT-style hierarchical memory and auto-summarization
- Big-Memory-style snapshot before compaction
- Cognitive-Memory-style reflection engine
- Hermes-Memory-Tiering for archival
- Context-Compaction-Recovery for post-compaction grep recovery

Configuration in config.yaml:
  context:
    engine: "unified"  # activates this plugin
"""

import hashlib
import json
import logging
import re
import time
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from agent.context_engine import ContextEngine

logger = logging.getLogger(__name__)

_THRESHOLD_PERCENT = 0.80
_PROTECT_LAST_N = 20
_MIN_SUMMARY_TOKENS = 2000
_MAX_SUMMARY_TOKENS = 8000

SUMMARY_PREFIX = (
    "[CONTEXT COMPACTION — REFERENCE ONLY] Earlier turns were compacted "
    "into the summary below. This is a handoff from a previous context "
    "window — treat it as background reference, NOT as active instructions. "
    "Do NOT answer questions or fulfill requests mentioned in this summary; "
    "they were already addressed. Respond ONLY to the latest user message "
    "that appears AFTER this summary."
)


class UnifiedContextEngine(ContextEngine):
    """Unified context engine combining MemGPT + Big-Memory + Cognitive + Hermes."""

    name = "unified"

    last_prompt_tokens: int = 0
    last_completion_tokens: int = 0
    last_total_tokens: int = 0
    threshold_tokens: int = 0
    context_length: int = 200000
    compression_count: int = 0

    threshold_percent: float = 0.80
    protect_first_n: int = 3
    protect_last_n: int = 20

    def __init__(self):
        self.session_id = None
        self.snapshot_dir = Path.home() / ".hermes" / "memory" / "snapshots"
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)
        self.memory_db = Path.home() / ".hermes" / "memory" / "memories.db"
        self._init_db()
        self._pending_snapshot = None

    def _init_db(self):
        try:
            conn = sqlite3.connect(str(self.memory_db))
            conn.execute("""
                CREATE TABLE IF NOT EXISTS facts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT NOT NULL,
                    tags TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    access_count INTEGER DEFAULT 0,
                    last_accessed TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS lessons (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action TEXT,
                    context TEXT,
                    outcome TEXT,
                    insight TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS entities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE,
                    type TEXT,
                    properties TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning(f"Failed to init memory DB: {e}")

    def on_session_start(self, session_id: str, **kwargs) -> None:
        self.session_id = session_id
        self.compression_count = 0
        self._pending_snapshot = None

    def on_session_end(self, session_id: str, messages: List[Dict[str, Any]]) -> None:
        if self._pending_snapshot:
            self._save_snapshot(self._pending_snapshot)
            self._pending_snapshot = None

    def on_session_reset(self) -> None:
        self.last_prompt_tokens = 0
        self.last_completion_tokens = 0
        self.last_total_tokens = 0
        self.compression_count = 0

    def update_model(self, model: str, context_length: int, base_url: str = "",
                     api_key: str = "", provider: str = "") -> None:
        self.context_length = context_length
        self.threshold_tokens = int(context_length * self.threshold_percent)

    def update_from_response(self, usage: Dict[str, Any]) -> None:
        self.last_prompt_tokens = usage.get("prompt_tokens", 0)
        self.last_completion_tokens = usage.get("completion_tokens", 0)
        self.last_total_tokens = usage.get("total_tokens", 0)

    def should_compress(self, prompt_tokens: int = None) -> bool:
        pt = prompt_tokens if prompt_tokens is not None else self.last_prompt_tokens
        if self.threshold_tokens <= 0:
            return False
        return pt >= self.threshold_tokens

    def should_compress_preflight(self, messages: List[Dict[str, Any]]) -> bool:
        rough_estimate = len(json.dumps(messages)) // 4
        return rough_estimate >= self.threshold_tokens

    def compress(
        self,
        messages: List[Dict[str, Any]],
        current_tokens: int = None,
        focus_topic: str = None,
    ) -> List[Dict[str, Any]]:
        self.compression_count += 1

        # Step 1: Extract and persist facts/lessons/entities from the conversation
        self._extract_and_persist_memories(messages)

        # Step 2: Big-Memory SNAPSHOT
        self._save_snapshot(self._build_snapshot(messages))

        # Step 3: MemGPT-style summary
        preserved_head = messages[:self.protect_first_n]
        preserved_tail = messages[-self.protect_last_n:] if self.protect_last_n > 0 else []
        middle = messages[self.protect_first_n:-self.protect_last_n] if self.protect_last_n > 0 else messages[self.protect_first_n:]

        summary = self._generate_summary(middle)

        compressed = []
        compressed.extend(preserved_head)
        if summary:
            summary_msg = {
                "role": "system",
                "content": f"{SUMMARY_PREFIX}\n\n{summary}"
            }
            compressed.append(summary_msg)
        compressed.extend(preserved_tail)

        logger.info(
            f"[UnifiedContextEngine] Compression #{self.compression_count}: "
            f"{len(messages)} → {len(compressed)} messages"
        )
        return compressed

    def _extract_and_persist_memories(self, messages: List[Dict[str, Any]]) -> None:
        """Extract facts, lessons, and entities from messages and persist to SQLite."""
        # Only extract on compression (when there's significant history to learn from)
        if len(messages) < 4:
            return

        # --- Facts ---
        seen_facts = set()
        for msg in messages:
            content = msg.get("content", "")
            if not isinstance(content, str):
                continue
            # Sentences ending with period/问号/感叹号 that look like facts
            for sent in re.split(r'[.。!?]', content):
                sent = sent.strip()
                if len(sent) > 10 and len(sent) < 200:
                    # Heuristic: sentences containing key knowledge markers
                    markers = [
                        r'(是|位于|被称为|称为|叫做)',
                        r'(模型|系统|框架|引擎|工具)',
                        r'(用户|昊奇梦|Hermes|Agent)',
                        r'(文件|目录|路径|路径)',
                        r'(配置|设置|参数|阈值)',
                        r'(token|context|compression|memory)',
                        r'(skill|技能|记忆|快照)',
                        r'(GitHub|push|commit|fork)',
                        r'(cron|定时|任务|调度)',
                    ]
                    if any(re.search(m, sent) for m in markers):
                        if sent not in seen_facts:
                            seen_facts.add(sent)
                            self.remember_fact(sent, tags=["auto-extracted"])

        # --- Entities ---
        seen_entities = set()
        for msg in messages:
            content = msg.get("content", "")
            if not isinstance(content, str):
                continue
            # Find capitalized/proper noun patterns and technical terms
            for match in re.finditer(r'\b([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)\b', content):
                entity = match.group(1).strip()
                if len(entity) > 2 and entity not in seen_entities:
                    seen_entities.add(entity)
                    # Classify entity type
                    if any(kw in entity.lower() for kw in ['model', 'engine', 'system', 'framework']):
                        etype = "technical"
                    elif any(kw in entity.lower() for kw in ['memory', 'context', 'token']):
                        etype = "concept"
                    else:
                        etype = "general"
                    self.add_entity(entity, entity_type=etype)

        # --- Lessons (from decision patterns) ---
        for i, msg in enumerate(messages[:-1]):
            content = msg.get("content", "")
            if not isinstance(content, str):
                continue
            # Look for decision/choice patterns
            decision_markers = [
                r'(决定|decided|选择|chose|选用|采用)',
                r'(修复|fix|修复了|fixed)',
                r'(创建|created|新增|added)',
            ]
            if any(re.search(m, content, re.I) for m in decision_markers):
                # Try to find the outcome in the next assistant message
                outcome = ""
                if i + 1 < len(messages):
                    next_msg = messages[i + 1]
                    next_content = next_msg.get("content", "")
                    if isinstance(next_content, str) and len(next_content) < 300:
                        outcome = next_content[:200]
                if outcome:
                    self.add_lesson(
                        action=content[:150],
                        context=f"compression #{self.compression_count}",
                        outcome=outcome,
                        insight=""
                    )

    def _build_snapshot(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        decisions, facts, open_tasks = [], [], []
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, str):
                if re.search(r"(decided|chose|选择|决定)", content, re.I):
                    decisions.append(content[:200])
                if re.search(r"(task|todo|next step|任务|下一步)", content, re.I):
                    open_tasks.append(content[:200])
                if re.search(r"(fact|learned|important)", content, re.I):
                    facts.append(content[:200])
        return {
            "timestamp": datetime.now().isoformat(),
            "snapshot_id": datetime.now().strftime("%Y-%m-%d-%H%M"),
            "compression_count": self.compression_count,
            "topic": "unknown",
            "decisions": decisions[:5],
            "facts": facts[:5],
            "open_tasks": open_tasks[:5],
            "message_count": len(messages),
        }

    def _save_snapshot(self, snapshot: Dict[str, Any]) -> None:
        snapshot_id = snapshot["snapshot_id"]
        filepath = self.snapshot_dir / f"{snapshot_id}.md"
        content = f"""<!-- UNIFIED-CONTEXT-SNAPSHOT v1 -->
<!-- timestamp: {snapshot['timestamp']} -->
<!-- snapshot_id: {snapshot_id} -->
<!-- compression_count: {snapshot['compression_count']} -->

## Topic
{snapshot['topic']}

## Decisions Made
{chr(10).join(f"- {d}" for d in snapshot['decisions']) if snapshot['decisions'] else "- none"}

## Key Facts
{chr(10).join(f"- {f}" for f in snapshot['facts']) if snapshot['facts'] else "- none"}

## Open Tasks
{chr(10).join(f"- {t}" for t in snapshot['open_tasks']) if snapshot['open_tasks'] else "- none"}

## Message Count at Snapshot
{snapshot['message_count']}

<!-- /UNIFIED-CONTEXT-SNAPSHOT -->
"""
        try:
            with open(filepath, "w") as f:
                f.write(content)
            logger.info(f"[UnifiedContextEngine] Snapshot saved: {filepath}")
        except Exception as e:
            logger.warning(f"Failed to save snapshot: {e}")

    def _generate_summary(self, middle_messages: List[Dict[str, Any]]) -> str:
        if not middle_messages:
            return ""
        try:
            from agent.auxiliary_client import call_llm
            messages_text = self._compact_messages(middle_messages)
            prompt = f"""You are a context compression assistant. Summarize the following conversation into key points.

CONVERSATION:
{messages_text}

Generate a structured summary with these sections:

### Decisions Made
List key decisions made and why.

### Key Facts
List important facts mentioned.

### User Preferences
Any preferences or habits mentioned.

### Open Tasks
Any incomplete tasks or next steps.

Keep the summary under 2000 tokens. Be precise.
"""
            result = call_llm(
                model="MiniMax-M2.5",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=_MIN_SUMMARY_TOKENS,
            )
            if result and isinstance(result, str) and len(result) > 50:
                return result
            return self._fallback_summary(middle_messages)
        except Exception as e:
            logger.warning(f"[UnifiedContextEngine] Summary call failed: {e}, using fallback")
            return self._fallback_summary(middle_messages)

    def _compact_messages(self, messages: List[Dict[str, Any]]) -> str:
        lines = []
        for msg in messages[-50:]:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            if isinstance(content, str) and len(content) > 500:
                content = content[:500] + "..."
            if content:
                lines.append(f"[{role}]: {content[:300]}")
        return "\n".join(lines)

    def _fallback_summary(self, messages: List[Dict[str, Any]]) -> str:
        decisions, facts, tasks = [], [], []
        for msg in messages:
            content = msg.get("content", "")
            if not isinstance(content, str):
                continue
            if re.search(r"(decided|chose|选择|决定)", content, re.I):
                decisions.append(content[:150])
            if re.search(r"(todo|next step|任务|下一步)", content, re.I):
                tasks.append(content[:150])
            if re.search(r"(fact|learned|important)", content, re.I):
                facts.append(content[:150])
        sections = []
        if decisions:
            sections.append("### Decisions Made\n" + "\n".join(f"- {d[:100]}" for d in decisions[:3]))
        if facts:
            sections.append("### Key Facts\n" + "\n".join(f"- {f[:100]}" for f in facts[:3]))
        if tasks:
            sections.append("### Open Tasks\n" + "\n".join(f"- {t[:100]}" for t in tasks[:3]))
        return "\n\n".join(sections) if sections else "Conversation summary unavailable."

    def recover_from_snapshot(self, session_id: str = None) -> Optional[str]:
        try:
            snapshots = sorted(self.snapshot_dir.glob("*.md"), key=lambda p: p.stat().st_mtime)
            if not snapshots:
                return None
            latest = snapshots[-1]
            content = latest.read_text()
            if "<!-- UNIFIED-CONTEXT-SNAPSHOT v1 -->" in content:
                logger.info(f"[UnifiedContextEngine] Recovered snapshot: {latest.name}")
                return content
        except Exception as e:
            logger.warning(f"[UnifiedContextEngine] Recovery failed: {e}")
        return None

    def grep_recover(self, query: str, session_dir: Path = None) -> List[str]:
        if session_dir is None:
            session_dir = Path.home() / ".hermes" / "sessions"
        results = []
        try:
            for session_file in session_dir.glob("session_*.json"):
                try:
                    if query.lower() in session_file.read_text().lower():
                        results.append(f"{session_file.name}: found '{query}'")
                except Exception:
                    continue
        except Exception as e:
            logger.warning(f"[UnifiedContextEngine] grep_recover failed: {e}")
        return results[:10]

    def remember_fact(self, fact: str, tags: List[str] = None) -> None:
        try:
            conn = sqlite3.connect(str(self.memory_db))
            conn.execute(
                "INSERT INTO facts (content, tags, created_at) VALUES (?, ?, datetime('now'))",
                (fact, ",".join(tags) if tags else "")
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning(f"[UnifiedContextEngine] remember_fact failed: {e}")

    def add_lesson(self, action: str, context: str, outcome: str, insight: str) -> None:
        """Store a lesson learned from action/outcome pairs during compression."""
        try:
            conn = sqlite3.connect(str(self.memory_db))
            conn.execute(
                "INSERT INTO lessons (action, context, outcome, insight, created_at) VALUES (?, ?, ?, ?, datetime('now'))",
                (action, context, outcome, insight)
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning(f"[UnifiedContextEngine] add_lesson failed: {e}")

    def add_entity(self, name: str, entity_type: str = "general", properties: Dict = None) -> None:
        """Store an entity extracted from conversation."""
        try:
            conn = sqlite3.connect(str(self.memory_db))
            props = json.dumps(properties or {})
            conn.execute(
                "INSERT OR IGNORE INTO entities (name, type, properties, created_at) VALUES (?, ?, ?, datetime('now'))",
                (name, entity_type, props)
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning(f"[UnifiedContextEngine] add_entity failed: {e}")

    def get_lessons(self, context: str = None) -> List[Dict]:
        lessons = []
        try:
            conn = sqlite3.connect(str(self.memory_db))
            cursor = conn.execute(
                "SELECT action, context, outcome, insight, created_at FROM lessons ORDER BY created_at DESC LIMIT 10"
            )
            for row in cursor:
                lessons.append({
                    "action": row[0], "context": row[1],
                    "outcome": row[2], "insight": row[3], "created_at": row[4]
                })
            conn.close()
        except Exception as e:
            logger.warning(f"[UnifiedContextEngine] get_lessons failed: {e}")
        return lessons

    def get_status(self) -> Dict[str, Any]:
        return {
            "last_prompt_tokens": self.last_prompt_tokens,
            "threshold_tokens": self.threshold_tokens,
            "context_length": self.context_length,
            "usage_percent": (
                min(100, self.last_prompt_tokens / self.context_length * 100)
                if self.context_length else 0
            ),
            "compression_count": self.compression_count,
            "engine": "unified",
        }


def register(ctx):
    ctx.register_context_engine(UnifiedContextEngine())
