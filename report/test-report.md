# ai_code2doc 测试报告

**执行环境**: Python 3.14.5 / Windows 11 / pytest 9.0.3
**执行时间**: 2026-05-12
**总用例数**: 177
**通过**: 177 (100%)
**失败**: 0
**耗时**: 1.31s

---

## 一、数据模型层（28 用例）

**功能描述**：数据模型层是整个项目的核心数据结构定义，使用 Pydantic BaseModel 定义了代码解析过程中产生的所有结构化数据。包括函数签名（FunctionInfo）、类定义（ClassInfo）、接口定义（InterfaceInfo）、导入声明（ImportInfo）、文件级信息（FileInfo）、模块摘要（ModuleSummary）等基础模型，以及依赖图模型（DependencyEdge / CallChain / ImpactHint / CycleInfo）、知识文档（KnowledgeDocument）、技术栈（TechStack）和增量分析状态（AnalysisState / FileState）。这些模型贯穿于解析、分析、生成三个核心阶段，是各模块间数据传递的契约。

> 覆盖模块：`models/module.py`, `models/graph.py`, `models/knowledge.py`, `models/analysis_state.py`, `models/project.py`

| 子模块 | 用例数 | 状态 | 说明 |
|--------|--------|------|------|
| FunctionInfo | 5 | ALL PASS | 基本创建、异步、装饰器、返回类型、导出标记 |
| ClassInfo | 4 | ALL PASS | 基本创建、方法、实现接口、装饰器 |
| InterfaceInfo | 2 | ALL PASS | 基本创建、继承 |
| ImportInfo | 3 | ALL PASS | 普通 import、type_only、空 specifiers |
| FileInfo | 3 | ALL PASS | 基本创建、完整字段、JSON 序列化往返 |
| ModuleSummary | 1 | ALL PASS | 基本创建及默认值 |
| Graph 模型 (Edge/Chain/Impact/Cycle) | 4 | ALL PASS | 依赖边、调用链、影响分析、环信息 |
| KnowledgeDocument | 2 | ALL PASS | 基本创建、标签与元数据 |
| TechStack | 2 | ALL PASS | 带参数创建、默认值 |
| AnalysisState / FileState | 3 | ALL PASS | 基本创建、文件状态、JSON 往返 |

**测试文件**: `tests/unit/test_models.py`

---

## 二、Python 代码解析（12 用例）

**功能描述**：Python 代码解析器基于 tree-sitter-python 实现对 Python 源代码的结构化信息提取。它能识别同步/异步函数定义（含参数、返回类型、装饰器）、类定义（含继承关系、方法、属性）、三种 import 语句（`import`、`from...import`、相对导入）、`__all__` 导出列表，以及将 Python 风格的点分模块名解析为项目内的实际文件路径。该模块是 Python 项目治理的核心能力，直接影响 Layer 2 模块摘要和 Layer 3 依赖图的质量。

> 覆盖模块：`parser/languages/python.py`, `parser/tree_sitter_parser.py`

| 子功能 | 用例数 | 状态 | 说明 |
|--------|--------|------|------|
| 函数提取 | 3 | ALL PASS | 普通 `def`（含类型注解/返回值）、`async def`、`@decorator` |
| 类提取 | 2 | ALL PASS | 带继承的类、类内方法提取 |
| Import 提取 | 3 | ALL PASS | `import os`、`from os.path import join`、`from .utils import helper` |
| `__all__` 导出提取 | 1 | ALL PASS | `__all__ = ["Foo", "bar"]` |
| 完整项目解析 | 1 | ALL PASS | 对 sample-py-project 全文件解析，验证函数/类非空 |
| Import 路径解析 | 1 | ALL PASS | `src.models.user` 解析到正确文件路径 |
| 第三方库不解析 | 1 | ALL PASS | `import numpy` 返回 None |

**测试文件**: `tests/integration/test_python_parser.py`

---

## 三、C/C++ 代码解析（12 用例）

