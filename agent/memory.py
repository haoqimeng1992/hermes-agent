# Memory — 记忆层

"""
存储和检索经验

记忆分层：
- Core层：核心事实，持续保留
- User层：用户偏好，长期保留
- Context层：当前会话，短期
- Archive层：冷数据，压缩归档

设计原理：
- 不是所有记忆都一样重要
- 根据重要性动态调整保留策略
- 定期整合和遗忘
"""

import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional

HERMES_HOME = Path.home() / ".hermes"
MEMORY_DIR = HERMES_HOME / "knowledge" / "memory"


class MemoryTier(Enum):
    CORE = "core"           # 核心事实，永远保留
    USER = "user"          # 用户偏好，长期保留
    CONTEXT = "context"     # 当前会话，短期
    ARCHIVE = "archive"    # 冷数据，压缩归档


@dataclass
class MemoryEntry:
    """记忆条目"""
    id: str
    content: str
    tier: MemoryTier
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    access_count: int = 0
    last_accessed: Optional[str] = None
    importance: float = 0.5          # 重要性 0-1
    tags: list[str] = field(default_factory=list)
    source: str = "unknown"
    metadata: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "content": self.content,
            "tier": self.tier.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "access_count": self.access_count,
            "last_accessed": self.last_accessed,
            "importance": self.importance,
            "tags": self.tags,
            "source": self.source,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, d: dict) -> "MemoryEntry":
        d["tier"] = MemoryTier(d.get("tier", "context"))
        return cls(**d)


