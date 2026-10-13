# L2层 1.0.1 版本 PRD

## 目标
完成VClaw 1.0.1版本中L2控制网关层的架构对齐与功能完善，确保L2层与系统架构规范一致，实现会话持久化、权限系统接入和完整的请求-响应闭环。

## 背景
L2层是六层架构的第二层，承上启下。上游接收L1的`StandardEvent`，下游组装完整的`L3Input`供L3决策，并负责L3返回`AgentAction`后的工具调用协调。当前代码功能框架基本完整，但存在关键架构缺口需要修复。

## 参考文档
- 根目录 `CLAUDE.md` — 全局开发规范与L2职责说明
- `docs/superpowers/specs/interfaces_lock.md` — 接口决策日志
- `src/l1/docs/task_plan.md` — L1层PRD（需对齐Session持久化策略）

---

## 功能规格

### 已实现的组件（保持稳定）

| 组件 | 功能 | 状态 |
|------|------|------|
| RateLimiter | 三级限流（全局/IP/用户），令牌桶算法 | 稳定 |
| MemoryAccessor | 从L4检索与用户查询相关的记忆片段 | 稳定 |
| ToolPreparer | 从L5获取工具定义，按权限筛选 | 稳定 |
| HistoryRetriever | 从L4检索会话历史记录 | 稳定 |
| ContextAssembler | 将StandardEvent组装为完整SessionContext | 稳定 |
| ControlGateway | L2主入口，限流→会话→组装→编排循环 | 稳定（框架） |

### 需要修复的缺口

#### ~~缺口1: Session持久化到L4~~ ✅ 按设计实现（与L1一致）
**决策:** 会话元数据支持可选 L4 持久化，与 L1 Session 映射持久化策略保持一致。

**当前实现:**
- `ControlGateway` 已支持可选 `memory: MemoryInterface` 注入
- `_get_or_create_session()` 内存 miss 时回查 L4 `load_user_preference()`
- 创建新会话时内存 `dict` + L4 `save_user_preference()` 双写
- `/new` 等命令触发时内存 `del` + L4 `save_user_preference(..., None)` 双删
- 定期清理过期会话时同步清理 L4
- 未提供 memory 时保持纯内存行为（向后兼容）

**L4 存储键:**
- `PREFERENCE_KEY_SESSION_META = "l2_session_metadata"`
- Value: `{"session_id": ..., "user_id": ..., "created_at": ...}`

#### ~~缺口2: 权限系统接入~~ ✅ 按设计实现（全开放策略）
**决策:** 所有用户默认拥有全部工具权限，L2 不做权限拦截。

**当前实现:**
- `ToolPreparer.ALL_PERMISSIONS` 定义了完整权限列表
- `process_event` 中 `user_permissions = ToolPreparer.ALL_PERMISSIONS`，所有用户获得全部权限
- `ToolPreparer.prepare_tools()` 按传入的权限筛选，因传入的是完整列表，所有工具均可见

**如需未来限制权限:**
- 修改 `process_event` 中的 `user_permissions` 来源（如从配置/L4读取）
- 保留 `ToolPreparer` 的筛选逻辑，无需重构

#### ~~缺口3: 响应发送路径完善~~ ✅ 按设计实现（委托L1发送）
**决策:** L2 的 `send_response()` 接收 `StandardEvent` + 结果文本，委托给注入的 `l1_sender.send_response()` 发送。如未注入 L1，降级为打印（开发调试）。

**当前实现:**
- `ControlGateway` 支持可选 `l1_sender` 注入
- `send_response(event, result)` 调用 `l1_sender.send_response(user_id, content, channel, metadata)`
- 保持 L1 的渠道格式化能力（Telegram/WebSocket/Webhook）
- 无 L1 时降级为 `print(...)`

**上层调用流程:**
```python
event = l1.receive_payload(raw_data)
l3_input = l2.process_event(event)      # L2 组装上下文
result = l3.run(l3_input)               # 上层调 L3
l2.send_response(event, result)          # L2 委托 L1 发送
```

#### ~~缺口4: ReAct循环迭代安全~~ ❌ 不在L2职责内
**说明:** ReAct 循环已移至 L3 或上层调用方，L2 不再持有 `l3_orchestrator`，`_orchestrate_loop()` 已删除。迭代安全由调用 L3 的上层负责处理。

---

## 开发阶段

```
Phase 1: 现状分析与方案确认 ────┐
                                ├──→ Phase 2: 测试增强
Phase 2: Session持久化实现 ──────┤
                                     │
                                     ▼
                               Phase 3: 文档同步
```

**执行时机:** 建议等待用户确认Phase 1方案后实施。

---

## 测试规格

### 新增测试文件

```
src/l2/tests/
├── test_session_persistence.py      # Session持久化（内存+L4）
├── test_response_path.py            # 响应发送路径
├── test_rate_limiter_edge_cases.py  # 限流边界情况
└── test_integration_l1_l2.py        # L1→L2集成
```

### 测试要求
- 所有现有测试继续通过（无回归）
- 新增单元测试覆盖率 ≥ 90%
- 每个测试文件在 `README.md` 中登记

---

## 风险

| 风险 | 影响 | 应对 |
|------|------|------|
| Session持久化可能影响性能 | 中 | 内存缓存 + 异步写L4，批量持久化 |
| Session持久化与L1 Session映射重复 | 低 | 明确分工：L1管映射，L2管会话元数据 |

---

## 提交计划

| 阶段 | 提交信息 |
|------|----------|
| Phase 1 | `docs(l2): add planning docs (CLAUDE.md, progress.md, task_plan.md)` |
| Phase 2 | `feat(l2): persist session metadata to L4 with lazy loading` |
| Phase 3 | `test(l2): add unit tests for session and response` |
| Phase 4 | `docs(l2): sync README and CLAUDE.md with L2 changes` |

---

*版本: 1.0.1*
*创建时间: 2026-04-24*
