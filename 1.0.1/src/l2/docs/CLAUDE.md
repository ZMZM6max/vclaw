# L2: Control Gateway Layer - Claude Code Guide

> **Purpose:** 记录L2层的开发习惯、偏好和需要Claude Code记住的上下文。不是技术文档，是协作备忘录。

---

## 1. 文档分工习惯（重要）

用户要求每层开发文档统一放在 `src/l*/docs/`，且每个文件有明确分工：

| 文件 | 职责 | 谁能修改 |
|------|------|----------|
| `progress.md` | 记录开发过程：做了什么、没做什么、以后可完善的 | Claude Code + 用户 |
| `CLAUDE.md` | 记录开发习惯、用户偏好、需要AI记住的东西 | Claude Code + 用户 |
| `task_plan.md` | 当前模块的PRD：目标、功能规格、验收标准 | Claude Code + 用户 |
| `docs/03_specs/` | 上层架构设计参考文档 | **一般不修改**，只读参考 |

**Claude Code必须遵守：**
- 技术方案、接口设计、实现细节 → 写入 `task_plan.md`
- 今天做了什么、遇到什么坑、还有什么没做 → 写入 `progress.md`
- 用户说"以后记得..."、"我喜欢..."、"不要..." → 写入 `CLAUDE.md`

---

## 2. 用户开发习惯

### 2.1 代码组织
- 源码：`src/l2/`
- 测试：`src/l2/tests/`
- 开发文档：`src/l2/docs/`（本目录）
- 跨层集成测试：`tests/integration/`

### 2.2 提交习惯
- **更改完成后不要自动提交**，由用户自行提交
- 提交信息格式：`feat(l2): ...` / `fix(l2): ...` / `test(l2): ...`
- 完成代码/文档修改后，执行 `git diff` 或 `git status` 展示更改，等待用户确认

### 2.3 测试习惯
- 单元测试：模拟所有外部依赖
- 真实环境测试：需要 `.env` 文件中的配置
- 每个测试文件必须在 `src/l2/tests/README.md` 中登记
- 运行测试前确保conda环境已激活：`conda activate vclaw`

### 2.4 文档同步规则（重要）
- **更改代码后必须同步更新相关MD文档**，不能只改代码不改文档
- 有更新想法、设计变更、接口调整后 → 立即同步 `CLAUDE.md` 或 `task_plan.md`
- 完成某项功能后 → 立即同步 `progress.md` 记录里程碑
- 修改XML规范后 → 同步所有引用该规范的文件
- **禁止**：代码和文档长期不一致

### 2.5 架构优先
- 先读XML规范，再写代码
- 发现代码与XML规范不一致时，先记录缺口，再制定修复计划
- 重视职责边界（如L1只管映射、L2管生命周期、L3管决策）

### 2.6 隐私信息
- 所有API Key、Bot Token必须放在 `.env` 文件中
- `.env` 已被 `.gitignore` 排除
- 不要硬编码任何敏感信息

---

## 3. L2层关键记忆

### 3.1 职责边界（经常混淆，需要提醒）

**L1.SessionManager vs L2.ControlGateway**
- L1：只维护 `user_id → session_id` 映射（"谁是谁"），可选持久化到 L4
- L2：负责 `session_id → SessionContext` 生命周期（创建、获取、更新、过期）
- **边界**：L1 不管会话 TTL、历史记录、状态存储——此类职责属于 L2

**L2 vs L3 的职责边界**
- L3：是"决策者"（Decider），决定**调用什么工具**，返回 `AgentAction`
- L2：是"组装者"（Assembler），负责**组装 L3Input**，不持有 L3 实例，不跑 ReAct 循环
- L5：是"执行者"（Executor），实际**执行工具**
- **关键**：L3 不直接调用 L5，ReAct 循环由上层（调用方）编排，L2 只提供上下文

**L2 的权限策略（全开放）**
- **设计决策**：所有用户默认拥有全部工具权限，L2 不做权限拦截
- `ToolPreparer.ALL_PERMISSIONS` 包含所有权限，`process_event` 直接赋值给所有用户
- 权限筛选逻辑保留在 `ToolPreparer` 中，但当前传入的是完整权限列表
- 后续如需限制权限，只需修改 `process_event` 中的 `user_permissions` 来源即可