class MemoryLayer:
    """
    记忆层 — 存储和检索经验
    
    核心职责：
    1. 分层存储记忆
    2. 动态升降级
    3. 智能检索
    4. 遗忘机制
    
    感知 → 记忆存储 → 分类 → 检索 → 遗忘
    """
    
    def __init__(self):
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        self._entries: dict[str, MemoryEntry] = {}
        self._load()
    
    def _load(self):
        """从磁盘加载记忆"""
        for tier in MemoryTier:
            tier_file = MEMORY_DIR / f"{tier.value}.jsonl"
            if tier_file.exists():
                with open(tier_file) as f:
                    for line in f:
                        if line.strip():
                            d = json.loads(line)
                            entry = MemoryEntry.from_dict(d)
                            self._entries[entry.id] = entry
    
    def _save(self, entry: MemoryEntry):
        """持久化单条记忆"""
        tier_file = MEMORY_DIR / f"{entry.tier.value}.jsonl"
        with open(tier_file, "a") as f:
            f.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")
    
    # === 存储 ===
    
    def store(
        self,
        content: str,
        tier: MemoryTier = MemoryTier.CONTEXT,
        importance: float = 0.5,
        tags: list[str] = None,
        source: str = "unknown",
        **metadata,
    ) -> MemoryEntry:
        """存储新记忆"""
        import hashlib
        entry_id = f"mem_{hashlib.md5(content.encode()).hexdigest()[:12]}"
        
        # 检查是否已存在
        if entry_id in self._entries:
            entry = self._entries[entry_id]
            entry.access_count += 1
            entry.last_accessed = datetime.now().isoformat()
            return entry
        
        entry = MemoryEntry(
            id=entry_id,
            content=content,
            tier=tier,
            importance=importance,
            tags=tags or [],
            source=source,
            metadata=metadata,
        )
        
        self._entries[entry_id] = entry
        self._save(entry)
        
        # 自动升级检查
        self._check_upgrade(entry)
        
        return entry
    
    def store_core(self, content: str, **kwargs) -> MemoryEntry:
        """存储核心记忆"""
        return self.store(content, tier=MemoryTier.CORE, importance=0.9, **kwargs)
    
    def store_user(self, content: str, **kwargs) -> MemoryEntry:
        """存储用户偏好"""
        return self.store(content, tier=MemoryTier.USER, importance=0.7, **kwargs)
    
    def store_context(self, content: str, **kwargs) -> MemoryEntry:
        """存储上下文记忆"""
        return self.store(content, tier=MemoryTier.CONTEXT, importance=0.3, **kwargs)
    
    # === 检索 ===
    
    def retrieve(self, query: str, tier: MemoryTier = None, limit: int = 10) -> list[MemoryEntry]:
        """检索记忆"""
        results = []
        
        for entry in self._entries.values():
            if tier and entry.tier != tier:
                continue
            
            # 简单关键词匹配
            if query.lower() in entry.content.lower():
                entry.last_accessed = datetime.now().isoformat()
                entry.access_count += 1
                results.append(entry)
        
        # 按重要性排序
        results.sort(key=lambda e: e.importance, reverse=True)
        
        return results[:limit]
    
    def retrieve_by_tag(self, tag: str, limit: int = 10) -> list[MemoryEntry]:
        """按标签检索"""
        results = [
            e for e in self._entries.values()
            if tag in e.tags
        ]
        results.sort(key=lambda e: e.importance, reverse=True)
        return results[:limit]
    
    def get_recent(self, tier: MemoryTier = None, limit: int = 20) -> list[MemoryEntry]:
        """获取最近记忆"""
        entries = list(self._entries.values())
        if tier:
            entries = [e for e in entries if e.tier == tier]
        
        entries.sort(key=lambda e: e.created_at, reverse=True)
        return entries[:limit]
    
    def get_core(self) -> list[MemoryEntry]:
        """获取核心记忆"""
        return self.retrieve("", tier=MemoryTier.CORE, limit=100)
    
    def get_user_preferences(self) -> list[MemoryEntry]:
        """获取用户偏好"""
        return self.retrieve("", tier=MemoryTier.USER, limit=100)
    
    # === 升降级 ===
    
    def _check_upgrade(self, entry: MemoryEntry):
        """检查是否需要升级"""
        # 高访问频率 → 升级
        if entry.access_count >= 5 and entry.tier == MemoryTier.CONTEXT:
            self._upgrade(entry)
        
        # 低访问频率 → 降级
        if entry.access_count == 0 and entry.tier == MemoryTier.CORE:
            self._downgrade(entry)
    
    def _upgrade(self, entry: MemoryEntry):
        """升级记忆层级"""
        tier_order = [MemoryTier.CONTEXT, MemoryTier.USER, MemoryTier.CORE]
        current_idx = tier_order.index(entry.tier)
        if current_idx < len(tier_order) - 1:
            entry.tier = tier_order[current_idx + 1]
            entry.importance = min(entry.importance + 0.1, 1.0)
            entry.updated_at = datetime.now().isoformat()
            self._save(entry)
    
    def _downgrade(self, entry: MemoryEntry):
        """降级记忆层级"""
        tier_order = [MemoryTier.CONTEXT, MemoryTier.USER, MemoryTier.CORE, MemoryTier.ARCHIVE]
        current_idx = tier_order.index(entry.tier)
        if current_idx < len(tier_order) - 1:
            entry.tier = tier_order[current_idx + 1]
            entry.importance = max(entry.importance - 0.1, 0.0)
            entry.updated_at = datetime.now().isoformat()
            self._save(entry)
    
    # === 遗忘 ===
    
    def forget(self, entry_id: str) -> bool:
        """遗忘指定记忆"""
        if entry_id in self._entries:
            del self._entries[entry_id]
            return True
        return False
    
    def prune(self, max_entries: int = 1000):
        """修剪低重要性记忆"""
        entries = list(self._entries.values())
        entries.sort(key=lambda e: e.importance)
        
        removed = 0
        for entry in entries[:-max_entries]:
            if entry.tier != MemoryTier.CORE:  # 核心记忆不删除
                self.forget(entry.id)
                removed += 1
        
        return removed
    
    # === 摘要 ===
    
    def get_summary(self) -> dict:
        """获取记忆层摘要"""
        tier_counts = {}
        for tier in MemoryTier:
            tier_counts[tier.value] = len([e for e in self._entries.values() if e.tier == tier])
        
        return {
            "total_entries": len(self._entries),
            "tier_distribution": tier_counts,
            "core_count": tier_counts.get("core", 0),
            "user_count": tier_counts.get("user", 0),
            "context_count": tier_counts.get("context", 0),
            "archive_count": tier_counts.get("archive", 0),
            "total_accesses": sum(e.access_count for e in self._entries.values()),
        }


# 全局单例
_memory: Optional[MemoryLayer] = None

def get_memory() -> MemoryLayer:
    global _memory
    if _memory is None:
        _memory = MemoryLayer()
    return _memory
