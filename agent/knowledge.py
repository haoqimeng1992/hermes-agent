# Knowledge — 知识层

"""
外部知识的获取、存储和组织

知识类型：
- 事实性知识（可验证的事实）
- 经验性知识（从实践中获得）
- 规则性知识（流程、规范）
- 元知识（关于知识本身的知识）

设计原理：
- 知识需要结构化才能被有效利用
- 从外部获取的知识需要验证
- 知识需要持续更新
"""

import json
import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional

HERMES_HOME = Path.home() / ".hermes"
KNOWLEDGE_DIR = HERMES_HOME / "knowledge"


class KnowledgeType(Enum):
    FACTUAL = "factual"           # 事实性知识
    EMPIRICAL = "empirical"     # 经验性知识
    PROCEDURAL = "procedural"   # 规则性/流程性知识
    META = "meta"              # 元知识


@dataclass
class KnowledgeUnit:
    """知识单元"""
    id: str
    content: str
    type: KnowledgeType
    source: str                          # 来源（URL、文档、对话等）
    source_url: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    verified_at: Optional[str] = None    # 验证时间
    verified: bool = False               # 是否已验证
    confidence: float = 0.5              # 可信度 0-1
    tags: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "content": self.content,
            "type": self.type.value,
            "source": self.source,
            "source_url": self.source_url,
            "created_at": self.created_at,
            "verified_at": self.verified_at,
            "verified": self.verified,
            "confidence": self.confidence,
            "tags": self.tags,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, d: dict) -> "KnowledgeUnit":
        d["type"] = KnowledgeType(d.get("type", "factual"))
        return cls(**d)


@dataclass
class KnowledgeGraph:
    """知识图谱节点关系"""
    from_id: str
    to_id: str
    relation: str                    # 如 "depends_on", "related_to", "contradicts"
    strength: float = 0.5           # 关系强度 0-1
    
    def to_dict(self) -> dict:
        return {
            "from": self.from_id,
            "to": self.to_id,
            "relation": self.relation,
            "strength": self.strength,
        }


