# ai_code2doc 设计文档

> 版本: 0.2.0
> 更新日期: 2026-05-14
> 状态: 新增 CMake 构建系统集成

---

## 1. 项目概述

### 1.1 定位

ai_code2doc 是一个 AI 驱动的代码文档生成工具，面向 Python / C / C++ 项目，自动扫描、解析、分析代码结构，并生成分层文档。核心价值在于：

- **多语言 AST 解析** — 基于 tree-sitter 的精确代码结构提取
- **CMake 构建系统集成** — 解析 CMakeLists.txt 提取 target/include/link 信息，改善 #include 解析和依赖分析
- **分层知识体系** — 项目概览 → 模块文档 → 依赖图三层递进
- **增量分析** — 基于文件哈希的变更检测，二次运行仅处理变化部分
- **LLM 增强** — 可选接入 GPT-4o 生成自然语言叙述
- **语义检索** — ChromaDB 向量存储 + OpenAI Embedding，支持自然语言查询

### 1.2 设计目标

| 目标 | 说明 |
|------|------|
| 正确性 | AST 级别的结构提取，不依赖正则表达式 |
| 可扩展 | 语言适配器模式，新增语言只需实现 3 个基类 |
| 高效 | 增量分析 + 解析缓存，二次运行秒级完成 |
| 离线可用 | LLM 为可选增强，无 API Key 时退化为纯静态生成 |
| 标准输出 | Markdown 格式输出，含 Mermaid 图表，兼容主流渲染器 |

### 1.3 技术栈

```
语言:      Python 3.11+
CLI:       Typer + Rich
AST:       tree-sitter (Python, C, C++ grammars)
数据模型:  Pydantic v2
依赖图:    NetworkX
LLM:       OpenAI GPT-4o (可选)
向量存储:  ChromaDB + text-embedding-3-small
Web:       FastAPI + Uvicorn
构建:      Poetry (pyproject.toml)
```

---

## 2. 系统架构

### 2.1 整体架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                         CLI (Typer)                             │
│  analyze │ serve │ query │ status                               │
└──────┬──────────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────────┐
│                      处理流水线 (Pipeline)                        │
│                                                                  │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐     │
│  │ Scanner  │──►│  Parser  │──►│ Analyzer │──►│Generator │     │
│  │ 文件扫描  │   │ AST 解析  │   │ 代码分析  │   │ 文档生成  │     │
│  └──────────┘   └──────────┘   └──────────┘   └──────────┘     │
│       │              │              │              │              │
│  ┌──────────┐   ┌──────────┐              ┌──────────┐          │
│  │ Change   │   │ Parse    │              │ Markdown │          │
│  │ Detector │   │ Cache    │              │ Writer   │          │
│  └──────────┘   └──────────┘              └──────────┘          │
│                                                                  │
│  ┌──────────────────────┐    ┌──────────────────────┐           │
│  │   LLM Client         │    │   Vector Store       │           │
│  │   (OpenAI GPT-4o)    │    │   (ChromaDB)         │           │
│  └──────────────────────┘    └──────────────────────┘           │
└──────────────────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────────┐
│                    Web API (FastAPI)                              │
│  /overview │ /modules │ /graph │ /search │ /ask                  │
└──────────────────────────────────────────────────────────────────┘
```

### 2.2 模块划分

```
ai_code2doc/
├── cli/                  # 命令行接口
│   ├── main.py           # Typer 应用，命令注册
│   ├── analyze_cmd.py    # analyze 命令实现
│   ├── serve_cmd.py      # serve 命令实现
│   ├── query_cmd.py      # query 命令实现
│   └── status_cmd.py     # status 命令实现
├── config/               # 配置管理
│   └── settings.py       # Pydantic Settings，环境变量绑定
├── models/               # 数据模型（Pydantic v2）
│   ├── module.py         # FunctionInfo, ClassInfo, InterfaceInfo, ImportInfo, FileInfo
│   ├── build.py          # CMakeTarget, CMakeProjectInfo
│   ├── knowledge.py      # KnowledgeDocument, ModuleSummary
│   ├── project.py        # TechStack, ProjectMetadata
│   ├── graph.py          # DependencyEdge, CallChain, ImpactHint, CycleInfo
│   └── analysis_state.py # AnalysisState, FileState
├── scanner/              # 文件扫描
│   ├── file_filter.py    # FileFilter（扩展名 + gitignore + 默认忽略规则）
│   ├── project_scanner.py # ProjectScanner（目录遍历）
│   └── change_detector.py # ChangeDetector（增量分析）
├── parser/               # 代码解析
│   ├── language_registry.py # LanguageRegistry（语言注册中心）
│   ├── base_extractor.py # BaseStructureExtractor（结构提取基类）
│   ├── base_parser.py    # BaseParser（解析基类）
│   ├── base_resolver.py  # BaseImportResolver（导入解析基类）
│   ├── tree_sitter_parser.py # TreeSitterParser（统一解析入口）
│   ├── build/            # 构建系统解析
│   │   └── cmake_parser.py # CMakeParser（CMakeLists.txt 解析）
│   └── languages/        # 语言实现
│       ├── python.py     # Python 适配器
│       └── c_cpp.py      # C/C++ 适配器（CMake 感知）
├── analyzer/             # 代码分析
│   ├── tech_stack.py     # TechStackDetector（技术栈检测）
│   ├── dependency_graph.py # DependencyGraphBuilder（依赖图构建）
│   └── metrics.py        # MetricsCalculator（度量计算）
├── generator/            # 文档生成
│   ├── base_generator.py # BaseGenerator（生成器基类）
│   ├── layer1_overview.py # Layer1 项目概览生成器
│   ├── layer2_modules.py # Layer2 模块文档生成器
│   ├── layer3_graph.py   # Layer3 依赖图生成器
│   ├── markdown_writer.py # MarkdownWriter（文件输出）
│   └── prompt_templates.py # Prompt 模板
├── llm/                  # LLM 集成
│   ├── client.py         # LLMClient（OpenAI 异步客户端）
│   ├── chunker.py        # Chunker（文本分块）
│   └── token_tracker.py  # TokenTracker（用量统计）
├── vector_store/         # 向量存储
│   ├── store.py          # VectorStore（ChromaDB 封装）
│   └── embedder.py       # Embedder（OpenAI Embedding）
├── utils/                # 工具模块
│   ├── hashing.py        # BLAKE2b 哈希
│   ├── path_utils.py     # 路径处理
│   ├── markdown_utils.py # Markdown 格式化
│   ├── parse_cache.py    # 解析缓存
│   └── logging.py        # 日志配置
└── web/                  # Web 接口
    ├── app.py            # FastAPI 应用
    └── routes/           # API 路由
        ├── overview.py   # 项目概览 API
        ├── modules.py    # 模块文档 API
        ├── graph.py      # 依赖图 API
        ├── search.py     # 语义搜索 API
        └── ask.py        # LLM 问答 API
