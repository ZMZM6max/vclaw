# XML 优化报告
**生成时间**: 2026-04-21T18:29:21.634216  
## 1. 执行摘要
| 指标 | 数值 |
|------|------|
| 总计用例 | 32 |
| 通过 | 4 |
| 失败 | 28 |
| 跳过 | 0 |
| 规则发现 | 12 |
| LLM 发现 | 0 |

## 2. 组件级偏差
### R1: XML 中缺失但在 Trace 中出现的组件

### R2/R3/R7: 组件状态与覆盖率偏差
- **L4** `VectorStore` (R2): Component 'VectorStore' is defined in XML but never touched in tests. It has references, so marked as Underutilized.
- **L4** `EmbeddingService` (R2): Component 'EmbeddingService' is defined in XML but never touched in tests. It has references, so marked as Underutilized.
- **L4** `TextChunker` (R2): Component 'TextChunker' is defined in XML but never touched in tests. It has references, so marked as Underutilized.
- **L4** `MemoryStore` (R2): Component 'MemoryStore' is defined in XML but never touched in tests. It has references, so marked as Underutilized.
- **L4** `IndexManager` (R2): Component 'IndexManager' is defined in XML but never touched in tests. It has references, so marked as Underutilized.
- **L4** `CacheManager` (R2): Component 'CacheManager' is defined in XML but never touched in tests. It has references, so marked as Underutilized.
- **L6** `SandboxManager` (R2): Component 'SandboxManager' is defined in XML but never touched in tests. It has references, so marked as Underutilized.
- **L6** `ResourceLimiter` (R2): Component 'ResourceLimiter' is defined in XML but never touched in tests. It has references, so marked as Underutilized.
- **L6** `CodeExecutor` (R2): Component 'CodeExecutor' is defined in XML but never touched in tests. It has references, so marked as Underutilized.
- **L6** `DockerController` (R2): Component 'DockerController' is defined in XML but never touched in tests. It has references, so marked as Underutilized.
- **L6** `SecurityEnforcer` (R2): Component 'SecurityEnforcer' is defined in XML but never touched in tests. It has references, so marked as Underutilized.
- **L6** `ExecutionLogger` (R2): Component 'ExecutionLogger' is defined in XML but never touched in tests. It has references, so marked as Underutilized.

### LLM 组件相关发现

## 3. 接口级偏差
- 未发现接口级偏差。

## 4. 数据流/规则级偏差
- 未发现明显的数据流时序偏差。

## 5. 测试覆盖率级偏差
- 未发现覆盖率异常。

## 6. 建议补丁清单
### auto_patch.patch（规则引擎生成）
```diff
# 无规则补丁

```

### llm_suggestions.patch（LLM 语义审查生成）
```diff
# No LLM suggestions generated

```
