# Fuxian 插件设计文档

**日期**: 2026-06-01
**项目名**: fuxian
**平台**: Claude Code + opencode
**领域**: 自研芯片编译器开发
**语言**: 中文

## 目标

创建一个类似 superpowers 的 Claude Code / opencode 插件基础仓库，用于承载面向自研芯片编译器开发的自定义 AI 技能。

## 目录结构

```
fuxian/
├── .claude-plugin/
│   ├── plugin.json          # 插件元数据
│   └── marketplace.json     # 本地开发市场配置
├── .opencode/
│   └── plugins/
│       └── fuxian.js        # opencode 插件入口
├── hooks/
│   ├── hooks.json           # SessionStart 钩子定义
│   ├── session-start        # bash 钩子脚本
│   └── run-hook.cmd         # Windows 兼容执行器
├── skills/
│   ├── using-fuxian/        # 引导技能
│   │   ├── SKILL.md
│   │   └── references/
│   │       └── opencode-tools.md
│   ├── brainstorming/
│   │   └── SKILL.md
│   ├── test-driven-development/
│   │   └── SKILL.md
│   └── systematic-debugging/
│       └── SKILL.md
├── docs/
│   └── specs/
├── CLAUDE.md
├── README.md
├── .gitignore
├── LICENSE
└── package.json
```

## 插件注册与钩子机制

### plugin.json

```json
{
  "name": "fuxian",
  "description": "自定义 AI 编码技能库：面向自研芯片编译器开发的 TDD、调试和协作最佳实践",
  "version": "0.1.0",
  "author": {
    "name": "MrLau"
  },
  "license": "MIT",
  "keywords": ["skills", "compiler", "tdd", "debugging"]
}
```

### SessionStart 钩子

- 定义在 `hooks/hooks.json` 中
- 匹配 `startup|clear|compact` 事件
- 执行 `session-start` bash 脚本
- 脚本读取 `skills/using-fuxian/SKILL.md`，包装为 `<EXTREMELY_IMPORTANT>` 上下文注入
- 根据 `CLAUDE_PLUGIN_ROOT`（Claude Code）或 `OPENCODE_ROOT`（opencode）选择 JSON 输出格式
- Windows 兼容通过 `run-hook.cmd` 实现

### opencode 插件入口

`fuxian.js` 作为 opencode 插件加载点，读取 skills 目录并注册技能。

## 初始技能集

### using-fuxian（引导技能）

- 在 SessionStart 时自动加载
- 定义指令优先级：用户指令 > fuxian 技能 > 默认系统行为
- 说明技能发现机制（通过 Skill 工具加载）
- 包含防合理化清单（红灯信号表）
- 引用 opencode 工具映射参考文件

### brainstorming（头脑风暴）

- 在任何创意工作前自动触发
- 流程：探索上下文 → 提问 → 提出方案 → 呈现设计 → 获取批准
- 针对编译器领域做中文适配
- 硬门禁：未获得设计批准前不得编写任何代码

### test-driven-development（TDD）

- 在实现任何功能或 bugfix 前触发
- 红-绿-重构循环
- 针对编译器测试的特殊指导（IR 测试、指令选择测试、寄存器分配测试等）

### systematic-debugging（系统调试）

- 遇到 bug、测试失败、意外行为时触发
- 结构化调试流程：复现 → 假设 → 验证 → 修复
- 针对编译器调试的特殊指导（中间表示检查、代码生成验证等）

## 技能编写规范

- 所有技能用中文编写
- 保持结构化风格：清单、流程图、优先级规则
- 每个技能一个目录，包含 `SKILL.md`
- SKILL.md 格式遵循 Claude Code 技能规范

## 其他文件

- `CLAUDE.md`: 面向 AI 代理的贡献指南（中文）
- `README.md`: 项目介绍、安装说明、支持平台、技能列表
- `.gitignore`: `.worktrees/`、`.claude/`、`node_modules/`、`.DS_Store`
- `LICENSE`: MIT