```

---

## 3. 核心数据模型

### 3.1 代码结构模型 (`models/module.py`)

```
FileInfo
├── path: str                    # 文件相对路径
├── name: str                    # 文件名
├── language: str                # 语言标识 (python, c, cpp)
├── functions: list[FunctionInfo]
├── classes: list[ClassInfo]
├── interfaces: list[InterfaceInfo]
├── imports: list[ImportInfo]
├── exports: list[str]           # __all__ / 显式导出
└── raw_source: str              # 原始源码

FunctionInfo
├── name: str
├── params: list[str]            # 含类型注解
├── return_type: str | None
├── is_async: bool
├── is_exported: bool
├── decorators: list[str]
├── docstring: str | None
├── start_line: int
└── end_line: int

ClassInfo
├── name: str
├── extends: str | None
├── implements: list[str]
├── methods: list[FunctionInfo]
├── properties: list[str]
├── decorators: list[str]
├── docstring: str | None
├── start_line: int
└── end_line: int

ImportInfo
├── source: str                  # 导入源
├── specifiers: list[str]        # 具体导入项
├── is_type_only: bool           # 类型导入 (C: <header.h>, TS: type)
└── line: int
```

### 3.2 知识文档模型 (`models/knowledge.py`)

```
KnowledgeDocument
├── id: str                      # 唯一标识
├── layer: int                   # 层级 (1, 2, 3)
├── title: str
├── content: str                 # Markdown 正文
├── metadata: dict               # 附加元数据
├── source_files: list[str]      # 来源文件
└── created_at: datetime

ModuleSummary
├── module_path: str
├── summary: str
├── key_components: list[str]
├── responsibilities: list[str]
└── dependencies: list[str]
```

### 3.3 依赖图模型 (`models/graph.py`)

```
DependencyEdge
├── source: str
├── target: str
├── edge_type: str               # import, include
└── weight: int = 1

CycleInfo
├── nodes: list[str]
└── description: str             # "A → B → C → A"

ImpactHint
├── change_target: str
├── affected: list[str]
└── risk_level: str              # low, medium, high

CallChain
├── start: str
├── end: str
└── path: list[str]
```

### 3.4 分析状态模型 (`models/analysis_state.py`)

```
AnalysisState
├── project_root: str
├── file_states: dict[str, FileState]
└── last_analysis: datetime | None

