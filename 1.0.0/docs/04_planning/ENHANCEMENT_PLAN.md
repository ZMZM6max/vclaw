# VClaw 功能增强实现方案

## 需求分析

### 1. L3 LLM调用管理器 + 第三方中转站API
**需求**: 支持第三方API中转站调用模型
**方案**:
- 扩展LLMProvider支持自定义base_url
- 支持多模型路由配置
- 添加代理API Provider（支持OpenRouter、API2D等中转站）

### 2. L3 任务规划重新实现（小模型驱动）
**需求**: 使用小模型实现智能任务规划
**方案**:
- 创建TaskPlannerV2类
- 使用轻量级模型（gpt-3.5-turbo/本地模型）进行任务分解
- 实现任务类型自动识别（atomic/composite/conditional）
- 支持任务依赖分析

### 3. L3 工具调用器和MemoryAccessor独立实现
**需求**: 将工具调用和记忆检索封装为独立组件
**方案**:
- 创建ToolCaller类
- 创建MemoryAccessor类
- 统一接口，便于测试和替换

### 4. L4 记忆压缩机制
**需求**: 会话上下文超限时压缩历史对话
**方案**:
- 创建MemoryCompressor类
- 当token数/消息数超限时触发压缩
- 使用LLM对历史进行摘要
- 保留关键信息，去除冗余

### 5. L5 工具描述文本化
**需求**: 将工具描述以文本形式发给模型
**方案**:
- 创建ToolContextFormatter类
- 生成自然语言格式的工具说明
- 在系统prompt中注入工具描述
- 支持few-shot示例

---

## 实现计划

### Phase 1: LLM Provider扩展
- [ ] 创建ProxyProvider支持中转站
- [ ] 添加多模型路由配置
- [ ] 更新LLMManager支持动态切换

### Phase 2: 任务规划器重构
- [ ] 实现TaskPlannerV2
- [ ] 集成小模型进行任务分解
- [ ] 添加任务类型识别

### Phase 3: L3组件独立化
- [ ] 实现ToolCaller
- [ ] 实现MemoryAccessor
- [ ] 重构Orchestration使用新组件

### Phase 4: 记忆压缩
- [ ] 实现MemoryCompressor
- [ ] 添加触发机制（token/消息数）
- [ ] 集成到L4

### Phase 5: 工具描述文本化
- [ ] 实现ToolContextFormatter
- [ ] 修改工具调用流程
- [ ] 更新prompt构建

---

## 文件变更清单

### 新增文件
```
src/
├── llm_providers/
│   └── proxy_provider.py          # 中转站API支持
├── l3_components_v2.py            # 新组件集合
│   ├── task_planner_v2.py         # 小模型任务规划
│   ├── tool_caller.py             # 工具调用器
│   └── memory_accessor.py         # 记忆访问器
├── l4_components.py               # L4组件集合
│   └── memory_compressor.py       # 记忆压缩
└── l5_components.py               # L5组件集合
    └── tool_context_formatter.py  # 工具描述格式化
```

### 修改文件
```
src/
├── llm_providers/
│   ├── __init__.py               # 导出ProxyProvider
│   └── openai_provider.py        # 支持自定义base_url
├── l3_orchestration.py           # 集成新组件
├── l4_memory.py                  # 添加压缩机制
└── l5_tools.py                   # 支持文本化工具描述
```

---

## 技术细节

### 1. 中转站API配置示例
```python
# .env
LLM_PROXY_BASE_URL=https://api.openrouter.ai/api/v1
LLM_PROXY_API_KEY=sk-xxxx
LLM_PROXY_MODEL=openai/gpt-4
```

### 2. 任务规划Prompt设计
```
你是一个任务规划专家。请将用户请求分解为可执行的子任务。

输入: {user_request}

请分析并输出任务列表（JSON格式）:
{
  "tasks": [
    {
      "id": "task_1",
      "type": "atomic|composite|conditional",
      "description": "任务描述",
      "dependencies": [],
      "estimated_tokens": 100
    }
  ]
}
```

### 3. 记忆压缩触发条件
- Token数 > 4000（接近模型上限）
- 消息数 > 20轮
- 用户请求涉及"总结"、"回顾"等关键词

### 4. 工具描述文本格式
```
可用工具:
1. python_repl - 执行Python代码
   参数: {"code": "Python代码字符串"}
   示例: {"code": "print(1+1)"}

2. calculator - 数学计算
   参数: {"expression": "数学表达式"}
   示例: {"expression": "15 * 23"}

使用方式: 当你需要调用工具时，请回复:
TOOL_CALL: {"tool": "工具名", "params": {...}}
```