**功能描述**：C/C++ 代码解析器基于 tree-sitter-c/tree-sitter-cpp 实现，提取 C 和 C++ 源文件中的函数定义（含参数和返回类型）、结构体与类定义（含继承关系、成员方法）、`#include` 指令（区分引号引用和尖括号系统头文件），以及 typedef、enum、宏定义等额外元数据。解析器还能将 `#include "header.h"` 解析为项目内的实际头文件路径（支持 src/、include/ 目录搜索），但不会将 `<stdio.h>` 等系统头文件映射到本地路径。

> 覆盖模块：`parser/languages/c_cpp.py`, `parser/tree_sitter_parser.py`

| 子功能 | 用例数 | 状态 | 说明 |
|--------|--------|------|------|
| 函数提取 | 2 | ALL PASS | `int main(void)`、`int add(int a, int b)` 含参数 |
| 结构体/类提取 | 2 | ALL PASS | `struct Point`、C++ `class Foo : public Bar` |
| `#include` 提取 | 2 | ALL PASS | 引号 `"header.h"` (is_type_only=False)、尖括号 `<stdio.h>` (is_type_only=True) |
| 额外元数据 | 2 | ALL PASS | `typedef`、`enum` 不崩溃 |
| 完整项目解析 | 1 | ALL PASS | 对 sample-c-project 全文件解析，验证 main 函数被找到 |
| Include 路径解析 | 2 | ALL PASS | `"utils.h"` 从 src/main.c 解析到 include/utils.h |
| 系统头文件不解析 | 1 | ALL PASS | `<stdio.h>` 返回 None |

**测试文件**: `tests/integration/test_c_parser.py`

---

## 四、语言注册中心（10 用例）

**功能描述**：语言注册中心（LanguageRegistry）是多语言解析架构的核心调度枢纽。它采用注册表模式，每种语言通过 LanguageAdapter 将提取器（Extractor）、导入解析器（Resolver）、技术栈检测器和入口点检测器打包注册。TreeSitterParser 在解析文件时根据扩展名自动从注册中心查找对应适配器，无需硬编码语言逻辑。系统启动时 Python 和 C/C++ 两个适配器会自动注册，未来新增语言只需实现 BaseStructureExtractor 和 BaseImportResolver 接口并调用 register 即可。

> 覆盖模块：`parser/language_registry.py`

| 子功能 | 用例数 | 状态 | 说明 |
|--------|--------|------|------|
| 内置语言自动注册 | 1 | ALL PASS | python + c_cpp 两个 adapter 存在 |
| 按扩展名查找 | 4 | ALL PASS | `.py`->python, `.c`->c_cpp, `.cpp`->c_cpp, `.zzz`->None |
| 按 ID 查找 | 2 | ALL PASS | `"python"`->adapter, `"fortran"`->None |
| 全量查询 | 2 | ALL PASS | `all_extensions()` 包含 .py/.c/.cpp/.h, `all_adapters()` >=2 |
| 大小写不敏感 | 1 | ALL PASS | `.PY` 能匹配 python |

**测试文件**: `tests/unit/test_language_registry.py`

---

## 五、文件扫描与过滤（14 用例）

**功能描述**：文件扫描模块负责递归遍历项目目录树，筛选出需要分析的目标源文件。FileFilter 组件根据预定义的忽略模式（版本控制目录、构建产物、缓存、IDE 配置等）和项目 `.gitignore` 文件排除无关文件，并通过 LanguageRegistry 动态判断哪些扩展名属于可解析的源代码文件。ProjectScanner 在 FileFilter 基础上进一步过滤掉超大文件（默认 500KB 阈值），输出包含目标文件列表、所有文件列表、目录列表和忽略计数的 ScanResult。

> 覆盖模块：`scanner/file_filter.py`, `scanner/project_scanner.py`

| 子功能 | 用例数 | 状态 | 说明 |
|--------|--------|------|------|
| 忽略规则 | 4 | ALL PASS | `__pycache__`、`.git`、`node_modules`、`.gitignore` 自定义模式 |
| 目标文件判定 | 5 | ALL PASS | 接受 `.py/.c/.cpp`、拒绝 `.pyc/.txt` |
| 项目扫描 | 4 | ALL PASS | Python 项目扫描、C 项目扫描、目录发现、root 路径正确 |
| 文件大小限制 | 1 | ALL PASS | 超过 500KB 的文件被跳过 |

