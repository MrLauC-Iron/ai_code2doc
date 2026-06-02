# Task-Context 技能实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增 task-context 技能，在实现任务前通过结构化问答补全业务背景，并将知识沉淀到项目文档。

**Architecture:** 新建独立 skill 文件 `skills/task-context/SKILL.md`，定义 12 步流程编排。业务背景问答产出两类持久化文件：模块文档（`.fuxian/modules/`）和任务上下文（`.fuxian/tasks/`）。传输层通过插件命令 `fuxian pull-module / push-task` 封装，skill 中 Bash 调用。同步修改 `using-fuxian` 的技能优先级。

**Tech Stack:** Markdown (skills), Bash (plugin commands)

---

## 文件清单

| 文件 | 职责 | 操作 |
|------|------|------|
| `skills/task-context/SKILL.md` | task-context 技能主体 | 新建 |
| `skills/using-fuxian/SKILL.md` | 技能优先级和调度规则 | 修改 |
| `.fuxian/bin/fuxian` | 插件命令入口（pull-module / push-task） | 新建 |

---

### Task 1: 创建 task-context 技能

**Files:**
- Create: `skills/task-context/SKILL.md`

- [ ] **Step 1: 创建 skills/task-context/SKILL.md**

```markdown
---
name: task-context
description: 在任何实现任务开始前使用 — 补全业务背景，确保 AI 理解任务的全貌后再进入设计和实现阶段
---

在存量项目中，AI 往往不了解功能的业务全貌。此技能通过结构化问答补全业务背景，确保实现不偏离业务意图。

<硬性门禁>
不要跳过业务背景问答直接进入实现。即使任务看起来很简单，也至少确认涉及模块和预期行为。
</硬性门禁>

## 技能类型

灵活型。对于非常简单的任务（如修改一行配置），可以快速确认后跳过，但不能完全跳过。

## 流程清单

你必须为以下每个条目创建任务并按顺序完成：

1. **读取项目基础信息** — 检查 docs/Project_Basic.md
2. **生成或提取** — 不存在则扫描代码并提示用户创建；存在则提取模块信息
3. **确认涉及模块** — 询问用户任务涉及哪些模块（提示已有模块列表）
4. **拉取模块文档** — 通过插件命令获取最新模块文档
5. **读取已有知识** — 读取模块文档 + Project_Basic.md 中对应信息
6. **差异分析** — 已有知识 vs 任务所需知识
7. **定向提问** — 只问未知或变化的业务背景
8. **输出摘要** — 结构化任务理解摘要
9. **用户确认** — 确认或补充
10. **落盘存储** — 保存到 .fuxian/tasks/
11. **回传任务上下文** — 通过插件命令推送到远程
12. **更新模块文档** — 将新知识增量更新到对应模块文档

## 详细流程

### 第一步：读取项目基础信息

检查项目根目录下是否存在 `docs/Project_Basic.md`。

### 第二步：生成或提取

**如果 Project_Basic.md 存在：**
- 提取项目背景和核心模块列表（模块名、功能描述、代码目录）
- 这些信息将作为后续提问的上下文

**如果 Project_Basic.md 不存在：**
- 扫描项目代码结构，识别主要目录和模块
- 生成一份 Project_Basic.md 的建议内容
- 提示用户确认或修改，保存到 `docs/Project_Basic.md`
- 这是项目的基础信息文件，后续由用户团队维护

### 第三步：确认涉及模块

向用户定向提问：此次任务涉及哪些模块。

**如果 Project_Basic.md 中有模块列表：**
- 以多选题形式展示已有模块，方便用户快速选择
- 允许用户补充不在列表中的模块

**如果没有模块列表：**
- 基于代码扫描结果让用户选择

### 第四步：拉取模块文档

对用户确认的每个涉及模块，执行插件命令拉取最新文档：

```bash
fuxian pull-module <模块名>
```

这会将远程最新的模块文档拉取到 `.fuxian/modules/<模块名>.md`。

**如果拉取失败或模块文档不存在：**
- 跳过该模块文档，在第五步中标注为"无已有文档"
- 后续提问中需要更多地覆盖该模块的业务背景

### 第五步：读取已有知识

读取以下信息，构建当前知识基线：

1. `.fuxian/modules/<模块名>.md` — 每个涉及模块的详细文档
2. `docs/Project_Basic.md` 中对应模块的条目（功能描述、代码目录）

将已有知识与任务描述对比，识别知识缺口。

### 第六步：差异分析

对每个涉及模块，评估：

- **已有知识：** 模块文档中已记录的内容
- **任务所需：** 完成此任务需要理解的业务逻辑
- **缺口：** 需要向用户询问的部分

只关注缺口，不要重复问已知信息。

### 第七步：定向提问

基于差异分析的结果，逐个向用户提问。

**提问原则：**
- 一次一个问题
- 多选题优先于开放式问题
- 只问缺口，不问已知信息
- 提问应聚焦于业务逻辑、预期行为、约束条件
- 不要问纯技术实现细节（那是 brainstorming 阶段的事）

**典型问题：**
- "这个模块的输入数据从哪里来？"
- "处理失败时的预期行为是什么？"
- "这个功能需要和哪些外部系统交互？"
- "性能上有无特殊要求？"

### 第八步：输出摘要

将收集到的业务背景整理为结构化摘要：

```markdown
# <任务名>