FileState
├── path: str
├── content_hash: str            # BLAKE2b hex digest
├── last_modified: datetime
└── file_size: int
```

### 3.5 构建系统模型 (`models/build.py`)

从 CMakeLists.txt 中提取的构建元数据，用于增强 C/C++ 项目的分析精度。

```
CMakeTarget
├── name: str                    # 目标名，如 "my_app"
├── target_type: str             # "executable" | "static_library" | "shared_library"
│                                #   "module_library" | "object_library" | "interface_library"
├── sources: list[str]           # 源文件路径（相对于项目根目录）
├── include_dirs: list[str]      # include 目录（来自 target_include_directories）
├── link_libraries: list[str]    # 链接库（来自 target_link_libraries）
└── cmake_file: str              # 定义该 target 的 CMakeLists.txt 路径

CMakeProjectInfo
├── cmake_version: str           # cmake_minimum_required 版本号
├── project_name: str            # project() 名称
├── project_languages: list[str] # project() 声明的语言（C, CXX, CUDA ...）
├── subdirectories: list[str]    # add_subdirectory 路径
├── find_packages: list[str]     # find_package 名称（第三方依赖）
└── targets: dict[str, CMakeTarget]  # target_name → CMakeTarget
```

---

## 4. 处理流水线

### 4.1 五阶段流水线

```
Stage 1: SCAN          Stage 2: PARSE         Stage 3: ANALYZE
┌─────────────┐       ┌─────────────┐        ┌─────────────┐
│ProjectScanner│      │TreeSitter    │        │TechStack    │
│  FileFilter  │──────►│Parser       │───────►│Detector     │
│ChangeDetector│      │Language      │        │Dependency   │
│             │      │Registry     │        │GraphBuilder │
└──────┬──────┘       └─────────────┘        │MetricsCalc  │
       │               ┌─────────────┐        └──────┬──────┘
       │               │CMakeParser  │               │
       └──────────────►│(C/C++ 项目) │               │
                       └─────────────┘               │
Stage 4: GENERATE          Stage 5: PUBLISH           │
┌─────────────┐           ┌─────────────┐            │
│Layer1       │           │Markdown     │            │
│Generator    │           │Writer       │◄───────────┘
│Layer2       │──────────►│VectorStore  │
│Generator    │           │(ChromaDB)   │
│Layer3       │           └─────────────┘
│Generator    │
│LLM Client   │
└─────────────┘
```

### 4.2 Stage 1 — 文件扫描

**入口**: `ProjectScanner.scan(project_root)`

**流程**:
1. 初始化 `FileFilter`，加载默认忽略规则 + `.gitignore`
2. 遍历目录树，过滤文件（扩展名白名单 + 忽略规则 + 大小限制）
3. `ChangeDetector` 对比文件哈希与历史状态，标记 changed / unchanged / new
4. 输出: 受影响的文件列表 + 更新后的 `AnalysisState`

**FileFilter 忽略规则**:
```
始终忽略:
  __pycache__/  .git/  node_modules/  .venv/
  *.pyc  *.pyo  *.so  *.egg-info/
  .ai_code2doc/

扩展名白名单:
  .py  .pyw  .pyx  .pxd
  .c  .h  .cpp  .hpp  .cc  .cxx  .hh  .hxx

大小限制:
  默认 500KB，可配置
