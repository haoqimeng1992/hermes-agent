"""
Living Core — Hermes Living System 核心集成
=============================================
把 hermes-living 插件的7个功能拆解为独立子系统

7个功能模块:
1. SemanticRecall — 语义记忆召回 (embedding recall)
2. Governance — 危险命令拦截 (已在 subsystems/governance.py)
3. OrchestratorHint — 任务编排建议 (已在 subsystems/orchestrator.py)
4. ScienceLoopHint — 假设检测 (已在 subsystems/science_loop.py)
5. WechatUrlDetect — 公众号链接检测
6. PostLLMUpdate — SelfModel/Identity/Reflective/Metacognitive 自动更新
7. FitnessEvaluate — FitnessBuilder 代码质量评估 (已在 subsystems/fitness_builder.py)

每个模块独立可调用，失败隔离，不影响其他模块。
"""

import json
import logging
import os
import re
import sys
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

HERMES_HOME = Path.home() / ".hermes"
sys.path.insert(0, str(HERMES_HOME))


# ---------------------------------------------------------------------------
# 1. SemanticRecall — 语义记忆召回
# ---------------------------------------------------------------------------

class SemanticRecall:
    """语义记忆召回 — 基于embedding的技能检索"""

    def __init__(self):
        self._initialized = False

    def _ensure_init(self):
        if self._initialized:
            return
        try:
            hybrid_path = HERMES_HOME / "knowledge" / "hybrid-index"
            if hybrid_path.exists():
                sys.path.insert(0, str(hybrid_path))
                from hybrid_search import smart_search, init as hs_init
                hs_init()
                self._initialized = True
                logger.info("[SemanticRecall] hybrid-search initialized")
        except Exception as e:
            logger.warning(f"[SemanticRecall] init failed: {e}")

    def recall(self, query: str, top_k: int = 2) -> list:
        """语义检索，返回 [(skill_name, score, desc), ...]"""
        self._ensure_init()
        if not self._initialized:
            return []

        try:
            from hybrid_search import smart_search
            result = smart_search(query, top_k=top_k)
            return [(s['name'], score, s.get('desc', '')) 
                    for s, score in result.get('results', [])]
        except Exception as e:
            logger.debug(f"[SemanticRecall] search failed: {e}")
            return []

    def recall_to_string(self, query: str) -> str | None:
        """生成hook注入字符串"""
        results = self.recall(query, top_k=2)
        if not results:
            return None

        signals = ["怎么", "为什么", "如何", "怎么办", "什么问题",
                   "报错", "出错", "失败", "解决", "debug", "fix",
                   "接入", "集成", "改造", "重构", "优化"]
        if not any(s in query.lower() for s in signals):
            return None

        lines = ["[语义记忆召回]", "相关技能:"]
        for name, score, desc in results:
            lines.append(f"  • {name} (相关度:{score:.2f}): {desc[:80]}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# 2. WechatUrlDetect — 公众号链接检测
# ---------------------------------------------------------------------------

class WechatUrlDetect:
    """检测消息中的公众号链接，返回读取提示"""

    def detect(self, text: str) -> str | None:
        if not text:
            return None
        pattern = r'https?://mp\.weixin\.qq\.com/s[^\s））\]]+'
        urls = re.findall(pattern, text)
        if not urls:
            return None
        return (f"\n\n[提示: 检测到微信公众号链接，"
                f"可用 `node ~/.hermes/skills/wechat-reader/scripts/read_wechat.js \"{urls[0]}\" --plain` 读取文章正文]")


# ---------------------------------------------------------------------------
# 3. PostLLMUpdate — 多子系统自动更新
# ---------------------------------------------------------------------------

class PostLLMUpdate:
    """每轮对话结束后自动更新多个子系统"""

    def update(self, user_message: str, assistant_response: str,
               conversation_history: list, platform: str = 'feishu') -> None:
        """执行所有后更新"""
        # 3a. SelfModel
        self._update_selfmodel(assistant_response)
        # 3b. IdentityEvolution
        self._update_identity(assistant_response)
        # 3c. ReflectiveEvolution
        self._update_reflective(user_message, conversation_history)
        # 3d. Metacognitive
        self._update_metacognitive(conversation_history)

    def _update_selfmodel(self, response: str) -> None:
        try:
            from subsystems import SelfModel
            sm = SelfModel()
            success = bool(response and len(response) > 10)
            success = success and not any(e in response for e in ['无法', '不能', '错误', '失败'])
            sm.increment_interaction(success=success)
        except Exception as e:
            logger.debug(f"[PostLLMUpdate] SelfModel failed: {e}")

    def _update_identity(self, response: str) -> None:
        try:
            from subsystems import IdentityEvolution
            ie = IdentityEvolution()
            if len(response) > 500:
                ie.adapt('verbosity_up', 1.0)
            elif len(response) < 100:
                ie.adapt('verbosity_down', 0.5)
            code_indicators = ['```', 'def ', 'class ', 'import ', 'python', '代码']
            if any(ind in response for ind in code_indicators):
                ie.adapt('more_code', 0.8)
            text_indicators = ['我认为', '我觉得', '总结', '详细']
            if any(ind in response for ind in text_indicators):
                ie.adapt('more_text', 0.8)
        except Exception as e:
            logger.debug(f"[PostLLMUpdate] Identity failed: {e}")

    def _update_reflective(self, user_msg: str, history: list) -> None:
        try:
            from subsystems import ReflectiveEvolution
            re_sub = ReflectiveEvolution()
            signals = ["完成了", "搞定", "好了", "已修复", "已解决",
                      "已经", "成功", "好哒", "可以了"]
            if not any(s in user_msg for s in signals):
                return
            tool_calls = []
            for msg in reversed(history):
                if msg.get('role') == 'assistant' and msg.get('tool_calls'):
                    for tc in msg['tool_calls']:
                        tool_calls.append(tc.get('function', {}).get('name', ''))
                    break
            if tool_calls:
                re_sub.add_learning(
                    category='task_completion',
                    lesson=f"使用{tool_calls[0]}完成了任务",
                    tags=['task', tool_calls[0]],
                    confidence=0.8
                )
        except Exception as e:
            logger.debug(f"[PostLLMUpdate] Reflective failed: {e}")

    def _update_metacognitive(self, history: list) -> None:
        try:
            from subsystems import Metacognitive
            mc = Metacognitive()
            user_turns = len([m for m in history if m.get('role') == 'user'])
            if user_turns >= 6:
                mc.reflect(
                    topic="对话过程",
                    observation=f"共进行了{user_turns}轮对话",
                    conclusion=""
                )
        except Exception as e:
            logger.debug(f"[PostLLMUpdate] Metacognitive failed: {e}")


# ---------------------------------------------------------------------------
# 4. OrchestratorHint — 任务编排建议 (轻量包装)
# ---------------------------------------------------------------------------

class OrchestratorHint:
    """检测用户是否在描述任务，提供编排建议"""

    def check(self, text: str) -> str | None:
        if not text:
            return None
        signals = ["帮我", "写一个", "做一个", "开发", "实现", "修复",
                  "搭建", "配置", "部署", "生成",
                  "接入", "集成", "改造", "重构", "优化"]
        if not any(s in text for s in signals):
            return None
        try:
            from subsystems import Orchestrator
            o = Orchestrator()
            result = o.recommend(text)
            if not result:
                return None
            hint = f"\n\n[Orchestrator任务编排] {result.get('hint', '')}"
            if result.get('steps'):
                hint += " 建议步骤：" + " → ".join(result['steps'][:3])
            elif result.get('pattern'):
                hint += f" 推荐模式：{result.get('pattern')}"
            return hint
        except Exception as e:
            logger.debug(f"[OrchestratorHint] failed: {e}")
            return None


# ---------------------------------------------------------------------------
# 5. ScienceLoopHint — 假设检测 (轻量包装)
# ---------------------------------------------------------------------------

class ScienceLoopHint:
    """检测用户消息中的假设，给出相关假设的提示"""

    def check(self, text: str) -> str | None:
        if not text:
            return None
        signals = ["应该是", "可能", "大概", "估计", "假设",
                  "如果", "要不要", "会不会", "应该先", "我觉得"]
        if not any(s in text for s in signals):
            return None
        try:
            from subsystems import ScienceLoop
            sl = ScienceLoop()
            status = sl.status()
            hypotheses = status.get('hypotheses', []) if isinstance(status, dict) else []
            if not hypotheses:
                return None
            lines = ["\n\n[ScienceLoop 活跃假设参考]"]
            for h in hypotheses[:3]:
                lines.append(f"  • [{h.get('id','?')}] {h.get('statement','')[:60]}")
            return "\n".join(lines)
        except Exception as e:
            logger.debug(f"[ScienceLoopHint] failed: {e}")
            return None


# ---------------------------------------------------------------------------
# 统一LivingCore — 所有功能集合
# ---------------------------------------------------------------------------

class LivingCore:
    """
    统一LivingCore — 整合所有7个功能模块
    供 hermes-living 插件调用，也供 subsystem_runner 直接调度
    """
    def __init__(self):
        self.semantic_recall = SemanticRecall()
        self.wechat_detect = WechatUrlDetect()
        self.post_update = PostLLMUpdate()
        self.orchestrator_hint = OrchestratorHint()
        self.science_loop_hint = ScienceLoopHint()

    def pre_llm_hooks(self, user_message: str) -> list[str]:
        """执行所有pre_llm hook，返回注入字符串列表"""
        results = []
        # 1. 语义记忆召回
        recall = self.semantic_recall.recall_to_string(user_message)
        if recall:
            results.append(recall)
        # 2. 公众号链接检测
        wechat = self.wechat_detect.detect(user_message)
        if wechat:
            results.append(wechat)
        # 3. Orchestrator编排建议
        orch = self.orchestrator_hint.check(user_message)
        if orch:
            results.append(orch)
        # 4. ScienceLoop假设检测
        science = self.science_loop_hint.check(user_message)
        if science:
            results.append(science)
        return results

    def post_llm_update(self, user_message: str, assistant_response: str,
                        conversation_history: list, platform: str = 'feishu') -> None:
        """执行所有post_llm update"""
        self.post_update.update(user_message, assistant_response,
                               conversation_history, platform)

    def status(self) -> dict:
        """子系统状态"""
        return {
            "semantic_recall": self.semantic_recall._initialized,
            "modules": ["SemanticRecall", "WechatUrlDetect", "PostLLMUpdate",
                       "OrchestratorHint", "ScienceLoopHint"]
        }
