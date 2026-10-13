# L1层 1.0.1 版本 PRD

## 目标
完成VClaw 1.0.1版本中L1用户交互层的架构对齐与功能完善，确保L1层与XML规范完全一致，消除代码重复，建立完整的错误回流处理机制。

## 背景
L1层是六层架构的最顶层，负责所有外部输入的接收、解析、验证和标准化。当前代码功能基本完整，但存在两个关键架构缺口需要修复。

## 参考文档
- `docs/03_specs/L1_UserInteraction.xml` — L1 XML规范（只读）
- `docs/superpowers/specs/2026-04-22-layer-by-layer-build-design-zh.md` — 逐层构建设计（只读）

---

## 功能规格

### 已实现的组件（保持稳定）

| 组件 | 功能 | 状态 |
|------|------|------|
| ProtocolAdapter | Telegram/WebSocket/Webhook三种协议适配 | 稳定 |
| DataValidator | 字段验证、注入检测、渠道校验 | 稳定 |
| EventNormalizer | 自动选择适配器，统一输出StandardEvent | 稳定 |
| UserInteraction | L1主入口，整合所有组件 | 稳定 |
| ErrorHandler（重试部分） | 指数退避重试机制 | 稳定 |

### 需要修复的缺口

#### 缺口1: ErrorHandler职责扩展
**问题:** 当前ErrorHandler仅实现了重试机制，缺少L3业务错误经L2回流后的协议级格式化能力。

**规格要求:**
- ErrorHandler需支持两类错误：
  1. L1内部错误（连接/协议/格式）→ 重试+指数退避
  2. L3业务错误（经L2回流）→ 协议级格式化输出
- 支持三种渠道的格式化：
  - Telegram: 返回Telegram消息结构
  - WebSocket: 返回JSON结构
  - Webhook: 返回HTTP状态码+body

**执行策略（2026-04-23更新）:**
- **Step 1（Phase 2先做）**: 实现 `handle_error()` 路由框架和 `format_for_*` 三个空壳方法，保持现有重试逻辑不变
- **Step 2（延后到L3完成后）**: 等 `L3.ErrorTranslator` 的错误输出结构确定后，再填充具体的业务错误格式化逻辑
- **原因**: 必须先知道L3输出什么错误结构（错误码、字段、语义），才能写对应的格式化逻辑，否则只能写无意义的占位符

**验收标准:**
- [x] `handle_error()` 方法能根据错误类型和渠道路由到对应格式化方法
- [x] `format_for_telegram()` 返回符合Bot API要求的消息结构（框架就绪，业务逻辑待L3完成后填充）
- [x] `format_for_websocket()` 返回有效的JSON对象（框架就绪，业务逻辑待L3完成后填充）
- [x] `format_for_webhook()` 返回 `(status_code, body)` 元组（框架就绪，业务逻辑待L3完成后填充）
- [ ] 业务错误格式化逻辑填充（待L3 ErrorTranslator输出结构确定后实施）

#### 缺口2: SessionManager重复消除 + 持久化
**问题:** `UserInteraction`类与独立`SessionManager`类实现了完全相同的会话映射逻辑；且 `_user_session_map` 为纯内存，重启即丢失。

**规格要求:**
- 仅保留一份会话映射实现
- L1只负责 `user_id → session_id` 映射，不管理会话生命周期
- 生命周期管理（创建、过期、历史记录）属于L2职责
- 映射关系支持 L4 持久化（可选注入 `MemoryInterface`），内存作为热缓存

**验收标准:**
- [x] 代码中只有一份会话映射逻辑
- [x] 独立`SessionManager`类已删除
- [x] `UserInteraction`文档字符串明确说明职责边界
- [x] 支持可选的 `memory: MemoryInterface` 注入
- [x] 启动时从 L4 懒加载映射（内存 miss 时回查 L4）
- [x] 更新映射时内存 + L4 双写
- [x] `/new` 命令时内存 + L4 双删
- [x] 未提供 memory 时保持纯内存行为（向后兼容）

#### 缺口3（可选）: 响应返回路径恢复
**问题:** 1.0.1删除了`send_response()`，L2无法通过L1向用户返回响应。

**规格要求:**
- 恢复/实现`send_response`方法
- 将L2返回的文本格式化为渠道特定结构
- 不依赖已删除的`StandardResponse`模型

**验收标准:**
- [x] `send_response(user_id, content, channel=None, metadata=None)` 接口可用
- [x] 支持Telegram/WebSocket/Webhook三种输出格式
- [x] 默认自动从请求上下文查找渠道信息，支持显式传入覆盖
- [ ] 引入 `request_id` 全链路追踪后，彻底消除 user_id 并发覆盖问题（跨层改进，后续实施）

---

## 开发阶段

```
Phase 2: ErrorHandler扩展 ──┐
                             ├──→ Phase 5: 测试增强
Phase 3: SessionManager去重 ─┤
                             │
Phase 4: 响应路径恢复 ────────┘
                                  │
                                  ▼
                            Phase 6: 文档同步
```

**执行时机:** 建议等待Phase 0-1（核心契约锁定+6个关键缺口修复）完成后实施。

---

## 测试规格

### 新增测试文件

```
src/l1/tests/
├── test_error_handler_business.py      # 业务错误格式化
├── test_error_handler_protocol.py      # 协议级格式化
├── test_response_sender.py             # 响应发送（如Phase4实施）
└── test_adapter_edge_cases.py          # 适配器边界情况
```

### 测试要求
- 所有现有测试继续通过（无回归）
- 新增单元测试覆盖率 ≥ 90%
- 每个测试文件在 `README.md` 中登记

---

## 风险

| 风险 | 影响 | 应对 |
|------|------|------|
| 删除SessionManager类可能影响其他层引用 | 中 | 全局搜索引用，如有则迁移到UserInteraction |
| ErrorHandler扩展可能破坏现有重试逻辑 | 中 | 保持现有方法签名不变，新增方法而非修改 |
| send_response设计需与L2输出格式对齐 | 高 | 与L2开发同步，先定义接口契约再实现 |

---

## 提交计划

| 阶段 | 提交信息 |
|------|----------|
| Phase 2 | `feat(l1): extend ErrorHandler to support business error formatting from L3` |
| Phase 3 | `refactor(l1): remove duplicate SessionManager, consolidate session logic` |
| Phase 4 | `feat(l1): restore send_response for L2→L1 output path` |
| Phase 5 | `test(l1): add unit tests for ErrorHandler and edge cases` |
| Phase 6 | `docs(l1): sync README and CLAUDE.md with L1 changes` |

---

*版本: 1.0.1*
*创建时间: 2026-04-23*