```

### 4.3 Stage 2 — AST 解析 + 构建系统解析

**入口**: `TreeSitterParser.parse_file(file_path)` + `CMakeParser().parse(project_root)`

**AST 解析流程**:
1. 根据文件扩展名从 `LanguageRegistry` 查找 `LanguageAdapter`
2. 用 tree-sitter 将源码解析为 CST（Concrete Syntax Tree）
3. 调用语言特定的 `StructureExtractor` 遍历 CST，提取:
   - 函数定义（含参数、返回类型、装饰器、异步标志）
   - 类定义（含继承、方法、属性）
   - 导入语句（含来源、具体项、是否类型导入）
   - 导出声明（`__all__` 等）
4. 调用语言特定的 `ImportResolver` 解析导入路径
5. 输出: `FileInfo` 对象

**CMake 构建系统解析**（仅 C/C++ 项目）:

当项目根目录存在 `CMakeLists.txt` 时，`CMakeParser` 遍历所有 CMakeLists.txt 文件，提取:

| CMake 命令 | 提取内容 | 用途 |
|-----------|---------|------|
| `cmake_minimum_required` | CMake 版本号 | 技术栈展示 |
| `project()` | 项目名称、语言 | 技术栈检测 |
| `add_subdirectory` | 子目录路径 | 模块结构发现 |
| `find_package` | 第三方包名 | 填充 `TechStack.dependencies` |
| `add_executable` | 可执行 target + 源文件 | 入口点检测 |
| `add_library` | 库 target + 源文件 | 依赖图构建 |
| `target_include_directories` | include 目录列表 | **改善 #include 解析精度** |
| `target_link_libraries` | 链接库名称 | **Layer 3 构建依赖图** |
| `target_sources` | 追加源文件列表 | target → 文件映射 |

**CMake 信息对 #include 解析的增强**:

`CCppImportResolver` 接收 `CMakeProjectInfo` 后，在 `resolve()` 中额外搜索:
1. 判断 `from_file` 属于哪个 CMake target（通过 `sources` 列表匹配）
2. 搜索该 target 声明的所有 `include_dirs`
3. 搜索该 target 链接的其他 target 的 `include_dirs`（传递性可见）
4. 无 CMake 信息时行为不变，完全向后兼容

**语言适配器模式**:

```python
@dataclass(frozen=True)
class LanguageAdapter:
    language_id: str             # "python", "c", "cpp"
    display_name: str            # "Python", "C", "C++"
    extensions: tuple[str, ...]  # (".py",) / (".c", ".h")
    tree_sitter_language: Language
    extractor: BaseStructureExtractor
    resolver: BaseImportResolver
    detect_tech_stack: Callable[[Path], TechStack]
    detect_entry_points: Callable[[Path], list[str]]
```

**解析缓存**: `ParseCache` 将 `FileInfo` 以 JSON 格式存储在 `.ai_code2doc/parse_cache/`，键为相对路径。未变更的文件直接读缓存，跳过 Stage 2。

### 4.4 Stage 3 — 代码分析

三个并行的分析器:

#### 4.4.1 TechStackDetector

检测项目技术栈，接收可选的 `CMakeProjectInfo` 以增强 C/C++ 项目的检测:
- **Python**: 解析 `pyproject.toml`（Poetry / setuptools）、`requirements.txt`、`setup.py`
- **C/C++**:
  - 基础检测: `CMakeLists.txt`、`Makefile`、`meson.build`、`WORKSPACE/BUILD`、`.sln`/`.vcxproj`
  - **CMake 增强**: `find_package` 结果 → `TechStack.dependencies`，`project()` 语言列表 → 语言检测
  - 框架检测: `Qt::`、`Boost::`、`.pro` 文件
- **输出**: `TechStack(language, frameworks, build_tool, package_manager, dependencies, entry_points)`

#### 4.4.2 DependencyGraphBuilder

基于 NetworkX 构建有向图:
- 节点 = 源文件
- 边 = import/include 关系
- 功能:
  - **环检测** — `detect_cycles()` 返回 `list[CycleInfo]`
  - **影响分析** — `analyze_impact(target)` 返回 `list[ImpactHint]`
  - **调用链查找** — `find_call_chains(start, end)` 返回 `list[CallChain]`
  - **拓扑排序** — `topological_sort()` 返回无环图的合法排序
  - **Mermaid 输出** — `to_mermaid()` 生成可渲染的依赖图代码

#### 4.4.3 MetricsCalculator

代码度量:
- 行数统计: code_lines, blank_lines, comment_lines, total_lines
- 结构统计: function_count, class_count, import_count
- 项目级聚合

### 4.5 Stage 4 — 文档生成

三层生成器继承自 `BaseGenerator`:

#### Layer 1 — 项目概览 (`Layer1OverviewGenerator`)

- **输入**: 项目结构、技术栈、度量、入口点、CMake 构建信息（如有）
- **输出**: 单个 `README.md`
- **内容**: 项目目的、架构类型、技术栈（含 CMake 版本）、目录结构、入口点、**构建目标表格**（CMake target 名称、类型、源文件）、关键设计模式
- **CMake 增强**: 新增 "Build Targets" 章节展示所有 CMake target；技术栈表格中增加 CMake Version 行
- **可选 LLM 增强**: 生成自然语言项目描述

#### Layer 2 — 模块文档 (`Layer2ModuleGenerator`)

- **输入**: 模块的 FileInfo、依赖关系、上下文模块摘要
- **输出**: 每个模块一个 `.md` 文件
- **内容**: 模块职责、公开 API、内部函数/类、依赖和被依赖
- **可选 LLM 增强**: 为每个模块生成职责描述

#### Layer 3 — 依赖图 (`Layer3GraphGenerator`)

- **输入**: 完整依赖图、度量、循环依赖、影响分析、CMake 构建信息（如有）
- **输出**: `dependency-graph.md` + `dependency-graph.mmd`
- **内容**: Mermaid 可视化、环检测报告、影响分析、耦合度量、**构建目标依赖图**（`target_link_libraries` 生成的 Mermaid 子图）、**target 详情表格**（target 名称、类型、链接库、源文件）、**find_package 第三方依赖列表**
- **纯静态生成**，不依赖 LLM

### 4.6 Stage 5 — 发布

- **MarkdownWriter**: 将 `KnowledgeDocument` 写入 `.ai_code2doc/layerN/` 目录
- **VectorStore**: 将文档切分后存入 ChromaDB，支持语义检索

---

## 5. 增量分析机制

### 5.1 设计原理

```
首次运行:
  Scan all files ──► Hash all ──► Parse all ──► Analyze all ──► Generate all

