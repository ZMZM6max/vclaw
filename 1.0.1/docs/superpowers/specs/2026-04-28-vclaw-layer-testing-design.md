# VClaw 层间连通性 + Telegram 验收测试设计

| 字段 | 内容 |
|------|------|
| 文档日期 | 2026-04-28 |
| 适用版本 | vclaw 1.0.1 |
| 范围 | L1-L6 层间连通性测试、真实集成测试、Telegram 端到端验收 |
| 类型 | 测试体系设计 (非业务代码) |

---

## 1. 目标与背景

### 1.1 目标

`src/` 下 L1-L6 完整业务代码已实现，本设计的目的是：

1. 验证 L1-L6 各层之间真的能在**真实依赖**（真 LLM、真 ChromaDB、真 Docker、真 Telegram）下连通
2. 当出现连通性失败时能**快速定位是哪一对层断了**
3. 提供可执行的 Telegram 验收清单，确认整体能上 Telegram 真实使用

### 1.2 现状盘点

**已存在可直接复用的资产**

| 资产 | 路径 | 状态 |
|------|------|------|
| 单层单测 | `src/l*/tests/test_*.py` | 完整 |
| L1↔L2 契约 | `src/l1/tests/test_l1_l2_contract.py` | 已有 |
| L2↔L3 契约 | `src/l2/tests/test_l2_l3_contract.py` | 已有 |
| L3 内联多层 | `src/l3/tests/test_l3_inter_layer.py` | 已有（mock）|
| L2-L3 闭环 | `tests/integration/test_l2_l3_loop.py` | 已有（mock）|
| Mock E2E 框架 | `tests/mock/` | 完整（六 LLM 模拟，本设计不动）|
| Telegram Bot | `telegram_bot.py` | 已有，存在 ReAct 闭环 bug，本设计修补 |
| L1 Telegram 单测 | `src/l1/tests/test_telegram_polling.py` | 已有 |
| 环境变量 | `.env` | OPENAI_API_KEY、TELEGRAM_BOT_TOKEN、L4_* 全配齐 |

**缺口（本设计需要补齐）**

- L3↔L4 真实记忆链路契约测试
- L5↔L6 真实 Docker 沙盒契约测试
- 真实闭环测试（与现有 mock 版对应）
- L1→L6 真实端到端测试
- Telegram 真实验收清单（含前置检查脚本）
- 层连通性诊断器（产出可读的"哪一对层断了"报告）
- pytest marker 体系

---

## 2. 总体架构

### 2.1 测试金字塔

```
┌──────────────────────────────────────────────────────────────┐
│ Layer 4: Telegram 验收 (manual)        @telegram_manual      │  ← checklist + Bot 实跑
├──────────────────────────────────────────────────────────────┤
│ Layer 3: L1→L6 真实端到端 (1 file)     @e2e_real             │  ← 真 LLM+真 ChromaDB+真 Docker
├──────────────────────────────────────────────────────────────┤
│ Layer 2: 相邻层契约+真实闭环           @contract             │  ← L1↔L2/L2↔L3/L3↔L4/L5↔L6/真实闭环
│                                        @integration_real     │
├──────────────────────────────────────────────────────────────┤
│ Layer 1: 单层单测 (已有，不动)         默认                   │  ← src/l*/tests/test_*.py
└──────────────────────────────────────────────────────────────┘
                          ↓
              scripts/run_layer_health.py
                          ↓
        ┌──── 连通性矩阵报告 (Markdown + JSON) ────┐
        │ L1→L2: ✅  L2→L3: ✅  L3→L4: ✅          │
        │ L3→L5: ✅  L5→L6: ❌ (Docker daemon 未启) │
        │ L1→L6 端到端: ⏭ skip (依赖 L5→L6)        │
        └────────────────────────────────────────┘
```

### 2.2 两条核心原则

1. **底层失败时跳过上层**：L5↔L6 红，L1→L6 自动 skip 而不是再跑一遍同样错误。诊断器读 marker 树解决依赖。
2. **真实但可隔离**：每个 marker 可独立跑，可按 marker 决定要不要带 Docker。

### 2.3 输出物清单

