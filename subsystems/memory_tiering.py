"""
Memory Tiering Subsystem — 记忆分层监控（只读安全版）

设计原则：只读不写，不自动归档/删除任何内容
- 所有操作均为"观察/报告"
- 归档/召回等写操作需要通过飞书手动触发
- 索引文件损坏时可通过"重新扫描"恢复

层级说明：
- core: 核心记忆文件（MEMORY.md / USER.md）内的活跃记忆
- l1/l2/l3: 归档层（由手动操作触发，不自动移动）

报告触发条件：
- 容量超过 80% 时报告
- 手动触发 /memorytier 命令时报告
- 每日 cron 轻量检查（只报告，不行动）
"""

import json
import logging
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .base import HERMES_HOME, Subsystem

logger = logging.getLogger(__name__)

MEMORY_DIR = HERMES_HOME / "memories"
INDEX_FILE = MEMORY_DIR / "memory_index.json"

# 容量阈值
MEMORY_CHAR_LIMIT = 10000
USER_CHAR_LIMIT = 5000
REPORT_THRESHOLD = 0.80  # 80% 时报告

# 归档规则（仅供参考，不自动执行）
L1_DAYS = 7     # 建议归档：核心层7天无访问
L2_DAYS = 30    # 建议归档：L1中30天无访问
L3_DAYS = 90    # 建议归档：L2中90天无访问