二次运行 (增量):
  Scan all files ──► Hash all ──► Compare hashes
                                    │
                           ┌────────┴────────┐
                           │ changed files    │ unchanged files
                           ▼                 ▼
                      Parse changed     Read ParseCache
                           │                 │
                           └────────┬────────┘
                                    ▼
                              Merge FileInfos ──► Analyze all ──► Generate affected layers
```

### 5.2 核心组件

**Hashing** (`utils/hashing.py`):
- 算法: BLAKE2b，digest_size=16
- 文件哈希: 分块读取（64KB），避免内存溢出
- 内容哈希: 直接对字符串计算

**AnalysisState** (`models/analysis_state.py`):
- 持久化: `.ai_code2doc/analysis_state.json`
- 每个文件记录: 路径、内容哈希、最后修改时间、文件大小

**ParseCache** (`utils/parse_cache.py`):
- 持久化: `.ai_code2doc/parse_cache/`，每个文件一个 JSON
- 键: 文件相对路径
- 未变更文件直接从缓存加载，跳过 tree-sitter 解析

**ChangeDetector** (`scanner/change_detector.py`):
- 输入: 当前扫描结果 + 历史 AnalysisState
- 输出: changed_files 列表 + 更新后的 AnalysisState
- 首次运行时，所有文件标记为 changed

---

## 6. 语言适配器详解

### 6.1 Python 适配器

**结构提取** (`parser/languages/python.py`):

| AST 节点类型 | 提取内容 |
|-------------|---------|
| `function_definition` | FunctionInfo(name, params, return_type, decorators, is_async) |
| `class_definition` | ClassInfo(name, extends, body 内的 methods/properties) |
| `import_statement` | ImportInfo(source="os") |
| `import_from_statement` | ImportInfo(source="os.path", specifiers=["join"]) |
| `expression_statement` 含 `assignment` 且左值为 `__all__` | exports = ["Foo", "bar"] |

**导入解析** (`PythonImportResolver`):
- 绝对导入: `from myapp.models import User` → 解析为 `src/myapp/models.py` 或 `src/myapp/models/__init__.py`
- 相对导入: `from .utils import helper` → 基于当前文件目录解析
- 第三方库: 返回 `None`（不尝试解析 site-packages）

### 6.2 C/C++ 适配器

**结构提取** (`parser/languages/c_cpp.py`):

| AST 节点类型 | 提取内容 |
|-------------|---------|
| `function_definition` | FunctionInfo(name, params, return_type) |
| `struct_specifier` | ClassInfo(name="StructName") |
| `class_specifier` | ClassInfo(name, extends) |
| `preproc_include` (引号) | ImportInfo(source="header.h", is_type_only=False) |
| `preproc_include` (尖括号) | ImportInfo(source="<stdio.h>", is_type_only=True) |
| `type_definition` | 存入 extract_extra_metadata |
| `enum_specifier` | 存入 extract_extra_metadata |

**导入解析** (`CCppImportResolver`):
- `#include "header.h"` — 搜索顺序: ① 当前文件目录 → ② `include/`/`src/` 默认目录 → ③ CMake `target_include_directories` 声明的目录 → ④ 传递链接 target 的 include 目录
- `#include <stdio.h>` — 系统头文件，返回 `None`
- 支持相对路径: `#include "sub/header.h"`
- **CMake 增强**: 接收 `CMakeProjectInfo`，利用 `target_include_directories` 和传递性链接关系改善跨目录 `#include` 解析

**技术栈检测** (`detect_ccpp_tech_stack`):
- 接收可选 `CMakeProjectInfo` 参数
- `find_package` 结果自动填入 `TechStack.dependencies`（如 `Boost`、`Qt6`、`Threads`）
- `project()` 语言列表替代基于文件扩展名的语言检测

