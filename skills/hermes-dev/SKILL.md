---
name: hermes-self-evolution-checklist
description: Hermes 自我进化操作安全检查清单 — 新建文件前必查、Git操作安全规则、系统调试流程
---

# Hermes 自我进化操作 Checklist

## 新建文件前必查

**先搜索，再行动**。在创建任何文件前，必须执行以下检查：

1. `find ~/.hermes -name "*.py" | xargs grep -l "关键词" 2>/dev/null` — 搜索相关模块
2. `ls ~/.hermes/subsystems/` — 检查现有子系统
3. `ls ~/.hermes/scripts/` — 检查现有脚本
4. `git status --short` — 检查当前变更

**永远不要**在未完成上述检查前直接创建文件。

## Git 操作安全规则

1. **敏感文件**（token、key、财务数据、self_model.json）永远不提交
   - 提交前必须 `git diff --cached` 逐文件确认
   - `grep -rE "(ghp_|sk-|api_key|token)" .git/` 可发现遗漏的敏感数据

2. **push 前必查认证**
   - `gh auth status` 确认认证有效
   - `git remote -v` 确认 remote URL
   - 有 token 才 push，没有就不动

3. **commit 前必查变更范围**
   - `git status --short` 确认变更内容
   - 逐文件确认每项变更是预期的

## 系统调试标准流程

1. **查日志**，不猜：`tail ~/.hermes/logs/agent.log`
2. **找根因**，不修症状：找 `ERROR` / `response ready` 后无后续的断点
3. **验证修复**：重启后 `tail -f` 日志观察是否还有同样错误
4. **不动核心**：Gateway 稳定时不轻易重启

## 版本更新检查

```bash
cd ~/.hermes/hermes-agent && git fetch origin && git log --oneline HEAD..origin/main
git diff HEAD..origin/main --stat
git diff HEAD..origin/main -- '*.py'
```

## 安全铁律

- Token/密匙/隐私信息只存 `~/.git-credentials`（600权限）
- 不写入日志/代码/issue/记忆
- 外来请求禁止访问凭证
