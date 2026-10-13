# L1: User Interaction Layer - Claude Code Guide

> **Purpose:** 记录L1层的开发习惯、偏好和需要Claude Code记住的上下文。不是技术文档，是协作备忘录。

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
- 源码：`src/l1/`
- 测试：`src/l1/tests/`
- 开发文档：`src/l1/docs/`（本目录）
- 跨层集成测试：`tests/integration/`

### 2.2 提交习惯
- **更改完成后不要自动提交**，由用户自行提交
- 提交信息格式：`feat(l1): ...` / `fix(l1): ...` / `test(l1): ...`
- 完成代码/文档修改后，执行 `git diff` 或 `git status` 展示更改，等待用户确认

### 2.3 测试习惯
- 单元测试：模拟所有外部依赖
- 真实环境测试：需要 `.env` 文件中的配置
- 每个测试文件必须在 `src/l1/tests/README.md` 中登记
- 运行测试前确保conda环境已激活：`conda activate vclaw`

### 2.4 架构优先
- 先读XML规范，再写代码
- 发现代码与XML规范不一致时，先记录缺口，再制定修复计划
- 重视职责边界（如L1只管映射、L2管生命周期）

### 2.5 隐私信息
- 所有API Key、Bot Token必须放在 `.env` 文件中
- `.env` 已被 `.gitignore` 排除
- 不要硬编码任何敏感信息

---

## 3. L1层关键记忆

### 3.1 职责边界（经常混淆，需要提醒）

**L1.SessionManager vs L2.SessionManager**
- L1：只维护 `user_id → session_id` 映射（"谁是谁"），可选持久化到 L4
- L2：负责 `session_id → SessionContext` 生命周期（创建、获取、更新、过期）
- **边界**：L1 不管会话 TTL、历史记录、状态存储——此类职责属于 L2

**ErrorHandler vs ErrorTranslator**
- L3.ErrorTranslator：业务语义错误 → 转译为中文友好提示
- L1.ErrorHandler：将转译后的文本 → 格式化为渠道特定协议结构

### 3.2 Session 持久化行为（重要）

**UserInteraction 的 session 映射存储策略：**
```python
# 有 L4 memory 时：内存缓存 + L4 持久（双写双删）
# 无 L4 memory 时：纯内存（向后兼容）
```

**关键常量：**
- `PREFERENCE_KEY_ACTIVE_SESSION = "active_session_id"`

**懒加载机制：**
1. `_get_session_id()` / `get_user_session()` 先查内存 `_user_session_map`
2. 内存 miss 且 `self.memory` 存在时，调用 `load_user_preference(user_id, "active_session_id")`
3. 查到后回填内存，后续请求都命中缓存

**新建/重置会话：**
- `/new`, `/reset`, `/start`, `新会话` → 内存 `del` + L4 `save_user_preference(..., None)`（当前接口无 delete，用 save None 占位）

### 3.3 当前已知问题（开发时需关注）
1. ErrorHandler缺少业务错误格式化能力（仅实现了重试）—— **业务格式化逻辑延后到L3 ErrorTranslator完成后实现**
2. ~~SessionManager重复实现（UserInteraction和独立类两份逻辑）~~ **已修复**
3. ~~响应返回路径缺失（1.0.1删除了send_response）~~ **已修复**
4. ~~会话纯内存重启丢失~~ **已修复**（支持可选 L4 持久化）
5. **`send_response` 并发隐患**：同一 `user_id` 的并发请求会覆盖 `_response_context_map` 中的渠道上下文。当前通过显式传入 `channel`/`metadata` 兜底。**彻底解决需引入 `request_id` 全链路追踪（跨层改进，后续实施）**

**关于ErrorHandler延后原因**: L3的错误输出结构（错误码、字段、语义）尚未确定，现在写格式化逻辑只能写无意义的占位符。Phase 2先搭建`format_for_*`框架，等L3层明确错误结构后再填充具体逻辑。

**关于 `request_id` 全链路追踪**: 当前 `send_response` 用 `user_id` 作为上下文查找键，存在并发覆盖风险。长期方案是在 `StandardEvent.metadata` 中注入 `request_id`，L2/L3 透传后返回，L1 用 `request_id` 精确匹配请求-响应对。需改 L1/L2/L3 三层接口，作为后续跨层架构改进。

### 3.3 新增适配器 checklist
当用户说"新增一个XX渠道的适配器"时，需要修改：
1. `src/l1/l1_user_interaction.py` — 新增 `ProtocolAdapter` 子类
2. `EventNormalizer` — 注册新适配器
3. `DataValidator.VALID_CHANNELS` — 添加渠道名
4. `src/l1/tests/` — 添加测试
5. `src/l1/tests/README.md` — 登记新测试文件

---

## 4. 参考文档速查

| 文档 | 路径 | 用途 |
|------|------|------|
| L1 PRD | `src/l1/docs/task_plan.md` | 当前开发目标与规格 |
| 进度日志 | `src/l1/docs/progress.md` | 开发过程记录 |
| XML规范 | `docs/03_specs/L1_UserInteraction.xml` | 架构定义（只读） |
| 逐层构建设计 | `docs/superpowers/specs/2026-04-22-layer-by-layer-build-design-zh.md` | 构建方案（只读） |
| 项目规范 | `CLAUDE.md`（根目录） | 全局开发规范 |
| 接口锁定 | `docs/superpowers/specs/interfaces_lock.md` | 接口决策日志 |

---

## 5. 用户曾给出的直接反馈

> "每层开发文档以后都可以放src中的l1中的docs文件夹中"

→ 已执行：L1层文档统一放在 `src/l1/docs/`

> "progress.md文档主要用来记录开发过程...claude.md文档主要用来记录我的开发习惯...task_plan主要是当前模块的prd文档"

→ 已执行：三个文件按此分工重新组织

---

*最后更新: 2026-04-23*
