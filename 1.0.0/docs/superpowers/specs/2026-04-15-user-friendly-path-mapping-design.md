# 用户友好路径智能映射系统设计

> **Goal:** 解决 LLM 代理无法将 "桌面"、"下载" 等中文/口语化路径映射到真实操作系统路径的问题，同时保持严格的分级权限控制。

**Architecture:** 在 L5 新建 `PathMapper` 服务，统一负责路径语义解析；L3 不再硬编码 `documents/desktop` 映射，改为引导 LLM 使用自然语言路径；L5 PermissionManager 按真实路径区域配置读/写/删权限；保留 `documents/` 开头的旧沙盒路径向后兼容。

**Tech Stack:** Python, `pathlib`, `platform`, `os.path.expanduser`

---

## 背景与问题

当前系统中，L3 的系统提示词要求 LLM 做如下映射：

```
"桌面" or "desktop" -> documents/desktop
"下载" or "downloads" -> documents/downloads
```

这导致用户说"帮我在桌面上建个文档"时，文件实际被创建到了项目根目录的 `documents/desktop/` 下（如 `E:\pythonproject\vclaw\vclaw\documents\desktop\周会提醒.txt`），而不是用户电脑的**真实桌面**。

## 设计目标

1. **自然语言路径识别**："桌面"、`desktop`、`C:\Users\...\Desktop` 都能被正确解析
2. **真实操作系统路径映射**：根据当前 OS 自动解析为真实目录
3. **严格权限分级**：不同真实路径区域有不同的读/写/删权限策略
4. **向后兼容**：以 `documents/` 开头的旧路径仍然走项目内沙盒逻辑
5. **可测试、可扩展**：新增路径别名或新平台时不需要改 LLM 提示词

## 组件设计

### 1. PathMapper (`src/l5/path_mapper.py`)

单一职责：把用户友好路径解析为真实操作系统路径。

#### 支持的别名映射

| 输入别名 | Windows 真实路径 | macOS/Linux 真实路径 |
|----------|------------------|----------------------|
| `桌面`, `desktop` | `~/Desktop` | `~/Desktop` |
| `下载`, `downloads` | `~/Downloads` | `~/Downloads` |
| `文档`, `documents` | `~/Documents` | `~/Documents` |
| `图片`, `pictures` | `~/Pictures` | `~/Pictures` |
| `音乐`, `music` | `~/Music` | `~/Music` |
| `视频`, `videos` | `~/Videos` | `~/Videos` |

#### 解析规则（按优先级）

1. **如果是绝对路径**（`C:\...` 或 `/home/...`）→ 直接返回
2. **如果以 `documents/` 开头** → 映射到项目根目录下的 `documents/`（保持旧沙盒行为）
3. **如果匹配已知别名**（如 `桌面/...`）→ 映射到对应真实 OS 目录
4. **如果是单个文件名**（如 `report.txt`）→ 默认映射到 `~/Documents/report.txt`
5. **无法解析** → 抛出 `PathMappingError`

#### API

```python
class PathMapper:
    ALIASES: Dict[str, str] = {
        "桌面": "~/Desktop",
        "desktop": "~/Desktop",
        "下载": "~/Downloads",
        "downloads": "~/Downloads",
        # ...
    }

    def resolve(self, path: str) -> str:
        """Resolve user-friendly path to real OS path."""

    def _is_absolute(self, path: str) -> bool:
        """Check if path is already absolute."""

    def _match_alias(self, path: str) -> Optional[str]:
        """Try to match the first path segment against known aliases."""
```

### 2. PermissionManager 规则更新 (`src/l5/permissions.py`)

PathMapper 解析出真实路径后，PermissionManager 按路径所属区域决定权限策略：

| 路径前缀 | 读操作 | 写操作 | 删除操作 |
|----------|--------|--------|----------|
| `~/Desktop` | `AUTO_APPLY` | `ASK` | `ASK` |
| `~/Downloads` | `AUTO_APPLY` | `AUTO_APPLY` | `ASK` |
| `~/Documents` | `AUTO_APPLY` | `AUTO_APPLY` | `ASK` |
| `~/Pictures` | `AUTO_APPLY` | `ASK` | `ASK` |
| `~/Music` | `AUTO_APPLY` | `ASK` | `ASK` |
| `~/Videos` | `AUTO_APPLY` | `ASK` | `ASK` |
| `<project>/documents/**` | `AUTO_APPLY` | `AUTO_APPLY` | `ASK` |
| 其他绝对路径 | `ASK` | `ASK` | `ASK` |