**测试文件**: `tests/unit/test_scanner.py`

---

## 六、增量变更检测（5 用例）

**功能描述**：增量变更检测模块是存量项目高效治理的关键能力。ChangeDetector 通过 BLAKE2b 哈希比对文件内容变化，将项目文件分为"已变更"和"未变更"两类。分析状态以 JSON 文件持久化存储（记录每个文件的哈希值和最后分析时间），支持跨会话持久化。当用户再次运行 `analyze --incremental` 时，只需重新解析变更文件，未变更文件直接从缓存加载，大幅减少重复解析的开销。首次运行时无历史状态，所有文件均视为变更文件。

> 覆盖模块：`scanner/change_detector.py`, `utils/hashing.py`

| 子功能 | 用例数 | 状态 | 说明 |
|--------|--------|------|------|
| 首次检测 | 1 | ALL PASS | 无历史状态时全部视为 changed |
| 无变更检测 | 1 | ALL PASS | 更新后再次检测，全部 unchanged |
| 部分变更 | 1 | ALL PASS | 仅修改 1 个文件，其余 unchanged |
| 新增文件 | 1 | ALL PASS | 新文件不在状态中，视为 changed |
| 状态持久化 | 1 | ALL PASS | save->load 往返一致（跨实例） |

**测试文件**: `tests/integration/test_change_detector.py`

---

## 七、哈希工具（11 用例）

**功能描述**：哈希工具模块提供基于 BLAKE2b 的文件和内容哈希计算能力，是增量变更检测的基础设施。`compute_file_hash` 以 64KiB 分块读取文件，避免大文件一次性加载到内存；`compute_content_hash` 对字符串内容计算哈希。两者均输出 32 字符的十六进制摘要（digest_size=16 字节），用于唯一标识文件内容的版本。

> 覆盖模块：`utils/hashing.py`

| 子功能 | 用例数 | 状态 | 说明 |
|--------|--------|------|------|
| 确定性 | 2 | ALL PASS | 同一内容/文件两次哈希结果相同 |
| 不同内容不同哈希 | 2 | ALL PASS | 不同字符串/文件产生不同哈希 |
| 哈希长度 | 2 | ALL PASS | 固定 32 hex 字符 (BLAKE2b, digest_size=16) |
| 边界情况 | 3 | ALL PASS | 空内容、空文件、Unicode 内容 |
| 大文件分块 | 1 | ALL PASS | >64KiB 文件正确分块计算 |
| 异常处理 | 1 | ALL PASS | 文件不存在抛出 OSError |

**测试文件**: `tests/unit/test_hashing.py`

---

## 八、依赖图分析（13 用例）

**功能描述**：依赖图分析模块基于 NetworkX 构建有向依赖图（Directed Graph），是 Layer 3 知识文档生成的核心。它将每个源文件作为节点，import/include 关系作为有向边，支持四种分析能力：(1) 环检测——发现循环依赖并输出环路径描述；(2) 影响分析——通过反向 BFS 计算某文件变更会影响哪些下游模块，并按影响范围划分 low/medium/high 三级风险；(3) 调用链查找——寻找两个模块之间的所有依赖路径；(4) 拓扑排序——返回按依赖关系排序的文件列表。此外还支持生成 Mermaid 格式的可视化图描述。

> 覆盖模块：`analyzer/dependency_graph.py`

| 子功能 | 用例数 | 状态 | 说明 |
|--------|--------|------|------|
| 图构建 | 2 | ALL PASS | 单文件无依赖、两文件依赖关系 |
| 环检测 | 1 | ALL PASS | A->B->A 检测到环 |
| 影响分析 | 2 | ALL PASS | <=2 依赖 low risk, >=6 依赖 high risk |
| 调用链查找 | 1 | ALL PASS | A->B->C 找到完整路径 |
| 拓扑排序 | 1 | ALL PASS | 无环图返回有效排序 |
| Mermaid 输出 | 1 | ALL PASS | 包含 `graph TD` 和 `-->` |
| 模块依赖查询 | 2 | ALL PASS | 已知节点返回 deps/dependents、未知节点返回空 |
| 真实项目图 | 2 | ALL PASS | Python/C fixture 项目构建成功 |
| 混合语言图 | 1 | ALL PASS | Python + C 节点共存 |