**入口点检测** (`detect_ccpp_entry_points`):
- 接收可选 `CMakeProjectInfo` 参数
- 从 `add_executable` target 的 `sources` 列表精确匹配含 `main` 的源文件
- 无 CMake 信息时回退到正则搜索和 `add_executable` 目标名猜测

### 6.3 扩展新语言

添加新语言（如 Java）需要:

1. **实现 `BaseStructureExtractor`** — 定义如何从 CST 提取函数/类/导入
2. **实现 `BaseImportResolver`** — 定义如何解析 import 路径到文件路径
3. **注册 LanguageAdapter** — 在 `languages/__init__.py` 中注册
4. **添加 tree-sitter 语法** — 在 `pyproject.toml` 中添加对应 grammar 依赖

```python
# languages/java.py
class JavaExtractor(BaseStructureExtractor):
    def extract(self, tree, source, file_path) -> ExtractionResult: ...

class JavaImportResolver(BaseImportResolver):
    def resolve(self, import_info, file_path, project_root) -> str | None: ...

def register_java(registry: LanguageRegistry):
    adapter = LanguageAdapter(
        language_id="java",
        display_name="Java",
        extensions=(".java",),
        tree_sitter_language=Language(java_language()),
        extractor=JavaExtractor(),
        resolver=JavaImportResolver(),
        detect_tech_stack=detect_java_tech_stack,
        detect_entry_points=detect_java_entry_points,
    )
    registry.register(adapter)
```

---

## 7. LLM 集成

### 7.1 架构

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Prompt     │────►│  LLM Client  │────►│    OpenAI    │
│  Templates   │     │  (async)     │     │    API       │
└──────────────┘     │  + semaphore │     └──────────────┘
                     │  (concurrency│           │
                     │   control)  │           ▼
                     └──────────────┘     ┌──────────────┐
                           │              │   Response   │
                           ▼              └──────────────┘
                     ┌──────────────┐
                     │Token Tracker │
                     │(usage stats) │
                     └──────────────┘
```

### 7.2 LLMClient (`llm/client.py`)

- 基于 `openai` SDK 的异步客户端
- 信号量控制并发数（默认 3）
- 超时重试 + 错误回退
- 所有请求通过 `TokenTracker` 记录 prompt/completion token 用量

### 7.3 Chunker (`llm/chunker.py`)

- 将长文本按 token 估算切分为 ≤ `chunk_size_tokens` 的块
- 切分策略: 优先在空行/函数边界切分
- 用于: 模块源码过长时，分块送入 LLM 生成摘要

### 7.4 Prompt 模板 (`generator/prompt_templates.py`)

三层模板:
- `format_layer1_prompt` — 项目概览生成
- `format_layer2_prompt` — 模块文档生成
- `format_layer3_prompt` — 依赖图分析

每个模板将结构化数据（代码结构、度量、依赖）填充到提示词中。

### 7.5 降级策略

LLM 不可用时（无 API Key / 网络错误 / 限额耗尽）:
- Layer 1/2 退化为纯结构化 Markdown（无自然语言叙述）
- Layer 3 本身不依赖 LLM
- 整个分析流程不会因 LLM 故障而中断

---

## 8. 向量存储与语义检索

### 8.1 架构

```
KnowledgeDocument ──► Embedder (text-embedding-3-small) ──► ChromaDB
                                                                  │
Query (自然语言) ──► Embedder ──► ChromaDB.similarity_search ──► Top-K 结果
```

### 8.2 VectorStore (`vector_store/store.py`)

- 底层: ChromaDB 持久化存储（`.ai_code2doc/chroma/`）
- 文档切分后按段落存入
- 支持 `similarity_search(query, top_k)` 语义搜索
- 元数据过滤: 按 layer、source_file 筛选

### 8.3 Embedder (`vector_store/embedder.py`)

- 模型: OpenAI `text-embedding-3-small`
- 批量嵌入支持
- 向量维度: 1536

---

## 9. Web 接口

### 9.1 API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/overview` | 获取项目概览文档 |
| GET | `/api/v1/modules` | 列出所有模块文档 |
| GET | `/api/v1/modules/{name}` | 获取指定模块文档 |
| GET | `/api/v1/graph` | 获取依赖图数据 |
| GET | `/api/v1/graph/mermaid` | 获取 Mermaid 图代码 |
| POST | `/api/v1/search` | 语义搜索文档 |
| POST | `/api/v1/ask` | LLM 问答（基于文档上下文） |

### 9.2 启动

```bash
ai_code2doc serve --host 0.0.0.0 --port 8420
```

---