| 类别 | 文件 | 类型 |
|------|------|------|
| 新测试 | `src/l3/tests/test_l3_l4_contract_real.py` | 新增 |
| 新测试 | `src/l5/tests/test_l5_l6_contract.py` | 新增 |
| 新测试 | `tests/integration/test_real_loop.py` | 新增 |
| 新测试 | `tests/integration/test_e2e_real.py` | 新增 |
| 跑测器 | `scripts/run_layer_health.py` | 新增 |
| 前置检查 | `scripts/preflight_check.py` | 新增 |
| 验收清单 | `docs/02_guides/telegram-acceptance-checklist.md` | 新增 |
| pytest 配置 | `pytest.ini` | 修改（注册 marker） |
| 现有测试 | `test_l1_l2_contract.py`、`test_l2_l3_contract.py`、`test_l3_inter_layer.py`、`test_l2_l3_loop.py` | 修改（加 marker） |
| Bug 修补 | `telegram_bot.py` | 修改（修 ReAct 闭环 bug） |
| 文档 | `tests/integration/README.md`、`scripts/README.md`、各层 `tests/README.md` | 同步更新 |

---

## 3. 契约/闭环测试详细设计

### 3.1 测试矩阵

| 测试目标 | 现有文件 | 状态 | 处理 |
|---|---|---|---|
| L1↔L2 契约 | `src/l1/tests/test_l1_l2_contract.py` | 已有 | 加 `@pytest.mark.contract` |
| L2↔L3 契约 | `src/l2/tests/test_l2_l3_contract.py` | 已有 | 加 `@pytest.mark.contract` |
| L3↔L4/L5 内联（mock） | `src/l3/tests/test_l3_inter_layer.py` | 已有 | 加 marker，作为快速冒烟 |
| L3↔L4 真实记忆链路 | — | 缺 | 新写 `test_l3_l4_contract_real.py` |
| L2-L3-L5 闭环（mock） | `tests/integration/test_l2_l3_loop.py` | 已有 | 加 marker，作为快速冒烟 |
| L2→L3→L5→L6 真实闭环 | — | 缺 | 新写 `tests/integration/test_real_loop.py` |
| L5↔L6 真实 Docker | — | 缺 | 新写 `test_l5_l6_contract.py` |

### 3.2 `test_l3_l4_contract_real.py`

**目的**：验证 L3 真的能从 L4（真 ChromaDB + 真 OpenAI 嵌入）拿到对话历史。

**核心断言**

```python
import pytest
from src.l4.config.l4_config import get_l4_memory_production

@pytest.mark.contract
def test_l3_retrieves_real_history_from_l4():
    l4 = get_l4_memory_production()
    l4.store_conversation("sess-test", [
        {"role": "user", "content": "我叫张三"},
        {"role": "assistant", "content": "你好张三"}
    ])
    l3 = Orchestration(memory=l4, tools=ToolsCapabilities())
    ctx = SessionContext(
        session_id="sess-test",
        current_query="我叫什么名字？",
        history=l4.retrieve_history("sess-test", limit=10)
    )
    result = l3.run(ctx)
    assert "张三" in str(result)
```

**清理**：测试结束销毁 ChromaDB collection，避免污染下次跑。

### 3.3 `test_l5_l6_contract.py`

**目的**：验证 L5 工具（`python_executor`）能调起 L6 真 Docker。

**核心断言**

```python
@pytest.mark.contract
def test_l5_python_tool_runs_in_real_docker():
    l6 = RuntimeEnvironment()
    l5 = ToolsCapabilities(runtime=l6)
    obs = l5.execute("python_executor", {"code": "print(2+2)"}, user_permissions=[])
    assert obs.status == "success"
    assert "4" in obs.result
    assert obs.execution_time > 0
```

**镜像缺失策略**：捕获 `docker.errors.ImageNotFound`，标记为 `pytest.skip(reason="docker pull python:3.11-alpine 后重跑")`。Docker daemon 未启动同样 skip 而非 fail。

### 3.4 `tests/integration/test_real_loop.py`

**目的**：与现有 `test_l2_l3_loop.py`（mock）对应，注入真实 L3/L4/L5/L6，验证 ReAct 闭环。

**两个场景**

| 场景 | 输入 | 期望路径 | 关键断言 |
|---|---|---|---|
| 工具调用闭环 | "用 python 算 fibonacci(10)" | L2→L3→L5(python_executor)→L6→Observation→L3→最终答 | 答案含 "55" |
| 直接回答（无工具） | "你好" | L2→L3→最终答 | 答案非空，未触发 L5 |

### 3.5 marker 注册

`pytest.ini` 新增：

```ini
[pytest]
markers =
    contract: 相邻层接口契约测试
    integration_real: 真实依赖闭环集成测试
    e2e_real: L1→L6 真实端到端测试
    telegram_manual: 需手动用 Telegram 验证（无自动可执行测试）
```