**测试文件**: `tests/integration/test_dependency_graph.py`

---

## 九、技术栈检测（7 用例）

**功能描述**：技术栈检测模块通过分析项目配置文件自动识别项目使用的技术栈。它将检测委托给各语言的适配器：Python 适配器解析 `pyproject.toml`（识别 FastAPI/Django/Flask 框架和 poetry/hatch 构建工具）、`requirements.txt`（提取依赖列表）和 `setup.py`；C/C++ 适配器检测 `CMakeLists.txt`、`Makefile`、`meson.build` 等构建系统，以及 Qt/Boost/CUDA 等库。检测结果汇总为 TechStack 模型，包含框架、构建工具、语言、依赖列表、包管理器等字段，供 Layer 1 项目概览使用。

> 覆盖模块：`analyzer/tech_stack.py`

| 子功能 | 用例数 | 状态 | 说明 |
|--------|--------|------|------|
| Python pyproject.toml | 1 | ALL PASS | 检测 FastAPI 框架、Python 语言 |
| Python requirements.txt | 1 | ALL PASS | 检测 Django 依赖 |
| C CMake 项目 | 1 | ALL PASS | 检测 C 语言、CMake 构建工具 |
| C Makefile 项目 | 1 | ALL PASS | 检测 C 语言 |
| 入口点检测 | 2 | ALL PASS | Python 入口点、C main.c 入口点 |
| 空项目 | 1 | ALL PASS | 无源文件时返回 Unknown |

**测试文件**: `tests/integration/test_tech_stack.py`

---

## 十、度量计算（9 用例）

**功能描述**：度量计算模块为源文件和项目生成量化统计指标。对于单个文件，它逐行分析内容，区分代码行、注释行（支持 `//` 单行注释和 `/* */` 块注释）和空行，计算行数和文件大小。对于已解析的 FileInfo 对象，它直接从结构化数据中提取函数数量、类数量、导入数量等指标。多个文件的 FileMetrics 可聚合为 ProjectMetrics，提供项目级别的总行数、总函数数等汇总数据。这些度量用于分析报告和 Layer 1 概览文档。

> 覆盖模块：`analyzer/metrics.py`

| 子功能 | 用例数 | 状态 | 说明 |
|--------|--------|------|------|
| 行计数 | 4 | ALL PASS | 纯代码、空行、C 风格注释、行数统计 |
| 项目级聚合 | 1 | ALL PASS | 多文件 FileMetrics 汇总为 ProjectMetrics |
| FileInfo 转换 | 1 | ALL PASS | 从 FileInfo 提取 function_count/class_count 等 |
| 边界情况 | 2 | ALL PASS | 空文件、size_bytes 正确性 |

**测试文件**: `tests/unit/test_metrics.py`

---

## 十一、解析缓存（6 用例）

**功能描述**：解析缓存模块（ParseCache）是增量治理体系的关键组件，用于避免对未变更文件的重复 tree-sitter 解析。它将每个文件的解析结果（FileInfo）序列化为 JSON 文件存储在 `.ai_code2doc/cache/file_infos/` 目录下，以文件相对路径作为缓存键。在增量模式下，`resolve_file_infos` 方法对未变更文件直接从缓存加载，仅对变更文件调用 TreeSitterParser 重新解析并更新缓存。缓存条目采用容错设计——加载失败时返回 None 而非抛异常，触发重新解析。

> 覆盖模块：`utils/parse_cache.py`

| 子功能 | 用例数 | 状态 | 说明 |
|--------|--------|------|------|
| put/get 往返 | 1 | ALL PASS | FileInfo 写入后读取一致 |
| 缓存未命中 | 1 | ALL PASS | 不存在的 key 返回 None |
| 缓存损坏 | 1 | ALL PASS | 无效 JSON 不崩溃，返回 None |
| 全量模式 | 1 | ALL PASS | changed_files=None 时全部重新解析 |
| 增量模式 | 1 | ALL PASS | 未变更文件从缓存加载，不调用 parser |
| 变更重解析 | 1 | ALL PASS | changed_files 中的文件强制重新解析 |