## 10. 配置系统

### 10.1 配置来源优先级

```
环境变量 (AI_CODE2DOC_*)  >  .env 文件  >  默认值
```

### 10.2 配置项

| 配置项 | 环境变量 | 默认值 | 说明 |
|--------|---------|--------|------|
| `llm_base_url` | `AI_CODE2DOC_LLM_BASE_URL` | `https://api.openai.com/v1` | LLM API 地址 |
| `llm_api_key` | `AI_CODE2DOC_LLM_API_KEY` | `""` | API Key |
| `llm_model` | `AI_CODE2DOC_LLM_MODEL` | `gpt-4o` | 模型名称 |
| `llm_max_tokens` | `AI_CODE2DOC_LLM_MAX_TOKENS` | `4096` | 最大生成 token |
| `llm_temperature` | `AI_CODE2DOC_LLM_TEMPERATURE` | `0.1` | 温度参数 |
| `llm_concurrency` | `AI_CODE2DOC_LLM_CONCURRENCY` | `3` | 并发请求数 |
| `max_file_size_kb` | `AI_CODE2DOC_MAX_FILE_SIZE_KB` | `500` | 文件大小限制 |
| `chunk_size_tokens` | `AI_CODE2DOC_CHUNK_SIZE_TOKENS` | `3000` | 分块大小 |
| `output_dir` | `AI_CODE2DOC_OUTPUT_DIR` | `.ai_code2doc` | 输出目录 |
| `chroma_persist_dir` | `AI_CODE2DOC_CHROMA_PERSIST_DIR` | `.ai_code2doc/chroma` | 向量库路径 |
| `embedding_model` | `AI_CODE2DOC_EMBEDDING_MODEL` | `text-embedding-3-small` | 嵌入模型 |
| `web_host` | `AI_CODE2DOC_WEB_HOST` | `0.0.0.0` | Web 监听地址 |
| `web_port` | `AI_CODE2DOC_WEB_PORT` | `8420` | Web 监听端口 |

---

## 11. 输出结构

```
.ai_code2doc/
├── analysis_state.json          # 增量分析状态
├── parse_cache/                 # 解析缓存
│   ├── src_main_py.json
│   └── ...
├── layer1/
│   └── README.md               # 项目概览
├── layer2/
│   ├── cli_main.md             # CLI 模块文档
│   ├── config_settings.md      # 配置模块文档
│   ├── models_module.md        # 模型模块文档
│   └── ...
├── layer3/
│   ├── dependency-graph.md     # 依赖图分析（含表格、影响分析）
│   └── dependency-graph.mmd    # Mermaid 图定义
└── chroma/                     # 向量数据库（serve 模式）
```

---

## 12. CLI 命令参考

| 命令 | 说明 | 关键参数 |
|------|------|---------|
| `ai_code2doc analyze <path>` | 扫描并生成文档 | `--no-llm`（禁用 LLM）、`--output-dir` |
| `ai_code2doc serve` | 启动 Web 服务 | `--host`、`--port` |
| `ai_code2doc query <question>` | 语义查询文档 | — |
| `ai_code2doc status` | 查看分析状态 | — |

---

## 13. 关键设计决策

### 13.1 为什么选择 tree-sitter 而非正则表达式

- **正确性**: 正则无法处理嵌套结构（如嵌套括号、字符串中的关键字）
- **多语言**: tree-sitter 有 50+ 语言的 grammar，扩展成本低
- **增量解析**: tree-sitter 原生支持增量解析（未来可利用）

### 13.2 为什么 BLAKE2b 而非 MD5/SHA256

- **性能**: BLAKE2b 比 MD5 快，比 SHA256 快得多
- **安全**: BLAKE2b 是密码学安全的（MD5 不是）
- **可配置摘要长度**: 16 字节已足够用于变更检测

### 13.3 为什么三层文档而不是一层

- **Layer 1** 面向项目新成员，提供宏观理解
- **Layer 2** 面向模块开发者，提供实现细节
- **Layer 3** 面向架构师，提供全局依赖视角
- 不同角色关注不同抽象层次

### 13.4 为什么 LLM 是可选的

- **离线场景**: 企业内网可能无法访问 OpenAI
- **成本控制**: GPT-4o 调用有成本，小项目可能不需要
- **确定性**: 纯静态生成结果可复现，LLM 输出有随机性

### 13.5 为什么 NetworkX 而非自实现图

- **功能完备**: 拓扑排序、环检测、最短路径开箱即用
- **性能**: 纯 Python 实现，对于代码项目规模（百~千节点）足够
- **可视化**: 可导出 Mermaid / Graphviz 格式