class MemoryTiering:
    """记忆分层监控管理器（只读安全模式）"""

    def __init__(self):
        self._ensure_index()
        self.index = self._load_index()

    def _ensure_index(self):
        """确保索引文件存在"""
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        if not INDEX_FILE.exists():
            INDEX_FILE.write_text(
                json.dumps({"version": 1, "entries": {}, "core_usage": {"memory": 0, "user": 0}, "last_rescan": None}, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )

    def _load_index(self) -> Dict:
        """加载索引文件"""
        try:
            return json.loads(INDEX_FILE.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning("索引文件损坏，将重建: %s", e)
            self._rebuild_index()
            return self._load_index()

    def _save_index(self):
        """保存索引文件"""
        INDEX_FILE.write_text(
            json.dumps(self.index, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

    def _read_memory_file(self, name: str) -> Tuple[List[str], int]:
        """读取核心记忆文件，返回(条目列表, 总字符数)"""
        path = MEMORY_DIR / f"{name.upper()}.md"
        if not path.exists():
            return [], 0
        content = path.read_text(encoding="utf-8")
        entries = [e.strip() for e in content.split("§") if e.strip()]
        return entries, len(content)

    def _generate_entry_id(self, content: str) -> str:
        """根据内容生成稳定ID"""
        import hashlib
        return hashlib.md5(content.encode()).hexdigest()[:12]

    def _now_ts(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _days_ago(self, ts_str: str) -> int:
        """返回距离今天的天数"""
        try:
            dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return (now - dt).days
        except Exception:
            return 0

    # ── 只读检查 ────────────────────────────────────────────────

    def rescan(self) -> Dict[str, Any]:
        """重新扫描 memory 文件，建立/重建索引（只读，不修改 memory 文件）"""
        entries_added = 0
        entries_updated = 0
        now = self._now_ts()

        for source in ["memory", "user"]:
            file_entries, char_count = self._read_memory_file(source)
            self.index["core_usage"][source] = char_count

            for content in file_entries:
                eid = self._generate_entry_id(content)
                if eid in self.index["entries"]:
                    # 已存在：更新最后访问时间和字符数
                    self.index["entries"][eid]["last_accessed"] = now
                    self.index["entries"][eid]["content_preview"] = content[:80]
                    entries_updated += 1
                else:
                    # 新条目
                    self.index["entries"][eid] = {
                        "id": eid,
                        "content_preview": content[:80],
                        "source": source,
                        "tier": "core",
                        "created": now,
                        "last_accessed": now,
                        "access_count": 1,
                    }
                    entries_added += 1

        self.index["last_rescan"] = now
        self._save_index()
        return {"added": entries_added, "updated": entries_updated}

    def check_status(self) -> Dict[str, Any]:
        """返回记忆系统状态（只读）"""
        counts = {"core": 0, "l1": 0, "l2": 0, "l3": 0}
        for meta in self.index["entries"].values():
            tier = meta.get("tier", "core")
            counts[tier] = counts.get(tier, 0) + 1

        memory_pct = self.index["core_usage"].get("memory", 0) / MEMORY_CHAR_LIMIT
        user_pct = self.index["core_usage"].get("user", 0) / USER_CHAR_LIMIT

        return {
            "ok": True,
            "name": "MemoryTiering",
            "total_entries": len(self.index["entries"]),
            "tier_counts": counts,
            "core_usage": {
                "memory": self.index["core_usage"].get("memory", 0),
                "user": self.index["core_usage"].get("user", 0),
            },
            "memory_limit": MEMORY_CHAR_LIMIT,
            "user_limit": USER_CHAR_LIMIT,
            "memory_pct": round(memory_pct * 100, 1),
            "user_pct": round(user_pct * 100, 1),
            "last_rescan": self.index.get("last_rescan"),
            "needs_report": memory_pct >= REPORT_THRESHOLD,
        }

    def get_stale_entries(self) -> Dict[str, List[Dict]]:
        """返回符合归档条件的记忆条目（只读，不执行归档）"""
        stale = {"l1_candidates": [], "l2_candidates": [], "l3_candidates": []}
        for eid, meta in self.index["entries"].items():
            days = self._days_ago(meta.get("last_accessed", ""))
            entry_info = {
                "id": eid,
                "preview": meta.get("content_preview", "")[:40],
                "source": meta.get("source"),
                "tier": meta.get("tier"),
                "days_inactive": days,
                "last_accessed": meta.get("last_accessed"),
            }
            tier = meta.get("tier", "core")
            if tier == "core" and days >= L1_DAYS:
                stale["l1_candidates"].append(entry_info)
            elif tier == "l1" and days >= L2_DAYS:
                stale["l2_candidates"].append(entry_info)
            elif tier == "l2" and days >= L3_DAYS:
                stale["l3_candidates"].append(entry_info)
        return stale

    # ── 手动操作（通过飞书触发） ────────────────────────────────

    def manual_archive(self, entry_id: str, target_tier: str) -> Dict[str, Any]:
        """手动归档某条记忆到指定层级（需要明确指定）"""
        from .base import HERMES_HOME
        L1_DIR = MEMORY_DIR / "l1"
        L2_DIR = MEMORY_DIR / "l2"
        L3_DIR = MEMORY_DIR / "l3"

        meta = self.index["entries"].get(entry_id)
        if not meta:
            return {"ok": False, "error": f"entry {entry_id} not found in index"}

        current_tier = meta.get("tier", "core")
        if current_tier == target_tier:
            return {"ok": False, "error": f"already in tier {target_tier}"}

        # 获取内容
        if current_tier == "core":
            source = meta["source"]
            entries, _ = self._read_memory_file(source)
            content = None
            for e in entries:
                if self._generate_entry_id(e) == entry_id:
                    content = e
                    break
        elif current_tier == "l1":
            content = (L1_DIR / f"{entry_id}.md").read_text(encoding="utf-8")
        elif current_tier == "l2":
            content = (L2_DIR / f"{entry_id}.md").read_text(encoding="utf-8")
        else:
            return {"ok": False, "error": f"cannot archive from tier {current_tier}"}

        if content is None:
            return {"ok": False, "error": "content not found"}

        # 写入目标层
        target_dir = {"l1": L1_DIR, "l2": L2_DIR, "l3": L3_DIR}.get(target_tier)
        if not target_dir:
            return {"ok": False, "error": f"invalid target tier: {target_tier}"}
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / f"{entry_id}.md").write_text(content + "\n", encoding="utf-8")

        # 从源层删除
        if current_tier == "core":
            source = meta["source"]
            entries, _ = self._read_memory_file(source)
            entries = [e for e in entries if self._generate_entry_id(e) != entry_id]
            content_new = "§\n".join(entries)
            if content_new:
                content_new += "§\n"
            (MEMORY_DIR / f"{source.upper()}.md").write_text(content_new, encoding="utf-8")
        elif current_tier == "l1":
            (L1_DIR / f"{entry_id}.md").unlink(missing_ok=True)
        elif current_tier == "l2":
            (L2_DIR / f"{entry_id}.md").unlink(missing_ok=True)

        meta["tier"] = target_tier
        meta["archived_at"] = self._now_ts()
        self._save_index()

        return {"ok": True, "entry_id": entry_id, "from": current_tier, "to": target_tier}

    def manual_recall(self, entry_id: str) -> Dict[str, Any]:
        """手动从归档层召回记忆到核心（只支持从l1/l2/l3回到core）"""
        from .base import HERMES_HOME
        L1_DIR = MEMORY_DIR / "l1"
        L2_DIR = MEMORY_DIR / "l2"
        L3_DIR = MEMORY_DIR / "l3"

        meta = self.index["entries"].get(entry_id)
        if not meta:
            return {"ok": False, "error": f"entry {entry_id} not found in index"}

        tier = meta.get("tier", "core")
        if tier == "core":
            return {"ok": False, "error": "already in core"}

        # 获取内容
        src_map = {"l1": L1_DIR / f"{entry_id}.md", "l2": L2_DIR / f"{entry_id}.md", "l3": L3_DIR / f"{entry_id}.md"}
        src_file = src_map.get(tier)
        if not src_file or not src_file.exists():
            return {"ok": False, "error": f"archived file not found for tier {tier}"}

        content = src_file.read_text(encoding="utf-8")

        # 追加回核心文件
        source = meta["source"]
        entries, _ = self._read_memory_file(source)
        entries.append(content.strip())
        content_new = "§\n".join(entries)
        if content_new:
            content_new += "§\n"
        (MEMORY_DIR / f"{source.upper()}.md").write_text(content_new, encoding="utf-8")

        # 删除归档文件
        src_file.unlink()

        meta["tier"] = "core"
        meta["last_accessed"] = self._now_ts()
        meta["access_count"] = meta.get("access_count", 0) + 1
        self._save_index()

        return {"ok": True, "entry_id": entry_id, "from": tier, "to": "core"}

    def reset_and_rescan(self) -> Dict[str, Any]:
        """重置索引并重新扫描（用于索引损坏时的恢复）"""
        self.index = {
            "version": 1,
            "entries": {},
            "core_usage": {"memory": 0, "user": 0},
            "last_rescan": None,
        }
        result = self.rescan()
        return {"ok": True, "reset": True, **result}

    # ── 自动化入口 ──────────────────────────────────────────────

    def run(self, **kwargs) -> Dict[str, Any]:
        """执行轻量检查（不触发任何写操作）"""
        status = self.check_status()
        stale = self.get_stale_entries()

        # 只在超阈值时标记需要报告，不自动行动
        status_summary = status['needs_report']
        result = {
            "ok": True,
            "message": f"记忆分层：core {status['memory_pct']}%/user {status['user_pct']}%{(' ⚠️需关注' if status_summary else ' ✅正常')}",
            "name": "MemoryTiering",
            "checked": len(self.index["entries"]),
            "core_usage": f"{status['core_usage']['memory']}/{MEMORY_CHAR_LIMIT} ({status['memory_pct']}%)",
            "user_usage": f"{status['core_usage']['user']}/{USER_CHAR_LIMIT} ({status['user_pct']}%)",
            "total_entries": status["total_entries"],
            "tier_counts": status["tier_counts"],
            "last_rescan": status["last_rescan"],
            "needs_report": status["needs_report"],
            "stale_summary": {
                "l1_candidates": len(stale["l1_candidates"]),
                "l2_candidates": len(stale["l2_candidates"]),
                "l3_candidates": len(stale["l3_candidates"]),
            },
        }
        return result

    def status(self) -> Dict[str, Any]:
        """返回详细状态"""
        status = self.check_status()
        stale = self.get_stale_entries()
        status["stale_entries"] = stale
        return status


# 全局单例
_tiering: Optional[MemoryTiering] = None


def get_tiering() -> MemoryTiering:
    global _tiering
    if _tiering is None:
        _tiering = MemoryTiering()
    return _tiering


# ── 兼容旧 API（只读代理）───────────────────────────────

def record_access(entry_id: str):
    """记录记忆被访问（只更新索引中的 last_accessed）"""
    tiering = get_tiering()
    if entry_id in tiering.index["entries"]:
        tiering.index["entries"][entry_id]["last_accessed"] = tiering._now_ts()
        tiering.index["entries"][entry_id]["access_count"] += 1
        tiering._save_index()


def add_entry(content: str, source: str = "memory") -> str:
    """添加记忆（只更新索引，不重复写入 memory 文件）

    注意：新系统不推荐使用此函数直接添加条目。
    记忆添加应通过 memory tool 的标准流程。
    此函数主要用于兼容旧的 add_entry 调用。
    """
    tiering = get_tiering()
    # 检查是否已存在
    eid = tiering._generate_entry_id(content)
    if eid in tiering.index["entries"]:
        record_access(eid)
        return eid

    now = tiering._now_ts()
    tiering.index["entries"][eid] = {
        "id": eid,
        "content_preview": content[:80],
        "source": source,
        "tier": "core",
        "created": now,
        "last_accessed": now,
        "access_count": 1,
    }
    tiering._save_index()
    return eid


def recall(entry_id: str) -> Optional[str]:
    """召回归档的记忆（手动模式）"""
    tiering = get_tiering()
    meta = tiering.index["entries"].get(entry_id, {})
    tier = meta.get("tier", "core")
    if tier == "l1":
        return tiering.recall_from_l1(entry_id) if hasattr(tiering, "recall_from_l1") else None
    elif tier == "l2":
        return tiering.recall_from_l2(entry_id) if hasattr(tiering, "recall_from_l2") else None
    elif tier == "l3":
        return tiering.recall_from_l3(entry_id) if hasattr(tiering, "recall_from_l3") else None
    return None
