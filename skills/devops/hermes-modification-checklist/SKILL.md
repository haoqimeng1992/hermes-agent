---
name: hermes-modification-checklist
description: Hermes 代码修改前必做检查清单 — 先查现有再行动，避免重复造轮子和误删
triggers:
  - 修改 hermes-agent 代码前
  - 创建新文件前
  - 安装 skill 前
  - git 操作前
---

# Hermes 代码修改检查清单

## 核心原则
**先查现有，再行动**。不先查就动手，会重复造轮子或删掉已有的。

---

## 步骤 1：修改文件前

### 1.1 搜索现有实现
```bash
# 搜索相关关键词
rg "keyword" ~/.hermes/hermes-agent/ --max-depth 3

# 查子系统目录（已有9个真实子系统）
ls ~/.hermes/subsystems/

# 查 agent/ 目录
ls ~/.hermes/hermes-agent/agent/
```

### 1.2 查 git 历史（防止误删）
```bash
cd ~/.hermes/hermes-agent
git status --short
# D = deleted | M = modified | ?? = untracked

# 如果看到很多 D，先查清楚
git log --oneline -- path/to/file
```

---

## 步骤 2：创建新文件前

### 2.1 检查是否已存在
```bash
ls ~/.hermes/hermes-agent/agent/ | grep -i name
ls ~/.hermes/subsystems/ | grep -i name
```

### 2.2 目录结构速查
```
hermes-agent/
├── agent/          # 代理核心模块
├── subsystems/     # 子系统包（已有9个真实实现！）
├── tools/         # 工具实现
├── gateway/       # 网关
├── hermes_cli/    # CLI
└── skills/        # 技能包
```

---

## 步骤 3：git 操作前

### 3.1 先看状态
```bash
git status --short
```

### 3.2 验证 push 权限
```bash
git remote -v
gh auth status 2>&1 | head -3
```

### 3.3 不要盲目 `git checkout --`
- 看到很多 `D` 文件时，先 `git restore path/` 恢复，再操作

### 3.4 忽略敏感文件
```bash
echo "config/mcporter.json" >> .gitignore
echo "screenshot-*.png" >> .gitignore
echo ".clawhub/" >> .gitignore
```

---

## 步骤 4：skill 安装前

```bash
# 查是否已存在
ls ~/.hermes/skills/ | grep -i name
ls ~/.hermes/hermes-agent/skills/ | grep -i name

# 同步到 cron 读取的目录
cp -r ~/.hermes/hermes-agent/skills/SKILL_NAME ~/.hermes/skills/
```

---

## 验证清单（修改后必做）

- [ ] 语法检查：`python3 -m py_compile path/to/file.py`
- [ ] 导入测试：`python3 -c "import module_name"`
- [ ] git status 干净，无意外删除
- [ ] 敏感文件已忽略
