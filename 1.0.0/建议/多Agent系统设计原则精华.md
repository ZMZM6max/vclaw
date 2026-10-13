# 多Agent系统设计原则精华提炼

> 原文：建议/建议.md
> 提炼日期：2026-04-20

---

## 一、核心结论

**不要让多个AI Agent像公司部门一样分工协作（"产品经理→架构师→开发→测试"）。** 这个模式在工程上有根本性缺陷。Anthropic、OpenAI、Google 三家厂商在构建自己的Agent系统时，没有一家采用这个模式。

---

## 二、"三省六部"式架构的根本问题

### 问题1：角色扮演制造假边界

| 人类的瓶颈 | LLM的特性 |
|-----------|----------|
| 单个人注意力有限，无法同时处理所有信息 | 同一个模型既能写PRD又能写代码，没有"职业边界" |
| 人有专业壁垒，学习切换成本高 | 模型的瓶颈不是注意力广度，而是**推理深度和信息完整性** |
| 人与人之间需要接口来协调 | 模型之间没有"文化"和"默契"来补偿信息损耗 |

给Agent贴上"产品经理"的标签，不会让它更专业——但会让它**拒绝越界**。最有价值的推理往往发生在边界上，而流水线模式在系统层面封死了这个可能性。

### 问题2：信息在流转中死亡

Agent A产出文档传给Agent B，传递的是**结论，不是推理过程**。原始意图在衰减，隐含假设在丢失，每次传递都在累积误差。工作流越长，最终输出越"局部正确但整体漂移"。

**关键区别**：
- **三省六部**：角色间单向交接，信息被压缩成结论，接棒就是断点
- **厂商方案**：同一任务的增量日志，执行主体在每个checkpoint往同一份记录追加，下一个session读取的是**完整历史**

---

## 三、三大厂商的实际做法

### Anthropic：Context Engineering + 显式状态文件

- **核心理念**：把"Prompt Engineering"升级成"Context Engineering"——问题不是怎么写好一个prompt，而是什么样的token配置最能产生想要的行为
- **claude-progress.txt**：跨session工作日志，Agent在每个session结束时更新，下一个session开始时读取
- **Git history**：作为状态锚点，记录每一个增量变化
- **Initializer Agent**：只在第一个session运行，建立环境、展开feature list、写好runbook
- **多Agent架构**：orchestrator-worker——一个lead agent分解任务、协调subagent并行探索不同方向，结果**回流**给lead agent综合
- **关键发现**：token消耗量本身解释了80%的性能差异——多Agent的价值不是"分工"，而是**用更多token覆盖更大的搜索空间**

### OpenAI：Compaction + Skills + 结构化Spec文件

- **长任务原则**：在任务开始时就为continuity做规划
- **Spec文件**：冻结目标，防止agent"做出了很impressive但方向错误的东西"
- **Runbook**：告诉agent如何操作，同时也是共享记忆和审计日志
- **Server-side compaction**：作为默认primitive，不是紧急fallback
- **Skills**：可复用的、版本化的指令集——这不是"角色"，是**工具和操作规程**

### Google：1M上下文 + Context-driven Development

- **硬扩窗口**：Gemini的1M token context让RAG切片、丢弃旧消息等技术可以被"直接放进去"取代
- **Conductor扩展**：把项目意图从聊天窗口移出来，放进代码库里的持久化Markdown文件
- **哲学**："不依赖不稳定的聊天记录，依赖正式的spec和plan文件"
- **Thought Signatures**：在长session里保存推理链的关键节点，防止reasoning drift

---

## 四、真正的架构原则

### 原则1：推理链不能断，只能分叉再合并

多Agent的正确用法不是流水线，而是一个**主agent持有完整意图**，子调用是为了深挖某个子问题，结果**回流给主agent**，不是传给下一个agent。

### 原则2：显式外部状态，不靠模型记住

推理链的关键节点必须**外化到持久存储**（progress.txt、git history、spec文件、数据库），而不依赖模型在context window里"记住"。

### 原则3：多Agent的价值是并行覆盖，不是分工

多Agent适合**breadth-first**类任务（同时探索多个独立方向），不适合需要连续推理、深度依赖上下文的场景。

| 三省六部 | Anthropic orchestrator-worker |
|---------|------------------------------|
| 职能性分工：不同角色承担不同工种 | 功能性并行：多个相同性质的agent同时搜索不同方向 |
| PM做完传给Dev，Dev做完传给QA | 没有"下一棒"，结果全部汇聚回同一个orchestrator |
| **接力赛** | **同时撒网捞鱼** |

### 原则4：验证Agent是否定者，不是接棒者

如果要用多Agent做质量控制，正确的设计是让一个Agent**专门找另一个Agent的问题**，而不是"传递工作成果"。**对抗性检验**，不是流水线传递。

### 原则5：工具是工具，不是角色

给Agent配什么工具（bash、文件读写、搜索、代码执行）远比给它贴什么标签重要。工具决定了Agent能做什么；角色标签只是约束它**愿意**做什么。

---

## 五、实践建议

### 1. 根据信息依赖结构选择模式

不要问"我需要几个Agent"，要问"这个任务的信息依赖结构是什么"。

| 任务类型 | 推荐模式 | 原因 |
|---------|---------|------|
| 连续推理、上下文高度依赖（写复杂设计文档） | **单Agent + 好的context engineering** | 避免信息损耗 |
| 同时探索多个独立方向（研究10个竞品） | **多Agent并行** | 信息损耗代价最小，token覆盖更大搜索空间 |

### 2. 跨session状态文件是必须的

一份有效的状态文件应该包含**四类信息**：

1. **任务目标**（不变，session开始时读取，防止漂移）
2. **已完成的步骤**（追加，不覆盖，保留完整历史）
3. **当前状态**（覆盖，反映最新进展）
4. **已知的坑**（追加，避免下一个session重复踩）

### 3. 验证环节用对抗性检验

让验证Agent的唯一任务是**找问题**，不是"接棒继续做"。

### 4. 保持架构的可演化性

模型能力在快速提升，今天harness里需要的workaround，六个月后可能变成死重量。Anthropic已经验证了这一点——Sonnet 4.5的context anxiety在Opus 4.5里消失了，为它设计的context reset随即变成了无用代码。

**保持架构的可演化性，比选一个"完美架构"更重要。**

---

## 六、一句话总结

> **最好的多Agent系统，不像公司。它更像一个思考者的多次草稿——同一个大脑，在不同维度上展开推理，最终合并成一个连贯的结论。**

三省六部是一个让人感觉良好但工程上代价高昂的错觉。它的真正成本不是直接的失败，而是让你的系统在复杂度上升时，以一种难以诊断的方式退化——每个节点都"看起来在工作"，但整体在漂移。

---

## 参考来源

- Anthropic Engineering Blog（Building Effective Agents, Effective Context Engineering, Multi-Agent Research System, Effective Harnesses for Long-Running Agents, Managed Agents）
- OpenAI Developers Blog（Run Long Horizon Tasks with Codex, Shell + Skills + Compaction）
- Google Developers Blog（Architecting Efficient Context-Aware Multi-Agent Framework, Conductor: Context-Driven Development for Gemini CLI）
