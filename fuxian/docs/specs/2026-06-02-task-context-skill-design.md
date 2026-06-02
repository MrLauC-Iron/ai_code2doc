# Task-Context 技能设计文档

**日期**: 2026-06-02
**项目名**: fuxian
**技能名**: task-context

## 目标

解决 AI 在存量项目中缺乏业务全貌的问题。在用户下发实现任务后，通过结构化问答补全业务背景，并将积累的知识沉淀为项目文档。

## 定位

- brainstorming 的前置步骤
- 所有实现任务触发
- 灵活型技能（内容少的任务可以快速跳过）

## 流程

```
收到实现任务 → 触发 task-context
         ↓
   1. 读取 docs/Project_Basic.md
         ↓
   2a. 存在 → 提取项目背景和核心模块信息
   2b. 不存在 → 代码扫描 + 提示用户创建 docs/Project_Basic.md
         ↓
   3. 定向提问：此次任务涉及哪些模块（提示 Project_Basic.md 中的模块列表）
         ↓
   4. 通过插件命令拉取涉及模块的最新文档到 .fuxian/modules/
         ↓
   5. 读取拉取后的模块文档 + Project_Basic.md 中对应模块信息
         ↓
   6. 差异分析：已有知识 vs 任务所需知识
         ↓
   7. 定向提问：只问未知/变化的业务背景
         ↓
   8. 输出摘要：结构化任务理解摘要
         ↓
   9. 用户确认：确认或补充
         ↓
   10. 落盘存储：保存到 .fuxian/tasks/<任务名>.md
         ↓
   11. 通过插件命令回传 tasks/<任务名>.md
         ↓
   12. 模块更新：将新知识增量更新到对应模块文档
         ↓
   进入 brainstorming
```

## 文件结构

### 项目侧（用户维护）

```
项目根目录/
├── docs/
│   └── Project_Basic.md           # 项目基础信息（项目自身维护）
```

### 插件侧（fuxian 生成+维护）

```
.fuxian/
├── modules/
│   ├── lexer.md                   # 各模块业务文档
│   ├── parser.md
│   └── ...
├── tasks/
│   ├── add-vector-support.md      # 各任务上下文记录
│   └── ...
└── bin/
    └── fuxian                      # 插件命令入口
```

## 数据模型

### docs/Project_Basic.md（项目侧，用户维护）

```markdown
# 项目基础信息

## 项目背景
[项目目的、目标芯片架构、编译器定位等]

## 核心模块

| 模块名 | 功能描述 | 代码目录 | 状态 |
|--------|----------|----------|------|
| lexer  | 词法分析  | src/lexer/ | 已有文档 |
| parser | 语法分析  | src/parser/ | 待补充 |
```

### .fuxian/modules/<模块名>.md（插件侧，fuxian 维护）

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

### .fuxian/tasks/<任务名>.md（插件侧，fuxian 生成）

```markdown
# <任务名>

## 涉及模块
- lexer
- ir

## 业务背景
[用户确认的业务上下文]

## 预期行为
[任务完成后的预期效果]

## 约束条件
[性能、兼容性等约束]
```

## 插件命令

传输层对 skill 透明，通过插件命令封装：

- `fuxian pull-module <模块名>` — 从远程拉取模块文档到本地 .fuxian/modules/
- `fuxian push-task <任务名>` — 将 .fuxian/tasks/<任务名>.md 回传到远程

skill 中通过 Bash 调用这些命令，不直接依赖 MCP 或其他传输协议。

## using-fuxian 修改

在技能优先级中增加 task-context：

```
当多个技能可能适用时，按此顺序使用：

1. **流程技能优先**（task-context, brainstorming, debugging）
2. **实现技能其次**（test-driven-development 等）

"实现 X 功能" → 先 task-context，再 brainstorming，然后实现技能。
"修复这个 bug" → 先 debugging，然后领域特定技能。
"新增 Y 能力" → 先 task-context，再 brainstorming，然后实现技能。
```

task-context 为灵活型技能：内容少的任务可以快速跳过。

## 变更范围

- 新增：`skills/task-context/SKILL.md`
- 修改：`skills/using-fuxian/SKILL.md`（技能优先级）
- 新增：`.fuxian/bin/fuxian`（插件命令入口，传输层实现待定）
