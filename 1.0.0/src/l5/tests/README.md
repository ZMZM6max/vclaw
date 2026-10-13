# src/l5/tests/README.md

## L5 能力抽象层测试

本目录包含 L5 Tools & Capabilities 层的所有单元测试。

## 测试文件列表

| 文件 | 用途 | 依赖 | 状态 |
|------|------|------|------|
| `test_l5.py` | L5 核心功能测试（12 个） | 无 | ✅ 已完成 |
| `test_confirmation.py` | 二次确认机制测试（12 个） | 无 | ✅ 已完成 |
| `test_path_validation.py` | 沙盒路径验证测试（5 个） | 无 | ✅ 已完成 |
| `test_path_mapper.py` | PathMapper 单元测试 | 无额外依赖 | ✅ 已完成 |
| `test_permissions.py` | 权限验证测试（含真实 OS 路径权限） | 无 | ✅ 已完成 |

## 依赖清单

```bash
# 无需额外依赖，使用项目标准依赖
pip install -r requirements.txt
```

## 运行方法

```bash
# 运行所有 L5 测试
pytest src/l5/tests/ -v

# 运行特定测试文件
pytest src/l5/tests/test_l5.py -v
pytest src/l5/tests/test_confirmation.py -v
pytest src/l5/tests/test_path_validation.py -v
pytest src/l5/tests/test_path_mapper.py -v
pytest src/l5/tests/test_permissions.py -v

# 运行特定测试
pytest src/l5/tests/test_confirmation.py::TestFileDeleteTool::test_file_delete_first_request_returns_confirmation_required -v
```

## 测试覆盖

- **工具执行**: python_repl, calculator, search_web, file_reader, file_writer, file_delete, terminal
- **确认机制**: 首次请求、确认执行、过期处理、无效 ID 处理、批量删除计数
- **路径验证**: 沙盒前缀、目录遍历、绝对路径防护
- **路径映射**: 用户友好路径（桌面/下载/文档等）到真实 OS 路径的自动解析
- **权限测试**: 真实 OS 路径的读写权限检查（基于当前运行用户）

## 注意事项

- 所有测试使用 `tmp_path` fixture 创建隔离的临时目录
- file_delete 测试需要文件系统写权限
- 确认过期测试使用 0 秒 TTL 加速测试
- Windows 路径使用 `os.chdir(tmp_path)` 切换到临时目录