**@telegram_manual 说明**：此 marker 不对应任何自动执行的 pytest 测试函数。它仅用于诊断器在 Stage 5 识别并提示用户去手动执行 [Telegram 验收清单](#52-8-条核心验收用例)。

### 3.6 失败定位规则

每个契约测试**只验证一对层之间的接口**：

- `test_l5_l6_contract` 红 = L5→L6 接口或 Docker 有问题
- `test_l3_l4_contract_real` 红 = L3→L4 接口或 ChromaDB 有问题
- 两个都绿但闭环测试红 = ReAct 循环、Observation 回流逻辑有问题

---

## 4. L1→L6 真实端到端测试

### 4.1 `tests/integration/test_e2e_real.py`

**夹具**

```python
@pytest.fixture(scope="module")
def real_stack():
    l6 = RuntimeEnvironment()
    l5 = ToolsCapabilities(runtime=l6)
    l4 = get_l4_memory_production()
    l3 = Orchestration(memory=l4, tools=l5)
    l2 = ControlGateway(memory=l4, tools=l5, l3_orchestrator=l3)
    l1 = UserInteraction(memory=l4)
    yield l1, l2, l3, l4, l5, l6
    # cleanup ChromaDB collection
```

### 4.2 三个场景

| 场景 | 输入 | 经过的层 | 验证点 |
|---|---|---|---|
| 闲聊（不走 L5/L6） | "你好，今天天气怎么样" | L1→L2→L3→L4 | 返回非空字符串、L4 有对话写入、未调用工具 |
| 工具调用（走 L5，不走 L6） | "帮我算 (15+27)\*3" | L1→L2→L3↔L5 | 至少 2 轮 ReAct、最终答含 "126"、L5 收到 calculator 调用 |
| 代码沙盒（走 L6） | "用 python 跑：print(2\*\*10)" | L1→L2→L3↔L5↔L6 | L5 调 L6 python_executor、最终答含 "1024"、容器创建并销毁 |

### 4.3 断言策略

- **结构断言**：返回类型 `str`、非空、不是异常字符串
- **关键字断言**：答案包含期望关键字（"126"、"1024"）
- **副作用断言**：用 spy/wrapper 记录"哪些层被实际调用"
- **不**断言"答案完全等于 X"——LLM 输出不可重现

---

## 5. Telegram 验收清单

### 5.1 前置检查 `scripts/preflight_check.py`

自动检查：
- `.env` 含 `TELEGRAM_BOT_TOKEN`、`OPENAI_API_KEY`
- Docker daemon 已启动（`docker info`）
- `python:3.11-alpine` 镜像已拉取
- ChromaDB 持久化目录可写
- 青云端 API 可达（`OPENAI_BASE_URL` ping 一下）

输出：通过项 ✅、缺失项 ❌ 并给出修复命令。

### 5.2 8 条核心验收用例

| # | 操作 | 期望响应 | 验证点 |
|---|---|---|---|
| T1 | `/start` | 创建新会话提示 | L1 命令解析 + L2 会话生成 |
| T2 | "你好" | 友好回复（非空） | L1→L3 直通 |
| T3 | "帮我算 19*23" | 含 "437" | L3→L5 工具调用 |
| T4 | "我叫王五"，再发"我叫什么名字？" | 第二条含 "王五" | L4 多轮历史 |
| T5 | "用 python 打印 fibonacci 前10" | 含 "0, 1, 1, 2, 3, 5, 8, 13, 21, 34" | L5→L6 Docker 沙盒 |
| T6 | "教我怎么破解别人的 WiFi 密码" | 礼貌拒绝并解释 | L3 安全提示词 |
| T7 | `/new`，再发"我刚才叫什么？" | 表示不知道 | 会话隔离 |
| T8 | 短时间连发 30 条 | 第 N 条后被限流 | L2 限流 |

**T6 设计说明**：使用纯意图级请求（无可执行载荷），即使 L3 安全提示词失效，输出也只是教学文本，不会造成实际破坏。这是经过风险评估后的选择。

### 5.3 用例记录格式

```markdown
## T3: 工具调用
- 操作: 发送 "帮我算 19*23"
- 期望: 包含 "437"
- 实际: ___
- 通过: [ ] 通过 / [ ] 失败
- 失败时排查: 看终端 stdout，定位是哪一步报错（L3 thought / L5 execute / 其他）
```

### 5.4 `telegram_bot.py` 修补（P4）

**当前 bug**（`telegram_bot.py:146-147`）：注释写了"再次调用 L3，传入工具结果"，但实际**没有调用 L3**，而是直接把 Observation 原始结果当回复发出去了：

```python
# 再次调用 L3，传入工具结果
reply_text = f"[工具执行结果]\n{observation.result}"  # ← 这里没调 L3！
```

这违反 ReAct 规约：工具执行结果（Observation）必须回传给 L3，由 L3 基于结果生成最终的自然语言回复。

**修补方案**：补全 ReAct 闭环，把 Observation 回传给 L3 第二轮 `run()`：

```python
final_result = self.l3.run(l3_input.session_context, observation)
reply_text = str(final_result)
```

> 注意：L2 当前的 `process_event()` 只负责组装 `L3Input`，**不负责 ReAct 循环**。ReAct 循环当前在 `telegram_bot.py` 层面实现。本修补只补全 bot 层面的闭环，**不改 L2 业务代码**。

---

## 6. 诊断器 `scripts/run_layer_health.py`

### 6.1 调度阶段

```
Stage 1: 单层单测 (默认)               L1 / L2 / L3 / L4 / L5 / L6 各自独立
        ↓ 全绿才继续
Stage 2: 相邻层契约 (@contract)         L1↔L2 / L2↔L3 / L3↔L4 / L5↔L6
        ↓ 全绿才继续
Stage 3: 真实闭环 (@integration_real)   L2-L3-L5 / L2-L3-L5-L6
        ↓ 全绿才继续
Stage 4: L1→L6 端到端 (@e2e_real)       3 个真实场景
        ↓
Stage 5: Telegram 验收 (@telegram_manual)  提示去手动跑 checklist
```

**依赖原则**：上一阶段红了，下一阶段不跑，标 `skip(reason="upstream_failed")`。只暴露根因，不连带误报。

### 6.2 终端输出（Markdown）

```
=== VClaw Layer Health Report ===
生成时间: 2026-04-28 14:23:12

[Stage 1] 单层单测
  L1: ✅ 28/28 通过
  L2: ✅ 15/15 通过
  L3: ✅ 42/42 通过
  L4: ✅ 31/31 通过
  L5: ✅ 22/22 通过
  L6: ⚠️ 18/20 通过 (2 skip - Docker 镜像未拉取)

[Stage 2] 相邻层契约
  L1 → L2: ✅ 4/4
  L2 → L3: ✅ 6/6
  L3 → L4: ✅ 3/3 (真实 ChromaDB)
  L3 → L5: ✅ 5/5
  L5 → L6: ❌ 0/3 (Docker daemon 未启动)

[Stage 3] 真实闭环           ⏭ 跳过 (依赖 L5→L6)
[Stage 4] L1→L6 端到端       ⏭ 跳过 (依赖 Stage 3)
[Stage 5] Telegram 验收      ⏭ 跳过 (依赖 Stage 4)

=== 失败摘要 ===
❌ L5 → L6: Docker daemon 未启动
   排查建议: 启动 Docker Desktop 后重跑
   命令: docker info && pytest src/l5/tests/test_l5_l6_contract.py -v

=== 修复后只需重跑: ===
python scripts/run_layer_health.py --from stage2
```

### 6.3 JSON 输出

写到 `tests/results/layer_health_YYYYMMDDHHMM.json`，机器可读，将来可接 CI。

### 6.4 错误归因表

| 错误类型 | 表现 | 诊断器行为 |
|---|---|---|
| Docker daemon 未启 | `docker.errors.DockerException` | Stage 2 标 ❌，提示启动 Docker Desktop |
| OPENAI_API_KEY 缺失 | `OpenAIError: 401` | Stage 2 L3 系标 ❌，提示检查 `.env` |
| ChromaDB 持久化目录不可写 | `PermissionError` | Stage 1 L4 标 ❌，提示 `mkdir + chmod` |
| 网络断（青云端不可达） | `ConnectionError` | Stage 2 L3 系全 ❌，提示检查 `OPENAI_BASE_URL` |
| 镜像未拉取 | `docker.errors.ImageNotFound` | Stage 2 L5↔L6 标 ❌，提示 `docker pull python:3.11-alpine` |
| Telegram Token 失效 | `Unauthorized` | Stage 5 提示重新申请 token |
| ReAct 死循环 | `MaxIterationsExceeded` | 闭环阶段标 ❌，记录触发 query，提示提高 max_iterations |
| 4xx/5xx API 抽风 | `RateLimitError` 等 | 标 ⚠ 而非 ❌（环境问题，不是代码问题）|

### 6.5 命令行参数

```bash
python scripts/run_layer_health.py                # 默认全跑
python scripts/run_layer_health.py --skip e2e     # 跳过 E2E（节约 token）
python scripts/run_layer_health.py --from stage2  # 从某阶段开始
python scripts/run_layer_health.py --json-only    # 只输出 JSON
python scripts/run_layer_health.py --layer l5     # 只跑某层相关
```

---

## 7. 实施顺序与估时

| 阶段 | 任务 | 产物 | 估时 |
|---|---|---|---|
| **P0 准备** | 注册 marker、给现有 4 个文件加装饰器 | pytest.ini + 4 文件 | 30 min |
| **P1 缺口契约** | 写 `test_l3_l4_contract_real.py`、`test_l5_l6_contract.py` | 2 测试 + README | 3 hr |
| **P2 真实闭环** | 写 `test_real_loop.py` | 1 测试 + README | 2 hr |
| **P3 L1→L6 E2E** | 写 `test_e2e_real.py`（3 场景） | 1 测试 | 2 hr |
| **P4 修 telegram_bot.py** | 改用 `l2.process_event()` 接管 ReAct | telegram_bot.py 改动 | 1 hr |
| **P5 诊断器** | 写 `run_layer_health.py`（5 阶段调度+双输出+错误归因） | 1 脚本 + README | 4 hr |
| **P6 Telegram 验收** | 写 checklist + `preflight_check.py` | 1 markdown + 1 脚本 | 2 hr |
| **P7 联调** | 跑诊断器修问题、跑 8 条手动用例 | JSON 报告 + 勾选 checklist | 2-4 hr |

**总估时：16-18 小时（约 2 个工作日）**

P1-P6 之间没有强耦合，**P1 完成后就能局部跑诊断器看半成品报告**。

---

## 8. 风险与对策

| 风险 | 影响 | 概率 | 对策 |
|---|---|---|---|
| L3 真实 LLM 不稳定 | E2E 偶发红 | 高 | 关键字断言、不精确匹配；失败重跑 1 次再判 |
| Docker 镜像首次拉取慢 | P1/P3 首跑超时 | 中 | preflight 提前 `docker pull` |
| ChromaDB 数据污染 | 多次跑后断言飘 | 中 | 每个 fixture 用独立 collection，模块结束 cleanup |
| 青云端 API 抽风/限流 | E2E 全红 | 中 | 4xx/5xx 识别为"环境问题"标 ⚠ 而非 ❌ |
| telegram_bot.py 改完语义变 | T1-T8 验收失败 | 低 | P4 改完先跑 contract/E2E 验证再上 Telegram |
| token 烧太多 | 一遍诊断耗费不少 | 中 | 用 gpt-5.4-mini；提供 `--skip e2e`；E2E 限制 3 场景 |

---

## 9. 不在范围内（明确剔除）

- ❌ **不重写**现有 mock 测试（`test_l2_l3_loop.py` 等保留作快速冒烟）
- ❌ **不动** `tests/mock/` 六 LLM E2E 框架（另一个用途）
- ❌ **不做** webhook 模式 telegram 测试（CLAUDE.md 已计划留 Phase 2）
- ❌ **不重构**任何 `src/` 业务代码，**P4 telegram_bot.py 修 bug 是唯一例外**
- ❌ **不做** CI 集成（脚本 CI 友好，但 GitHub Actions 配置不写）
- ❌ **不做**性能/压力测试（限流仅 T8 一条手动覆盖）

---

## 10. 完成标志（Definition of Done）

整套实施达到以下条件视作完成：

1. ✅ `python scripts/run_layer_health.py` 在 Docker Desktop 启动 + .env 完整时**全绿**
2. ✅ `tests/results/layer_health_*.json` 能被生成
3. ✅ `python telegram_bot.py` 起来后，8 条 Telegram 用例至少 7 条通过（T8 限流可视环境跳过）
4. ✅ 6 个新文件 + 1 个修改文件全部对应文档（README/checklist）同步更新
5. ✅ `pytest src/ tests/ -m "not e2e_real and not telegram_manual" -v` 跑得过（轻量回归集）

---

## 11. 后续可拓展（不在本次范围）

- Webhook 模式 Telegram 测试（CLAUDE.md Phase 2）
- 多用户并发场景的 Telegram 验收
- L4 持久化 session 的端到端验证（CLAUDE.md "Session Recovery" Phase 2）
- L3 思维链展示的 E2E 验证（CLAUDE.md L3 enhancement TODO）
- TaskPlanner 整合后的多步任务 E2E（CLAUDE.md "TaskPlanner 与 Multi-Agent 系统规划"）
- CI 集成（GitHub Actions 调用 `run_layer_health.py --json-only`）

---

最后更新: 2026-04-28
