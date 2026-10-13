# 使用指南

本目录包含 VClaw 项目的使用指南和开发文档。

## 文件说明

| 文件 | 说明 | 适用读者 |
|------|------|----------|
| `getting_started.md` | 快速入门指南 - 如何安装、配置、运行项目 | 所有用户 |
| `tools.md` | 工具集完整文档 - 9个工具的详细使用说明 | 开发者、用户 |
| `web_chat_usage.md` | Web 聊天界面使用指南 | 最终用户 |
| `web_chat_design.md` | Web 聊天界面设计方案 | 开发者 |

## 快速开始

如果你是新用户，请按以下顺序阅读：

1. 先阅读 `getting_started.md` 完成环境搭建
2. 然后阅读 `tools.md` 了解可用工具
3. 查看 `web_chat_usage.md` 使用 Web 界面
4. 查看 `examples/` 目录下的示例代码

## 工具集概览

VClaw 提供 9 个核心工具：
- **文件操作**：file_read, file_write, file_edit
- **文件搜索**：glob, grep  
- **系统命令**：bash
- **网络工具**：web_search, web_fetch
- **项目管理**：todo_write

## Web 聊天界面

使用浏览器与 VClaw 聊天：

```bash
python start_web.py
# 打开 http://localhost:8000
```

详细说明见 `web_chat_usage.md`
