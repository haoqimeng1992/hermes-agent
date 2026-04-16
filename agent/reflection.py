# Reflection — 反思层

"""
事后反思与自我改进

反思维度：
- 行为反思（我做错了什么）
- 结果反思（结果是否符合预期）
- 策略反思（方法是否最优）
- 学习反思（学到了什么）

设计原理：
- 反思是进步的起点
- 没有反思的经验只是经历
- 反思需要结构化才能转化为行动
"""

import json
import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional

HERMES_HOME = Path.home() / ".hermes"
REFLECTION_DIR = HERMES_HOME / "knowledge" / "reflection"


class ReflectionType(Enum):
    BEHAVIOR = "behavior"       # 行为反思
    OUTCOME = "outcome"        # 结果反思
    STRATEGY = "strategy"     # 策略反思
    LEARNING = "learning"       # 学习反思


@dataclass
class Reflection:
    """反思记录"""
    id: str
    type: ReflectionType
    content: str                      # 反思内容
    context: str                       # 上下文
    trigger: str                      # 触发反思的事件
    insights: list[str] = field(default_factory=list)  # 洞察
    action_items: list[str] = field(default_factory=list)  # 改进行动
    confidence: float = 0.5         # 反思质量
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    related_reflection_ids: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type.value,
            "content": self.content,
            "context": self.context,
            "trigger": self.trigger,
            "insights": self.insights,
            "action_items": self.action_items,
            "confidence": self.confidence,
            "timestamp": self.timestamp,
            "related_reflection_ids": self.related_reflection_ids,
            "tags": self.tags,
        }
    
    @classmethod
    def from_dict(cls, d: dict) -> "Reflection":
        d["type"] = ReflectionType(d.get("type", "learning"))
        return cls(**d)


@dataclass
class ReflectionSession:
    """反思会话 — 一段时间的反思集合"""
    id: str
    start_time: str
    end_time: Optional[str] = None
    reflections: list[str] = field(default_factory=list)  # 反思ID列表
    summary: str = ""
    key_insights: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "reflections": self.reflections,
            "summary": self.summary,
            "key_insights": self.key_insights,
        }