**ToolPreparer 权限解析优先级（新增）：**
1. 优先读取工具元数据中的 `required_permission` 字段（L5 为权威来源）
2. 无则回退到本地 `TOOL_PERMISSION_MAP`（向后兼容）
3. 均未命中则默认 `None`（无需权限）

### 3.2 process_event 内部流程（重要）

**当前实现（委托 ContextAssembler）：**
```python
# process_event() 步骤：
# 1. RateLimiter 限流检查
# 2. _get_or_create_session() 获取/创建会话（支持可选 L4 持久化）
# 3. ContextAssembler.assemble() 组装 SessionContext（含历史记录）
# 4. ToolPreparer.prepare_tools() 获取可用工具（L5 不可用时降级为空列表）
# 5. MemoryAccessor.retrieve_relevant() 获取相关记忆（L4 不可用时降级为空列表）
# 6. 返回 L3Input
```

**关键设计：**
- `ControlGateway` 初始化时创建 `ContextAssembler`，并复用其内部 `memory_accessor` 和 `tool_preparer`
- `process_event()` 不再直接调用各组件，而是委托 `ContextAssembler` 组装 `SessionContext`
- L5/L4 不可用时降级为空列表，避免阻塞用户请求

### 3.3 Session 管理行为（重要）

**当前实现（内存 + L4 可选持久化 + 3600s TTL）：**
```python
# sessions: Dict[str, Dict] = {session_id: {"user_id": ..., "created_at": ...}}
# 有 memory 时：内存缓存 + L4 双写双删
# 无 memory 时：纯内存（向后兼容）
# 每 100 次请求清理过期会话
```

**持久化策略（与 L1 保持一致）：**
- 创建/更新会话：内存 `dict` + L4 `save_user_preference()` 双写
- `/new` 等命令：内存 `del` + L4 `save_user_preference(..., None)` 双删
- 内存 miss 时：回查 L4 `load_user_preference()`，查到后回填内存
- `PREFERENCE_KEY_SESSION_META = "l2_session_metadata"`

**新建/重置会话：**
- L1 收到 `/new` 等命令 → 清除 `user_id → session_id` 映射 → 传 `session_id=None` 给 L2
- L2 发现 `session_id=None` 或无效 → 创建新 `UUID`
- **已实现**：L2 显式检查 `event.metadata.get("is_new_session_request")`，为 True 时主动删除旧会话并创建新会话

### 3.3 当前已知问题（开发时需关注）

1. **~~Session 无持久化~~ ✅ 按设计实现（与L1一致）**
   - 当前支持可选 L4 持久化：内存缓存 + L4 双写双删
   - 无 memory 时保持纯内存行为（向后兼容）
   - `PREFERENCE_KEY_SESSION_META = "l2_session_metadata"`

2. **~~权限系统未接入~~ ✅ 按设计实现（全开放）**
   - 所有用户默认拥有 `ToolPreparer.ALL_PERMISSIONS` 全部权限
   - `process_event` 中直接赋值完整权限列表，不拦截任何工具
   - 如需未来限制权限，修改 `user_permissions` 来源即可

3. **~~`is_new_session_request` 标志未使用~~ ✅ 已修复**
   - L2 的 `_get_or_create_session()` 显式检查 `event.metadata.get("is_new_session_request")`
   - 为 True 时主动删除内存中的旧会话，再创建新会话

4. **~~`send_response` 为模拟实现~~ ✅ 已改为委托L1发送**
   - `send_response(event, result)` 在有 `l1_sender` 时委托给 `l1_sender.send_response()`
   - 无 `l1_sender` 时降级为 `print(...)`（开发调试）

---

## 4. 参考文档速查

| 文档 | 路径 | 用途 |
|------|------|------|
| L2 PRD | `src/l2/docs/task_plan.md` | 当前开发目标与规格 |
| 进度日志 | `src/l2/docs/progress.md` | 开发过程记录 |
| 项目规范 | `CLAUDE.md`（根目录） | 全局开发规范 |
| 接口锁定 | `docs/superpowers/specs/interfaces_lock.md` | 接口决策日志 |

---

*最后更新: 2026-04-26*
