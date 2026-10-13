# L2 Control Gateway Tests

L2 控制网关层测试文档

## 测试文件列表

| 测试文件 | 用途 | 测试类 | 状态 |
|----------|------|--------|------|
| `test_rate_limiter.py` | 限流器测试（基础 + 增强） | TestRateLimiter, TestEnhancedRateLimiter | 通过 |
| `test_l3_input.py` | L3Input 数据模型测试 | TestL3Input | 通过 |
| `test_memory_accessor.py` | MemoryAccessor 组件测试 | TestMemoryAccessor | 通过 |
| `test_tool_preparer.py` | ToolPreparer 组件测试 | TestToolPreparer | 通过 |
| `test_control_gateway.py` | ControlGateway 测试 | TestControlGateway, TestControlGatewayEnhanced | 通过 |
| `test_tools_interface.py` | ToolsInterface 接口测试 | TestToolsInterface | 通过 |
| `test_l2_l3_contract.py` | L2-L3 契约测试 | TestL2L3Contract | 通过 |
| `test_integration.py` | 集成测试 | TestL2Integration, TestL2ErrorHandling | 通过 |

## 测试类说明

### TestRateLimiter
限流器基础测试：
- `test_rate_limit_allows_under_limit` - 限制内请求通过
- `test_rate_limit_blocks_over_limit` - 超限请求被拒绝

### TestEnhancedRateLimiter
增强限流器测试（IP/全局）：
- `test_rate_limit_with_ip` - IP级限流
- `test_rate_limit_global_blocks_all` - 全局限流
- `test_rate_limit_ip_blocks_same_ip` - 同IP不同用户限流
- `test_rate_limit_without_ip` - 无IP场景

### TestL3Input
数据模型测试：
- `test_l3input_creation` - L3Input 创建
- `test_l3input_optional_fields` - 可选字段默认值
- `test_l3input_contains_session_context` - 包含会话上下文
- `test_l3input_multiple_tools` - 多工具支持
- `test_l3input_multiple_memories` - 多记忆支持

### TestMemoryAccessor
记忆访问器测试：
- `test_memory_accessor_retrieves_relevant_memories` - 检索相关记忆
- `test_memory_accessor_returns_empty_list_when_no_results` - 空结果处理
- `test_memory_accessor_uses_default_memory` - 默认内存实例
- `test_memory_accessor_filters_by_user_id` - 用户ID过滤
- `test_memory_accessor_respects_top_k` - top_k 参数
- `test_memory_accessor_extracts_content_only` - 内容提取

### TestToolPreparer
工具准备器测试：
- `test_tool_preparer_returns_all_tools_with_no_permissions` - 无权限筛选
- `test_tool_preparer_filters_by_permissions` - 权限过滤
- `test_tool_preparer_returns_all_tools_with_all_permissions` - 全权限
- `test_tool_preparer_uses_default_tools` - 默认工具实例
- `test_tool_preparer_permission_map` - 权限映射验证
- `test_tool_preparer_multiple_permissions` - 多权限处理
- `test_tool_preparer_unknown_tools` - 未知工具处理

### TestControlGateway
核心网关功能测试：
- `test_session_creation_and_context_assembly` - 会话创建与上下文组装
- `test_rate_limit_triggered` - 限流触发机制
- `test_history_retrieval_and_concatenation` - 历史记录检索
- `test_send_response` - 响应发送
- `test_no_auth_required` - 无认证模式

### TestControlGatewayEnhanced
增强网关测试：
- `test_process_event_returns_l3input` - 返回 L3Input
- `test_process_event_passes_ip_to_rate_limiter` - IP 传递
- `test_process_event_includes_all_l3input_fields` - 完整 L3Input 字段
- `test_session_context_contains_metadata` - 元数据包含

### TestToolsInterface
接口测试：
- `test_tools_interface_can_be_implemented` - 接口可实现
- `test_tools_interface_requires_execute_method` - execute 方法要求
- `test_tools_interface_requires_list_tools_method` - list_tools 方法要求
- `test_mock_tools_returns_expected_format` - 返回格式验证

### TestL2L3Contract
L2-L3 契约测试：
- `test_l2_outputs_l3input_type` - 输出类型验证
- `test_l3input_contains_session_context` - 包含 SessionContext
- `test_l3input_contains_available_tools` - 包含可用工具
- `test_l3input_contains_relevant_memories` - 包含相关记忆
- `test_session_context_has_required_fields` - 必需字段验证
- `test_l3input_optional_fields_have_defaults` - 可选字段默认值
- `test_tools_have_required_fields` - 工具必需字段

### TestL2Integration
集成测试：
- `test_complete_flow_with_all_components` - 完整流程
- `test_rate_limit_integration` - 限流集成
- `test_session_persistence_across_requests` - 会话持久化
- `test_different_users_get_different_sessions` - 不同用户不同会话
- `test_memory_accessor_filters_by_user` - 记忆用户过滤
- `test_tool_preparer_respects_permissions` - 工具权限
- `test_new_session_with_ip_tracking` - IP 追踪

### TestL2ErrorHandling
错误处理测试：
- `test_rate_limit_error_message` - 限流错误消息
- `test_memory_search_failure_handling` - 记忆搜索失败
- `test_empty_tool_list_handling` - 空工具列表

## 依赖清单

```bash
# 基础依赖
pip install pytest

# 项目依赖（已安装）
# - pydantic (src/core/models.py)
# - 项目内各层模块
```

## 如何运行测试

```bash
# 运行所有 L2 测试
pytest src/l2/tests/ -v

# 运行特定测试文件
pytest src/l2/tests/test_rate_limiter.py -v
pytest src/l2/tests/test_control_gateway.py -v
pytest src/l2/tests/test_integration.py -v

# 运行特定测试类
pytest src/l2/tests/test_rate_limiter.py::TestEnhancedRateLimiter -v
pytest src/l2/tests/test_control_gateway.py::TestControlGatewayEnhanced -v

# 运行特定测试用例
pytest src/l2/tests/test_control_gateway.py::TestControlGateway::test_session_creation_and_context_assembly -v

# 运行速率限制相关测试
pytest src/l2/tests/ -k "rate_limit" -v

# 运行集成测试
pytest src/l2/tests/test_integration.py -v

# 运行契约测试
pytest src/l2/tests/test_l2_l3_contract.py -v
```

## 测试架构

```
src/l2/tests/
├── test_rate_limiter.py          # 限流器组件测试
├── test_l3_input.py              # 数据模型测试
├── test_memory_accessor.py       # MemoryAccessor 组件测试
├── test_tool_preparer.py         # ToolPreparer 组件测试
├── test_control_gateway.py       # ControlGateway 核心测试
├── test_tools_interface.py       # 接口契约测试
├── test_l2_l3_contract.py        # L2-L3 层间契约测试
├── test_integration.py           # 集成测试
└── README.md                     # 本文档
```

## 注意事项

1. **Mock 依赖**: 所有测试使用 `unittest.mock` 模拟 L4/L5 依赖
2. **无外部服务**: 测试为纯单元测试，不依赖外部服务
3. **状态隔离**: 每个测试用例独立运行，确保状态不互相影响
4. **命名规范**: 测试文件以 `test_` 开头，测试类以 `Test` 开头

## 测试覆盖率

- RateLimiter: 用户级、IP级、全局三级限流
- MemoryAccessor: L4 记忆检索
- ToolPreparer: L5 工具权限筛选
- ControlGateway: 完整 L3Input 组装
- L2-L3 Contract: 层间接口契约

---
最后更新: 2026-04-12