**测试文件**: `tests/unit/test_parse_cache.py`

---

## 十二、路径工具（14 用例）

**功能描述**：路径工具模块提供跨平台的路径处理辅助函数。`relative_path` 将绝对路径转换为基于项目根目录的 POSIX 风格相对路径；`module_name_from_path` 从文件路径推导点分模块名（如 `src/analyzer/parse.py` -> `analyzer.parse`），并自动去除 `__init__` 叶节点；`safe_filename` 将文件名中的不安全字符（`<>:"/\|?*`）替换为下划线，用于生成安全的输出文件名；`ensure_dir` 递归创建目录。

> 覆盖模块：`utils/path_utils.py`

| 子功能 | 用例数 | 状态 | 说明 |
|--------|--------|------|------|
| relative_path | 4 | ALL PASS | 正常相对路径、无关路径、同目录、嵌套路径 |
| module_name_from_path | 5 | ALL PASS | Python/CPP/C 模块名、`__init__` 去除、嵌套 |
| safe_filename | 5 | ALL PASS | 正常名称、特殊字符、连续下划线、空串回退 |

**测试文件**: `tests/unit/test_path_utils.py`

---

## 十三、Markdown 工具（10 用例）

**功能描述**：Markdown 工具模块提供文档生成过程中的格式化能力。`escape_markdown` 转义 Markdown 特殊字符（反引号、星号、花括号、方括号等）以实现字面渲染；`format_code_block` 将源代码包裹为带语法高亮标记的围栏代码块（默认语言为 python）；`format_table` 从表头和数据行列表生成标准 Markdown 表格，自动处理行数不足的填充；`format_toc` 从标题-锚点元组列表生成目录列表。

> 覆盖模块：`utils/markdown_utils.py`

| 子功能 | 用例数 | 状态 | 说明 |
|--------|--------|------|------|
| 转义 | 4 | ALL PASS | 特殊字符、空串、普通文本、管道符 |
| 代码块 | 3 | ALL PASS | 默认 python、指定 c、空语言 |
| 表格 | 2 | ALL PASS | 正常表格、行数不足自动填充 |
| 目录 | 1 | ALL PASS | TOC 格式化（含空列表） |

**测试文件**: `tests/unit/test_markdown_utils.py`

---

## 十四、LLM 相关（12 用例）

**功能描述**：LLM 相关模块包含 Token 追踪器和文本分块器两个组件。TokenTracker 记录每次 LLM 调用的 prompt/completion token 使用量，支持累加统计和格式化报告输出，供分析结束时向用户展示用量概览。Chunker 将长文件内容按 token 估算值（chars/4）分块，分块时优先在空行或闭合花括号处切割以保持代码结构完整性，每个分块携带索引、起止行号和 token 估算值，供 LLM 调用时控制上下文长度。

> 覆盖模块：`llm/token_tracker.py`, `llm/chunker.py`

| 子功能 | 用例数 | 状态 | 说明 |
|--------|--------|------|------|
| Token 追踪 | 5 | ALL PASS | 初始状态、单次/多次累加、报告生成、空报告 |
| 文本分块 | 7 | ALL PASS | 短文本不分块、长文本分块、空文本、索引/行号、文件分块、token 估算 |

**测试文件**: `tests/unit/test_token_tracker.py`, `tests/unit/test_chunker.py`

---

## 十五、文档生成（9 用例）

**功能描述**：文档生成模块包含 Prompt 模板和 Markdown 写入器两个组件。Prompt 模板定义了三层知识文档的 LLM 提示词：Layer 1 项目概览（需要项目名称、技术栈、目录结构、入口点和关键文件信息）、Layer 2 模块摘要（需要模块名、路径、文件摘要、上下游依赖）、Layer 3 依赖图分析（需要 Mermaid 图、环信息和度量数据）。MarkdownWriter 负责将 KnowledgeDocument 写入文件系统，自动创建不存在的父目录，在文件头部添加标题、生成时间和标签信息。

