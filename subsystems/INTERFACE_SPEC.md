# Hermes 活子系统接口规范

> 来源：计划文档 + 实际实现合并后的统一规范
> 日期：2026-04-15

---

## 1. Governance — 治理层

### record_action
```python
def record_action(
    action: Union[Dict, str],   # 操作 dict 或 str（兼容旧数据）
    result: str,                 # 操作结果
    risk_level: str = "low",     # low/medium/high/critical
    quality_score: float = 1.0,  # 质量评分 0.0~1.0
    details: str = "",
)
```

### block_action
```python
def block_action(action: Dict, agent_goal: str) -> bool:
    """预检操作。返回 True=拦截，False=放行。
    
    action dict 示例:
      {"type": "terminal", "command": "rm -rf /"}
      {"type": "execute_code", "code": "import os; os.system('rm -rf /')"}
      {"type": "delegate", "goal": "delete all files"}
    """
```

---

## 2. Orchestrator — 编排系统

### recommend
```python
def recommend(task_description: str) -> Dict[str, Any]:
    """返回完整推荐对象。
    
    Returns:
        {
            "pattern": str,           # 模式名称，如 "triangular_review"
            "pattern_desc": str,      # 模式描述
            "reasoning": str,         # 推理过程
            "confidence": float,       # 置信度 0.0~1.0
            "alternatives": List[Dict]  # 备选方案
        }
    """
```

---

## 3. ReflectiveEvolution — 反思进化

### add_learning
```python
def add_learning(
    category: str,           # 分类，如 "terminal", "api"
    lesson: str,             # 教训内容
    tags: List[str] = None, # 标签列表
    confidence: float = 0.8, # 置信度 0.0~1.0
) -> Dict
```

---

## 4. ScienceLoop — 科学循环

### evaluate_hypothesis
```python
def evaluate_hypothesis(
    hypothesis_id: str,
    verdict: str,                    # retain/discard/modify
    evaluation_data: Dict = None,     # 详细评估数据
) -> Dict:
    """
    evaluation_data 示例:
        {"metrics": {"efficiency_gain": 0.15}, "reasoning": "分析理由"}
    """
```

---

## 5. FitnessBuilder — 适应度构建

### create_function
```python
def create_function(
    name: str,                    # 函数名称
    target: str,                  # 目标描述
    dimensions: List[Dict],       # 维度列表
) -> Dict:
    """
    dimensions 示例:
        [
            {"name": "效率", "weight": 0.4},
            {"name": "可维护性", "weight": 0.3},
            {"name": "安全性", "weight": 0.3},
        ]
    """
```

---

## 所有子系统的 run() / status() 统一返回格式

### run()
```python
{
    "ok": True,
    "message": "中文摘要消息",
    "details": {
        # 子系统具体数据
    }
}
```

### status()
```python
{
    "ok": True,
    "name": "子系统名",
    # 子系统具体字段
}
```