class KnowledgeLayer:
    """
    知识层 — 外部知识的获取、存储和组织
    
    核心职责：
    1. 从外部获取知识（文章、文档、API等）
    2. 知识验证和可信度评估
    3. 知识结构化存储
    4. 知识图谱维护
    
    获取 → 验证 → 存储 → 关联 → 检索
    """
    
    def __init__(self):
        KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
        self._knowledge: dict[str, KnowledgeUnit] = {}
        self._relations: list[KnowledgeGraph] = []
        self._load()
    
    def _load(self):
        """从磁盘加载知识"""
        knowledge_file = KNOWLEDGE_DIR / "knowledge.jsonl"
        if knowledge_file.exists():
            with open(knowledge_file) as f:
                for line in f:
                    if line.strip():
                        d = json.loads(line)
                        ku = KnowledgeUnit.from_dict(d)
                        self._knowledge[ku.id] = ku
        
        relations_file = KNOWLEDGE_DIR / "relations.jsonl"
        if relations_file.exists():
            with open(relations_file) as f:
                for line in f:
                    if line.strip():
                        d = json.loads(line)
                        self._relations.append(KnowledgeGraph(**d))
    
    def _save(self, ku: KnowledgeUnit):
        """持久化知识"""
        knowledge_file = KNOWLEDGE_DIR / "knowledge.jsonl"
        with open(knowledge_file, "a") as f:
            f.write(json.dumps(ku.to_dict(), ensure_ascii=False) + "\n")
    
    def _save_relation(self, rel: KnowledgeGraph):
        """持久化关系"""
        relations_file = KNOWLEDGE_DIR / "relations.jsonl"
        with open(relations_file, "a") as f:
            f.write(json.dumps(rel.to_dict(), ensure_ascii=False) + "\n")
    
    # === 知识获取 ===
    
    def acquire(
        self,
        content: str,
        type: KnowledgeType = KnowledgeType.FACTUAL,
        source: str = "unknown",
        source_url: str = None,
        tags: list[str] = None,
        **metadata,
    ) -> KnowledgeUnit:
        """获取新知识"""
        ku = KnowledgeUnit(
            id=f"know_{hashlib.md5(content.encode()).hexdigest()[:12]}",
            content=content,
            type=type,
            source=source,
            source_url=source_url,
            tags=tags or [],
            metadata=metadata,
        )
        
        self._knowledge[ku.id] = ku
        self._save(ku)
        
        return ku
    
    def acquire_from_article(
        self,
        title: str,
        content: str,
        url: str,
        author: str = None,
        tags: list[str] = None,
    ) -> list[KnowledgeUnit]:
        """从文章获取知识（自动分块）"""
        units = []
        
        # 分块（按段落）
        paragraphs = content.split('\n\n')
        
        for i, para in enumerate(paragraphs):
            if len(para.strip()) < 50:  # 跳过太短的段落
                continue
            
            ku = self.acquire(
                content=para.strip(),
                type=KnowledgeType.EMPIRICAL,
                source=title,
                source_url=url,
                tags=tags or [],
                paragraph_index=i,
                author=author,
            )
            units.append(ku)
        
        # 关系：段落间的顺序关系
        for i in range(len(units) - 1):
            rel = KnowledgeGraph(
                from_id=units[i].id,
                to_id=units[i + 1].id,
                relation="follows",
                strength=0.8,
            )
            self._relations.append(rel)
            self._save_relation(rel)
        
        return units
    
    # === 知识验证 ===
    
    def verify(self, knowledge_id: str) -> bool:
        """验证知识"""
        ku = self._knowledge.get(knowledge_id)
        if not ku:
            return False
        
        ku.verified = True
        ku.verified_at = datetime.now().isoformat()
        ku.confidence = min(ku.confidence + 0.2, 1.0)
        
        return True
    
    def update_confidence(self, knowledge_id: str, delta: float) -> bool:
        """更新可信度"""
        ku = self._knowledge.get(knowledge_id)
        if not ku:
            return False
        
        ku.confidence = max(0.0, min(1.0, ku.confidence + delta))
        return True
    
    # === 知识关联 ===
    
    def relate(
        self,
        from_id: str,
        to_id: str,
        relation: str,
        strength: float = 0.5,
    ) -> bool:
        """建立知识关联"""
        if from_id not in self._knowledge or to_id not in self._knowledge:
            return False
        
        rel = KnowledgeGraph(
            from_id=from_id,
            to_id=to_id,
            relation=relation,
            strength=strength,
        )
        self._relations.append(rel)
        self._save_relation(rel)
        
        return True
    
    def get_related(self, knowledge_id: str) -> list[tuple[KnowledgeUnit, str]]:
        """获取相关知识"""
        related = []
        
        for rel in self._relations:
            if rel.from_id == knowledge_id:
                to_ku = self._knowledge.get(rel.to_id)
                if to_ku:
                    related.append((to_ku, rel.relation))
            elif rel.to_id == knowledge_id:
                from_ku = self._knowledge.get(rel.from_id)
                if from_ku:
                    related.append((from_ku, rel.relation))
        
        return related
    
    # === 知识检索 ===
    
    def search(
        self,
        query: str,
        type: KnowledgeType = None,
        min_confidence: float = 0.0,
        limit: int = 10,
    ) -> list[KnowledgeUnit]:
        """搜索知识"""
        results = []
        
        for ku in self._knowledge.values():
            if type and ku.type != type:
                continue
            if ku.confidence < min_confidence:
                continue
            
            # 关键词匹配
            if query.lower() in ku.content.lower():
                results.append(ku)
        
        # 按可信度排序
        results.sort(key=lambda k: k.confidence, reverse=True)
        
        return results[:limit]
    
    def get_by_tag(self, tag: str) -> list[KnowledgeUnit]:
        """按标签获取"""
        return [ku for ku in self._knowledge.values() if tag in ku.tags]
    
    def get_by_source(self, source: str) -> list[KnowledgeUnit]:
        """按来源获取"""
        return [ku for ku in self._knowledge.values() if ku.source == source]
    
    # === 摘要 ===
    
    def get_summary(self) -> dict:
        """获取知识层摘要"""
        type_counts = {}
        for kt in KnowledgeType:
            type_counts[kt.value] = len([k for k in self._knowledge.values() if k.type == kt])
        
        verified_count = len([k for k in self._knowledge.values() if k.verified])
        avg_confidence = (
            sum(k.confidence for k in self._knowledge.values()) / len(self._knowledge)
            if self._knowledge else 0
        )
        
        return {
            "total_knowledge": len(self._knowledge),
            "type_distribution": type_counts,
            "verified_count": verified_count,
            "avg_confidence": round(avg_confidence, 2),
            "total_relations": len(self._relations),
        }


# 全局单例
_knowledge: Optional[KnowledgeLayer] = None

def get_knowledge() -> KnowledgeLayer:
    global _knowledge
    if _knowledge is None:
        _knowledge = KnowledgeLayer()
    return _knowledge