## 涉及模块
- <模块名>

## 业务背景
[从问答中收集的业务上下文]

## 预期行为
[任务完成后的预期效果]

## 约束条件
[性能、兼容性等约束]
```

### 第九步：用户确认

将摘要呈现给用户，询问：
- 信息是否准确？
- 是否有遗漏或需要补充？

等待用户确认后继续。

### 第十步：落盘存储

将确认后的摘要保存到 `.fuxian/tasks/<任务名>.md`。

任务名使用简洁的英文短横线命名（如 `add-vector-support`、`fix-regalloc-spill`）。

如果 `.fuxian/tasks/` 目录不存在，先创建。

### 第十一步：回传任务上下文

执行插件命令将任务上下文推送到远程，供团队成员参考：

```bash
fuxian push-task <任务名>
```

**如果推送失败：**
- 不阻塞流程，提示用户推送失败但本地已保存
- 继续执行

### 第十二步：更新模块文档

如果问答中收集到了模块的新知识（Project_Basic.md 或模块文档中没有的信息）：

1. 打开对应的 `.fuxian/modules/<模块名>.md`
2. 如果文件不存在，基于收集的信息创建
3. 如果文件存在，将新知识增量追加到对应章节
4. 保存

模块文档的标准格式：

```markdown
# <模块名>

## 功能
[模块的业务功能和职责]

## 代码目录
[关键文件和目录路径]

## 业务规则
[关键的业务逻辑和约束]

## 依赖关系
[上下游模块、数据流向]

## 备注
[其他重要信息]
```

更新完成后，进入 brainstorming 技能。
```

- [ ] **Step 2: 提交**

```bash
git add skills/task-context/
git commit -m "添加 task-context 技能：实现任务前的业务背景问答"
```

---

### Task 2: 修改 using-fuxian 技能优先级

**Files:**
- Modify: `skills/using-fuxian/SKILL.md:85-95`

- [ ] **Step 1: 修改技能优先级章节**

将 `skills/using-fuxian/SKILL.md` 中"技能优先级"章节替换为：

原内容（第 85-95 行）：
```
## 技能优先级

当多个技能可能适用时，按此顺序使用：

1. **流程技能优先**（brainstorming, debugging）— 这些决定如何处理任务
2. **实现技能其次**（test-driven-development 等）— 这些指导执行

"让我们构建 X" → 先 brainstorming，然后实现技能。
"修复这个 bug" → 先 debugging，然后领域特定技能。
```

替换为：
```
## 技能优先级

当多个技能可能适用时，按此顺序使用：

1. **流程技能优先**（task-context, brainstorming, debugging）— 这些决定如何处理任务
2. **实现技能其次**（test-driven-development 等）— 这些指导执行

"实现 X 功能" → 先 task-context，再 brainstorming，然后实现技能。
"修复这个 bug" → 先 debugging，然后领域特定技能。
"新增 Y 能力" → 先 task-context，再 brainstorming，然后实现技能。
```