### 13.6 为什么用轻量正则解析 CMake 而非完整 CMake 解析器

- **无重依赖**: 完整的 CMake 解析器（如 `cmake-language-server`）体积大且依赖复杂
- **够用**: 只需提取 9 个命令的关键参数，正则 + 括号平衡即可
- **容错**: 对缺失参数、嵌套 generator 表达式、条件语句等场景不崩溃，只提取能提取的部分
- **不过度设计**: CMakeLists.txt 的复杂度没有上限（if/else/foreach/function），完整解析不现实

---

## 14. 性能考量

### 14.1 瓶颈分析

| 阶段 | 瓶颈 | 优化措施 |
|------|------|---------|
| 文件扫描 | 磁盘 I/O | 仅扫描白名单扩展名 |
| AST 解析 | tree-sitter 解析 | ParseCache 缓存 + 增量分析 |
| 依赖图构建 | 图算法 | NetworkX 内部优化 |
| LLM 生成 | API 延迟 | 并发控制 + 异步 + 可选禁用 |
| 向量嵌入 | API 延迟 | 批量嵌入 |

### 14.2 大型项目建议

- 使用增量分析（默认开启）避免重复解析
- 调低 `llm_concurrency` 避免触发 API 限流
- 增大 `max_file_size_kb` 处理大型模板文件

---

## 15. 安全考量

| 风险 | 缓解措施 |
|------|---------|
| API Key 泄露 | 通过环境变量 / .env 传入，不硬编码 |
| 路径遍历 | 所有路径操作基于项目根目录的相对路径 |
| 依赖图 DoS | 无外部输入攻击面（本地工具） |
| 源码泄露 | 仅发送到用户配置的 LLM API，默认 OpenAI |

---

## 16. 测试策略

### 16.1 测试分层

```
单元测试 (tests/unit/)
├── 纯函数测试: hashing, path_utils, markdown_utils
├── 模型测试: models, token_tracker
├── 组件测试: scanner, parse_cache, language_registry, metrics
├── 生成器测试: prompt_templates, markdown_writer, chunker
├── CMake 解析: cmake_parser（29 用例）
└── CMake 解析器集成: c_cpp_resolver_cmake（5 用例）

集成测试 (tests/integration/)
├── Python 解析: 函数/类/导入提取 + 完整项目解析
├── C 解析: 函数/结构体/include 提取 + 完整项目解析
├── 依赖图: 图构建 + 环检测 + 影响分析 + 拓扑排序
├── 技术栈: pyproject.toml / CMake / Makefile 检测
├── 变更检测: 增量分析 + 状态持久化
└── CMake 集成: 构建信息解析 → 技术栈 → 依赖图 → 入口点（5 用例）
```

**总计**: 216 项测试

### 16.2 Fixture 项目

- `sample-py-project/` — FastAPI 风格 Python 项目
- `sample-c-project/` — CMake 风格 C 项目

---

## 附录 A: 依赖关系图

项目自身依赖关系（基于 .ai_code2doc 分析结果）:

```
最被依赖的模块:
  models/module.py      (被 9 个模块导入)
  config/settings.py    (被 8 个模块导入)
  models/knowledge.py   (被 7 个模块导入)

最复杂的模块:
  generator/layer2_modules.py  (导入 10 个模块)
  generator/layer3_graph.py    (导入 10 个模块)
  generator/layer1_overview.py (导入 9 个模块)

循环依赖: 无

CMake 构建系统集成:
  parser/build/cmake_parser.py  → 被 generator/layer1、generator/layer3、
                                   analyzer/tech_stack 引用
  models/build.py               → 被 parser/build、parser/languages/c_cpp、
                                   generator/layer1、generator/layer3 引用
```

## 附录 B: 外部依赖清单

| 包 | 用途 | 必选 |
|----|------|------|
| `typer` | CLI 框架 | 是 |
| `rich` | 终端美化 | 是 |
| `pydantic` | 数据模型 | 是 |
| `pydantic-settings` | 配置管理 | 是 |
| `tree-sitter` | AST 解析 | 是 |
| `tree-sitter-python` | Python 语法 | 是 |
| `tree-sitter-c` | C 语法 | 是 |
| `tree-sitter-cpp` | C++ 语法 | 是 |
| `networkx` | 依赖图 | 是 |
| `openai` | LLM 客户端 | 否 |
| `chromadb` | 向量存储 | 否 |
| `fastapi` | Web API | 否 |
| `uvicorn` | ASGI 服务器 | 否 |
| `httpx` | HTTP 客户端 | 否 |
| `structlog` | 结构化日志 | 是 |
