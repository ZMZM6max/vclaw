# VClaw Web 聊天界面使用指南

通过浏览器与 VClaw 进行实时聊天的完整指南。

## 启动服务

### 方式一：使用启动脚本（推荐）

```bash
python start_web.py
```

### 方式二：直接使用 uvicorn

```bash
uvicorn src.web_server:app --reload --host 0.0.0.0 --port 8000
```

### 方式三：Python 模块

```bash
python -m src.web_server
```

## 访问界面

服务启动后，在浏览器中打开：

```
http://localhost:8000
```

## 功能特性

### ✅ 已实现

- **实时聊天** - WebSocket 双向通信
- **流式响应** - AI 回复逐字显示（打字机效果）
- **Markdown 支持** - 代码高亮、列表、粗体等
- **多会话支持** - 每个连接独立会话
- **对话历史** - 保留当前会话上下文
- **响应式设计** - 支持桌面和移动端
- **一键清除** - 清除当前对话

### 📝 界面元素

| 元素 | 说明 |
|------|------|
| 🤖 | AI 助手头像 |
| 👤 | 用户头像 |
| 思考中... | AI 正在处理 |
| ▋▋▋▋ | 流式输出指示器 |
| 发送按钮 | 发送消息 |
| 清除按钮 | 清除对话 |

## 使用方法

### 基本对话

1. 在输入框中输入消息
2. 按 **Enter** 发送（或点击发送按钮）
3. 按 **Shift+Enter** 换行
4. 等待 AI 响应（会显示"思考中..."）

### 代码提问示例

```
请帮我写一个 Python 函数，计算斐波那契数列的前 n 项
```

AI 会返回带语法高亮的代码：

```python
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)
```

### 文件操作示例

```
帮我查找项目中所有包含 "class" 的 Python 文件
```

AI 会自动使用工具执行：

```
[使用工具: grep]
找到 5 个文件...
```

### 网络搜索示例

```
搜索 Python 3.12 的新特性
```

## 技术细节

### 通信协议

- **协议**: WebSocket
- **路径**: `/ws/chat`
- **消息格式**: JSON

### 消息类型

**客户端 → 服务器**

```json
{
  "message": "用户输入的消息"
}
```

**服务器 → 客户端**

```json
// 会话信息
{
  "type": "session",
  "session_id": "abc123"
}

// 思考中
{
  "type": "thinking",
  "content": "思考中..."
}

// 流式内容
{
  "type": "chunk",
  "content": "响应片段"
}

// 完成
{
  "type": "complete",
  "content": "完整响应"
}

// 错误
{
  "type": "error",
  "message": "错误信息"
}
```

## API 接口

### 获取会话历史

```bash
GET /api/sessions/{session_id}/history
```

### 清除会话

```bash
POST /api/sessions/{session_id}/clear
```

## 配置文件

通过 `.env` 文件配置：

```bash
# LLM 配置
OPENAI_API_KEY=sk-your-key
OPENAI_MODEL=gpt-4

# 或使用 Mock 模式（无需 API key）
LLM_PROVIDER=mock
```

## 故障排除

### 问题 1：无法连接到服务器

**解决**：检查防火墙设置，确保端口 8000 开放

```bash
# 测试连接
curl http://localhost:8000
```

### 问题 2：WebSocket 连接失败

**解决**：检查浏览器控制台，确保使用兼容的浏览器（Chrome/Firefox/Edge）

### 问题 3：AI 无响应

**解决**：
1. 检查 `.env` 中的 LLM 配置
2. 切换到 Mock 模式测试
3. 查看服务器日志

### 问题 4：中文乱码

**解决**：确保浏览器使用 UTF-8 编码

## 自定义开发

### 修改界面

编辑 `src/web/static/index.html`：

```html
<!-- 修改主题色 -->
<style>
  .bg-blue-600 { background-color: #your-color; }
</style>
```

### 添加功能

在 `src/l1_web_interface.py` 中添加：

```python
async def custom_handler(self, message: str):
    # 自定义处理逻辑
    pass
```

## 扩展计划

- [ ] 用户认证系统
- [ ] 聊天记录持久化
- [ ] 文件上传功能
- [ ] 多用户并发
- [ ] 深色主题

## 参考

- 设计文档: `docs/02_guides/web_chat_design.md`
- 项目结构: `PROJECT_STRUCTURE.md`
