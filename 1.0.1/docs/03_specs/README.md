# 技术规范文档

本目录包含 VClaw 项目各层的技术规范（XML 格式）。

## 文件说明

| 文件 | 说明 | 对应层次 |
|------|------|----------|
| `L1_UserInteraction.xml` | L1 用户接入层规范 | L1 |
| `L2_ControlGateway.xml` | L2 控制网关层规范 | L2 |
| `L3_Orchestration.xml` | L3 逻辑编排层规范 | L3 |
| `L4_MemoryKnowledge.xml` | L4 记忆与知识层规范 | L4 |
| `L5_ToolsCapabilities.xml` | L5 能力抽象层规范 | L5 |
| `L6_RuntimeEnvironment.xml` | L6 环境执行层规范 | L6 |
| `Integration_Tests.xml` | 集成测试规范 | - |

## XML 规范内容

每个 XML 文件包含该层的完整规范：
- **结构说明**：组件、职责、数据流
- **接口规范**：输入/输出/异常定义
- **耦合关系**：与上下层的通信方式
- **Mock 测试规范**：测试用例和 TDD 流程

## 使用建议

- **开发新功能**前，先查看对应层次的 XML 规范
- **接口设计**参考 XML 中的接口定义
- **测试编写**参考 XML 中的测试规范