- [ ] **Step 2: 在技能类型章节增加 task-context 说明**

在"技能类型"章节中，将：

原内容（第 97-101 行）：
```
## 技能类型

**严格型**（TDD, debugging）：严格遵循。不要适应性地偏离纪律。

**灵活型**（patterns）：根据上下文调整原则。
```

替换为：
```
## 技能类型

**严格型**（TDD, debugging）：严格遵循。不要适应性地偏离纪律。

**灵活型**（task-context, patterns）：根据上下文调整原则。对于非常简单的任务，task-context 可以快速确认后跳过，但不能完全跳过。
```

- [ ] **Step 3: 提交**

```bash
git add skills/using-fuxian/SKILL.md
git commit -m "更新 using-fuxian：增加 task-context 技能优先级"
```

---

### Task 3: 创建插件命令入口

**Files:**
- Create: `.fuxian/bin/fuxian`

- [ ] **Step 1: 创建 .fuxian/bin/fuxian**

```bash
#!/usr/bin/env bash
# Fuxian 插件命令入口
#
# 用法：
#   fuxian pull-module <模块名>  — 从远程拉取模块文档到 .fuxian/modules/
#   fuxian push-task <任务名>     — 将 .fuxian/tasks/<任务名>.md 推送到远程

set -euo pipefail

PLUGIN_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MODULES_DIR="${PLUGIN_ROOT}/modules"
TASKS_DIR="${PLUGIN_ROOT}/tasks"

mkdir -p "$MODULES_DIR" "$TASKS_DIR"

usage() {
    echo "用法: fuxian <command> [args]"
    echo ""
    echo "命令:"
    echo "  pull-module <模块名>  从远程拉取模块文档"
    echo "  push-task <任务名>     推送任务上下文到远程"
    exit 1
}

cmd_pull_module() {
    local module_name="$1"
    local target_file="${MODULES_DIR}/${module_name}.md"

    # TODO: 实现远程拉取逻辑（MCP/HTTP/Git 等）
    # 当前为占位实现，直接检查本地文件
    if [ -f "$target_file" ]; then
        echo "模块文档已存在: ${target_file}"
    else
        echo "提示: 远程拉取尚未配置，模块文档 ${module_name} 不存在"
        echo "将进入问答阶段补全该模块的业务背景。"
    fi
}

cmd_push_task() {
    local task_name="$1"
    local task_file="${TASKS_DIR}/${task_name}.md"

    if [ ! -f "$task_file" ]; then
        echo "错误: 任务文件不存在: ${task_file}"
        exit 1
    fi

    # TODO: 实现远程推送逻辑（MCP/HTTP/Git 等）
    echo "提示: 远程推送尚未配置，任务上下文已保存到本地: ${task_file}"
}

# 主入口
if [ $# -lt 1 ]; then
    usage
fi

COMMAND="$1"
shift

case "$COMMAND" in
    pull-module)
        if [ $# -lt 1 ]; then
            echo "错误: pull-module 需要模块名参数"
            exit 1
        fi
        cmd_pull_module "$1"
        ;;
    push-task)
        if [ $# -lt 1 ]; then
            echo "错误: push-task 需要任务名参数"
            exit 1
        fi
        cmd_push_task "$1"
        ;;
    *)
        echo "错误: 未知命令: ${COMMAND}"
        usage
        ;;
esac
```

- [ ] **Step 2: 提交**

```bash
git add .fuxian/bin/fuxian
git commit -m "添加 fuxian 插件命令入口（pull-module / push-task）"
```

---

## 自审

**规范覆盖检查：**
- task-context 技能主体 ✓ (Task 1)
- using-fuxian 技能优先级修改 ✓ (Task 2)
- 插件命令入口 ✓ (Task 3)
- 12 步流程全部在 SKILL.md 中定义 ✓
- Project_Basic.md 读取逻辑 ✓
- 模块文档拉取/回传 ✓
- 任务上下文落盘/回传 ✓
- 模块文档增量更新 ✓

**占位符扫描：** 无 TBD/TODO（Task 3 中有传输层 TODO 但这是明确的占位，标注了"当前为占位实现"）

**一致性检查：** 流程步骤编号、文件路径、命令名称跨 Task 一致。