默认规则（兜底）：任何不在白名单里的绝对路径，所有操作都需要确认。

### 3. L5 Tools 执行流程变更 (`src/l5/l5_tools.py`)

在工具执行前增加 **PathMapper 拦截**（以 `file_reader`、`file_writer`、`file_delete`、`terminal` 为例）：

```
用户参数 path = "桌面/周会提醒.txt"
        |
        v
[PathMapper.resolve] -> "C:\Users\Lenovo\Desktop\周会提醒.txt"
        |
        v
[PermissionManager.check_permission]
        |
        v
[实际文件操作]
```

需要修改的函数：
- `_execute_file_read`
- `_execute_file_write`
- `_execute_file_delete`
- `_execute_terminal`（提取 `working_dir` 时也做映射）

### 4. L3 提示词更新 (`src/l3/l3_orchestration.py`)

**移除**当前硬编码的 `documents/desktop` 映射规则，改为：

```
FILE PATH HANDLING:
When the user mentions a file path in natural language (e.g., "桌面", "下载", "文档"),
simply pass the path as-is in the tool parameters. The system will automatically resolve it.
Examples:
- "桌面/文件.txt" -> the user's real Desktop
- "下载/报告.pdf" -> the user's real Downloads folder
- "文档/笔记.md" -> the user's real Documents folder
- Single filename like "test.txt" -> defaults to Documents folder
- "documents/..." -> project sandbox directory (backward compatible)
```

## 数据流

```
User: "帮我在桌面上建个文档，写今天下午3点开周会"
    |
    v
L1: normalize -> StandardEvent(content="帮我在桌面上建个文档...")
    |
    v
L2: assemble SessionContext (history retrieved from L4)
    |
    v
L3: ReAct -> decides to call file_writer(path="桌面/周会提醒.txt", content="...")
    |
    v
L5:
  1. PathMapper.resolve("桌面/周会提醒.txt")
     -> "C:\Users\Lenovo\Desktop\周会提醒.txt"
  2. PermissionManager.check_permission("file_writer", "C:\Users\Lenovo\Desktop\周会提醒.txt")
     -> allowed=True, mode=AUTO_APPLY (Desktop write = ask? 根据规则表)
  3. 实际写入文件
    |
    v
User: 收到 "已在桌面上创建了名为 '周会提醒.txt' 的文档..."
```

## 需要修改的文件清单

| 文件 | 修改内容 |
|------|----------|
| `src/l5/path_mapper.py` | **新建**：PathMapper 核心实现 |
| `src/l5/tests/test_path_mapper.py` | **新建**：PathMapper 单元测试 |
| `src/l5/permissions.py` | 更新默认规则，为真实路径区域添加分级权限 |
| `src/l5/tests/test_permissions.py` | 增加真实路径权限测试用例 |
| `src/l5/l5_tools.py` | 在文件读写/终端工具执行前集成 PathMapper |
| `src/l5/tests/test_l5.py` | 更新集成测试 |
| `src/l3/l3_orchestration.py` | 更新 `_build_system_prompt` / `_build_messages`，移除硬编码映射 |
| `src/l3/tests/test_l3.py` | 更新相关测试（如果有） |
| `CLAUDE.md` | 更新 L3 提示词文档 |
| `docs/L3_Orchestration.xml` | 同步更新架构文档 |
| `src/l5/tests/README.md` | 添加 path_mapper 测试说明 |

## 测试策略

1. **PathMapper 单元测试**：覆盖 Windows/macOS/Linux 三种平台下的别名解析
2. **PermissionManager 测试**：验证 Desktop、Downloads 等路径的权限分级
3. **L5 集成测试**：验证 `file_writer("桌面/test.txt")` 最终写入真实 Desktop
4. **L3 提示词测试**：验证 LLM 不再输出 `documents/desktop` 这类旧映射

## 安全边界

- PathMapper **只解析已知别名**，不会把任意相对路径泄露到系统外
- 绝对路径（非白名单区域）默认走 `ASK` 模式
- `documents/` 开头的路径仍然被限制在项目沙盒内
- 所有文件操作最终仍经过 PermissionManager 和 SecurityEnforcer

---
