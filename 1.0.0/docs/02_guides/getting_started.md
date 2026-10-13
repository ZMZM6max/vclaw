# VClaw 项目运行指南

## 1. 环境准备

### 安装依赖

```bash
# 基础依赖
pip install -r requirements.txt

# 工具集可选依赖（用于 web_fetch）
pip install requests beautifulsoup4

# 图片处理可选依赖（用于 file_read 图片）
pip install Pillow
```

### 配置文件

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env 文件，填入你的 API keys
```

**.env 最小配置（仅使用 Mock 模式）：**
```bash
# 使用 Mock 模式（无需真实 API key）
LLM_PROVIDER=mock
EMBEDDING_PROVIDER=mock
```

**.env 完整配置（使用真实 API）：**
```bash
# OpenAI 配置
OPENAI_API_KEY=sk-your-key
OPENAI_MODEL=gpt-4

# 代理/中转站（可选）
LLM_PROXY_BASE_URL=https://api.openrouter.ai/api/v1
LLM_PROXY_API_KEY=sk-your-key

# 任务规划器（使用小模型节省成本）
LLM_PLANNER_MODEL=gpt-3.5-turbo

# 嵌入模型
EMBEDDING_MODEL=text-embedding-ada-002

# Web 搜索（可选）
GOOGLE_API_KEY=your-key
GOOGLE_CSE_ID=your-cse-id
```

## 2. 运行测试

### 运行所有测试

```bash
# 运行全部 55 个测试
pytest tests/ -v

# 或简写
python -m pytest tests/ -v
```

### 运行特定层次测试

```bash
# L1 - 用户接入层
pytest tests/test_l1.py -v

# L2 - 控制网关层
pytest tests/test_l2.py -v

# L3 - 逻辑编排层
pytest tests/test_l3.py -v

# L4 - 记忆层
pytest tests/test_l4.py -v

# L5 - 工具层
pytest tests/test_l5.py -v

# L6 - 运行时层
pytest tests/test_l6.py -v
```

### 运行集成测试

```bash
# 端到端集成测试
pytest tests/test_integration.py -v

# 仅运行特定集成测试
pytest tests/test_integration.py::TestEndToEndWorkflows -v
```

### 运行工具测试

```bash
# 运行工具演示
python examples/tools_demo.py
```

## 3. 交互式使用

### Python 交互式环境

```python
# 启动 Python
python

# 导入 VClaw 组件
>>> from src.l3_orchestration import Orchestration
>>> from src.l2_control_gateway import ControlGateway
>>> from src.models import SessionContext

# 创建会话上下文
>>> context = SessionContext(
...     session_id="test-001",
...     user_id="user-001",
...     current_query="Hello, VClaw!"
... )

# 运行编排层
>>> orch = Orchestration()
>>> result = orch.run(context)
>>> print(result)
```

### 使用新工具集

```python
import asyncio
from src.tools import tool_manager

async def main():
    # 列出所有工具
    print("可用工具:", tool_manager.list_tools())
    
    # 使用 bash 工具
    result = await tool_manager.call("bash", command="echo Hello")
    print(result.content)
    
    # 使用 grep 工具
    result = await tool_manager.call("grep", 
        pattern="class ", 
        path="src", 
        glob="*.py"
    )
    print(result.content)

asyncio.run(main())
```

## 4. 启动 Web 服务（可选）

如需 Web 界面，可以创建一个简单的 FastAPI 服务：

```bash
# 安装 FastAPI
pip install fastapi uvicorn

# 启动服务
uvicorn src.web:app --reload --port 8000
```

## 5. 验证安装

### 快速验证

```bash
# 验证 Python 版本
python --version  # 需要 3.11+

# 验证依赖安装
python -c "import pydantic; print('Pydantic OK')"
python -c "from src.tools import tool_manager; print('Tools OK')"

# 运行快速测试
python -m pytest tests/test_l5.py -v
```

### 完整验证

```bash
# 运行所有测试（约 2 分钟）
python -m pytest tests/ -v --tb=short

# 预期结果：
# - 单元测试：全部通过
# - 集成测试：部分可能失败（需要 API key）
```

## 6. 常见问题

### 问题 1: ModuleNotFoundError: No module named 'src'

**解决：** 在项目根目录运行，或设置 PYTHONPATH

```bash
# Windows
set PYTHONPATH=E:\pythonproject\vclaw\vclaw

# Linux/Mac
export PYTHONPATH=/path/to/vclaw
```

### 问题 2: API key 错误

**解决：** 使用 Mock 模式测试

```bash
# 编辑 .env
LLM_PROVIDER=mock
EMBEDDING_PROVIDER=mock
```

### 问题 3: 编码错误（Windows）

**解决：** 设置 UTF-8 编码

```bash
# Windows PowerShell
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# 或在运行前设置环境变量
set PYTHONIOENCODING=utf-8
```

## 7. 开发工作流

### TDD 开发流程

```bash
# 1. 编写测试
# tests/test_new_feature.py

# 2. 运行测试（应该失败）
pytest tests/test_new_feature.py -v

# 3. 实现功能
# src/lx_component.py

# 4. 运行测试（应该通过）
pytest tests/test_new_feature.py -v

# 5. 运行所有测试确保没有破坏
pytest tests/ -v
```

### 添加新工具

```bash
# 1. 创建工具文件
# src/tools/my_tool.py

# 2. 在 manager.py 注册

# 3. 测试工具
python -c "from src.tools import tool_manager; tool_manager.call('my_tool', ...)"
```

## 8. 生产部署

### Docker 部署

```bash
# 构建镜像
docker build -t vclaw .

# 运行容器
docker run -p 8000:8000 --env-file .env vclaw
```

### 系统服务

```bash
# 使用 systemd (Linux)
sudo systemctl enable vclaw
sudo systemctl start vclaw
```

## 快速开始命令总结

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置环境
# 编辑 .env 文件（使用 mock 模式无需配置）

# 3. 运行测试
pytest tests/ -v

# 4. 运行演示
python examples/tools_demo.py

# 5. 交互式使用
python
>>> from src.tools import tool_manager
>>> import asyncio
>>> asyncio.run(tool_manager.call("bash", command="echo Hello VClaw!"))
```

## 项目状态

- ✅ **单元测试**: 49/49 通过
- ✅ **集成测试**: 部分需要 API key
- ✅ **工具集**: 9 个工具全部可用
- ✅ **架构**: 六层架构完整实现

**推荐首次运行方式：**

```bash
# 不配置 API key，使用 Mock 模式
pytest tests/test_l1.py tests/test_l2.py tests/test_l3.py tests/test_l4.py tests/test_l5.py tests/test_l6.py -v
```