> 覆盖模块：`generator/prompt_templates.py`, `generator/markdown_writer.py`

| 子功能 | 用例数 | 状态 | 说明 |
|--------|--------|------|------|
| Prompt 模板 | 4 | ALL PASS | Layer1/2/3 模板参数替换正确 |
| Markdown 写入 | 5 | ALL PASS | 写文档（含标题/标签）、自动创建目录、写原始内容 |

**测试文件**: `tests/unit/test_prompt_templates.py`, `tests/unit/test_markdown_writer.py`

---

## 测试过程发现并修复的生产 Bug（2 个）

| Bug | 文件 | 影响 | 修复方式 |
|-----|------|------|----------|
| `_is_async_function` 传空字符串 | `parser/languages/python.py:38-70` | `async def` 函数永远无法被识别为异步 | 改用 `child.type == "async"` 代替 `get_text(child, "")` |
| `extract_exports` 未处理 `expression_statement` | `parser/languages/python.py:303-319` | `__all__ = [...]` 导出列表永远提取不到 | 增加 `expression_statement` 层级展开 |

---

## 覆盖率总览

| 功能维度 | 用例数 | 覆盖模块 |
|----------|--------|----------|
| 数据模型 | 28 | models/* |
| Python 解析 | 12 | parser/languages/python.py |
| C/C++ 解析 | 12 | parser/languages/c_cpp.py |
| 语言注册中心 | 10 | parser/language_registry.py |
| 文件扫描 | 14 | scanner/* |
| 增量变更检测 | 5 | scanner/change_detector.py |
| 哈希工具 | 11 | utils/hashing.py |
| 依赖图分析 | 13 | analyzer/dependency_graph.py |
| 技术栈检测 | 7 | analyzer/tech_stack.py |
| 度量计算 | 9 | analyzer/metrics.py |
| 解析缓存 | 6 | utils/parse_cache.py |
| 路径工具 | 14 | utils/path_utils.py |
| Markdown 工具 | 10 | utils/markdown_utils.py |
| LLM 相关 | 12 | llm/token_tracker.py, llm/chunker.py |
| 文档生成 | 9 | generator/prompt_templates.py, generator/markdown_writer.py |
| **合计** | **177** | -- |

---

## 测试文件清单

| 文件路径 | 类型 | 用例数 |
|----------|------|--------|
| `tests/unit/test_models.py` | 单元测试 | 28 |
| `tests/unit/test_hashing.py` | 单元测试 | 11 |
| `tests/unit/test_path_utils.py` | 单元测试 | 14 |
| `tests/unit/test_markdown_utils.py` | 单元测试 | 10 |
| `tests/unit/test_parse_cache.py` | 单元测试 | 6 |
| `tests/unit/test_language_registry.py` | 单元测试 | 10 |
| `tests/unit/test_scanner.py` | 单元测试 | 14 |
| `tests/unit/test_metrics.py` | 单元测试 | 9 |
| `tests/unit/test_token_tracker.py` | 单元测试 | 5 |
| `tests/unit/test_chunker.py` | 单元测试 | 7 |
| `tests/unit/test_prompt_templates.py` | 单元测试 | 4 |
| `tests/unit/test_markdown_writer.py` | 单元测试 | 5 |
| `tests/integration/test_python_parser.py` | 集成测试 | 12 |
| `tests/integration/test_c_parser.py` | 集成测试 | 12 |
| `tests/integration/test_dependency_graph.py` | 集成测试 | 13 |
| `tests/integration/test_tech_stack.py` | 集成测试 | 7 |
| `tests/integration/test_change_detector.py` | 集成测试 | 5 |

## Fixture 项目

| 项目 | 路径 | 说明 |
|------|------|------|
| sample-py-project | `tests/integration/fixtures/sample-py-project/` | FastAPI 风格 Python 项目（含 pyproject.toml、models/api/utils 子模块） |
| sample-c-project | `tests/integration/fixtures/sample-c-project/` | CMake 风格 C 项目（含 CMakeLists.txt、include/src 目录） |