class ReflectionLayer:
    """
    反思层 — 事后反思与自我改进
    
    核心职责：
    1. 触发反思（基于失败/成功/定时）
    2. 结构化反思记录
    3. 洞察提取
    4. 行动项跟踪
    
    触发 → 记录 → 分析 → 提取洞察 → 行动
    """
    
    def __init__(self):
        REFLECTION_DIR.mkdir(parents=True, exist_ok=True)
        self._reflections: dict[str, Reflection] = {}
        self._sessions: dict[str, ReflectionSession] = {}
        self._current_session: Optional[ReflectionSession] = None
        self._load()
    
    def _load(self):
        """从磁盘加载"""
        reflections_file = REFLECTION_DIR / "reflections.jsonl"
        if reflections_file.exists():
            with open(reflections_file) as f:
                for line in f:
                    if line.strip():
                        d = json.loads(line)
                        r = Reflection.from_dict(d)
                        self._reflections[r.id] = r
        
        sessions_file = REFLECTION_DIR / "sessions.json"
        if sessions_file.exists():
            with open(sessions_file) as f:
                data = json.load(f)
                for d in data.values():
                    self._sessions[d["id"]] = ReflectionSession(**d)
    
    def _save_reflection(self, r: Reflection):
        """保存反思"""
        reflections_file = REFLECTION_DIR / "reflections.jsonl"
        with open(reflections_file, "a") as f:
            f.write(json.dumps(r.to_dict(), ensure_ascii=False) + "\n")
    
    def _save_session(self, s: ReflectionSession):
        """保存会话"""
        sessions_file = REFLECTION_DIR / "sessions.json"
        data = {sid: s.to_dict() for sid, s in self._sessions.items()}
        with open(sessions_file, "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    # === 反思触发 ===
    
    def start_session(self) -> ReflectionSession:
        """开始反思会话"""
        self._current_session = ReflectionSession(
            id=f"session_{datetime.now().strftime('%Y%m%d_%H%M')}",
            start_time=datetime.now().isoformat(),
        )
        return self._current_session
    
    def end_session(self, summary: str = "", key_insights: list[str] = None) -> Optional[ReflectionSession]:
        """结束反思会话"""
        if not self._current_session:
            return None
        
        self._current_session.end_time = datetime.now().isoformat()
        self._current_session.summary = summary
        self._current_session.key_insights = key_insights or []
        
        self._sessions[self._current_session.id] = self._current_session
        self._save_session(self._current_session)
        
        session = self._current_session
        self._current_session = None
        return session
    
    # === 反思记录 ===
    
    def reflect(
        self,
        type: ReflectionType,
        content: str,
        context: str = "",
        trigger: str = "",
        tags: list[str] = None,
    ) -> Reflection:
        """记录反思"""
        reflection = Reflection(
            id=f"ref_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            type=type,
            content=content,
            context=context,
            trigger=trigger,
            tags=tags or [],
        )
        
        self._reflections[reflection.id] = reflection
        self._save_reflection(reflection)
        
        # 如果有当前会话，加入会话
        if self._current_session:
            self._current_session.reflections.append(reflection.id)
        
        return reflection
    
    def reflect_on_failure(
        self,
        task: str,
        failure_reason: str,
        context: str = "",
    ) -> Reflection:
        """反思失败"""
        content = f"任务'{task}'失败。失败原因：{failure_reason}"
        
        reflection = self.reflect(
            type=ReflectionType.BEHAVIOR,
            content=content,
            context=context,
            trigger=f"failure: {task}",
            tags=["failure", "self-improvement"],
        )
        
        # 提取洞察
        reflection.insights = self._extract_insights(reflection)
        
        return reflection
    
    def reflect_on_success(
        self,
        task: str,
        result: str = "",
        context: str = "",
    ) -> Reflection:
        """反思成功"""
        content = f"任务'{task}'成功完成。"
        if result:
            content += f" 结果：{result}"
        
        reflection = self.reflect(
            type=ReflectionType.OUTCOME,
            content=content,
            context=context,
            trigger=f"success: {task}",
            tags=["success", "learning"],
        )
        
        reflection.insights = self._extract_insights(reflection)
        
        return reflection
    
    def reflect_on_learning(
        self,
        content: str,
        context: str = "",
        tags: list[str] = None,
    ) -> Reflection:
        """记录学习反思"""
        reflection = self.reflect(
            type=ReflectionType.LEARNING,
            content=content,
            context=context,
            trigger="learning",
            tags=tags or ["learning"],
        )
        
        reflection.insights = [content]
        
        return reflection
    
    def _extract_insights(self, reflection: Reflection) -> list[str]:
        """从反思中提取洞察"""
        # 简单的关键词提取
        insights = []
        
        if "失败" in reflection.content or "error" in reflection.content.lower():
            insights.append("从失败中学习是进步的关键")
        
        if "成功" in reflection.content:
            insights.append("确认有效的策略")
        
        return insights
    
    # === 反思检索 ===
    
    def get_recent(self, limit: int = 20) -> list[Reflection]:
        """获取最近的反思"""
        reflections = list(self._reflections.values())
        reflections.sort(key=lambda r: r.timestamp, reverse=True)
        return reflections[:limit]
    
    def get_by_type(self, type: ReflectionType, limit: int = 20) -> list[Reflection]:
        """按类型获取"""
        reflections = [
            r for r in self._reflections.values()
            if r.type == type
        ]
        reflections.sort(key=lambda r: r.timestamp, reverse=True)
        return reflections[:limit]
    
    def get_action_items(self) -> list[str]:
        """获取所有待执行行动项"""
        action_items = []
        for r in self._reflections.values():
            action_items.extend(r.action_items)
        return action_items
    
    def get_key_insights(self, limit: int = 10) -> list[str]:
        """获取关键洞察"""
        insights = []
        for r in self._reflections.values():
            insights.extend(r.insights)
        
        # 去重
        seen = set()
        unique = []
        for i in insights:
            if i not in seen:
                seen.add(i)
                unique.append(i)
        
        return unique[:limit]
    
    # === 摘要 ===
    
    def get_summary(self) -> dict:
        """获取反思层摘要"""
        type_counts = {}
        for rt in ReflectionType:
            type_counts[rt.value] = len([r for r in self._reflections.values() if r.type == rt])
        
        return {
            "total_reflections": len(self._reflections),
            "type_distribution": type_counts,
            "total_sessions": len(self._sessions),
            "key_insights": self.get_key_insights(5),
            "pending_action_items": len(self.get_action_items()),
        }


# 全局单例
_reflection: Optional[ReflectionLayer] = None

def get_reflection() -> ReflectionLayer:
    global _reflection
    if _reflection is None:
        _reflection = ReflectionLayer()
    return _reflection
