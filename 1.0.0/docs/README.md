# VClaw 文档中心

VClaw 项目文档分类索引。所有文档按用途分为 5 个类别。

## 📁 文档结构

```
docs/
├── 01_architecture/     # 架构设计文档（高层设计）
├── 02_guides/          # 使用指南（用户手册）
├── 03_specs/           # 技术规范（XML 规范）
├── 04_planning/        # 项目规划（开发计划）
└── 05_reports/         # 项目报告（总结报告）
```

## 📖 快速导航

### 如果你...

| 你的目的 | 推荐阅读 |
|----------|----------|
| **想了解项目架构** | [01_architecture/](01_architecture/) → `sdd.md` |
| **想快速开始使用** | [02_guides/](02_guides/) → `getting_started.md` |
| **想查看技术规范** | [03_specs/](03_specs/) → 对应层次的 XML 文件 |
| **想看开发计划** | [04_planning/](04_planning/) → `task_plan.md` |
| **想看项目总结** | [05_reports/](05_reports/) → `BUILD_SUMMARY.md` |

## 📋 文档分类说明

### 01_architecture - 架构设计
包含高层架构设计文档，适合想要了解系统整体设计的读者。

**关键文件**：
- `sdd.md` - 软件设计文档（最全面的架构说明）
- `Architecture_Overview.xml` - 架构可视化规范

### 02_guides - 使用指南
包含用户手册和开发指南，适合需要上手使用项目的读者。

**关键文件**：
- `getting_started.md` - 快速入门（安装、配置、运行）
- `tools.md` - 工具集使用指南

### 03_specs - 技术规范
包含各层的详细技术规范（XML 格式），适合需要精确接口定义的开发者。

**关键文件**：
- `L1_UserInteraction.xml` ~ `L6_RuntimeEnvironment.xml` - 六层规范
- `Integration_Tests.xml` - 集成测试规范

### 04_planning - 项目规划
包含开发计划和进度跟踪，适合想了解项目演进过程的读者。

**关键文件**：
- `ENHANCEMENT_PLAN.md` - 功能增强计划
- `progress.md` - 最新进度

### 05_reports - 项目报告
包含各类总结报告，适合想快速了解项目完成情况的读者。

**关键文件**：
- `TOOLS_INTEGRATION_REPORT.md` - 工具集成报告
- `COMPONENTS_FINAL_REPORT.md` - 组件完成报告

## 🔍 文档搜索提示

- **找架构设计**：查看 `01_architecture/` 和 `03_specs/`
- **找使用说明**：查看 `02_guides/`
- **找实现细节**：查看 `03_specs/` 的 XML 文件
- **找完成情况**：查看 `05_reports/`

## 📝 文档更新说明

- 文档按编号前缀排序，编号越小越基础
- 新文档请放入合适的分类目录
- 根目录下保留的文件（旧文档）将在下一版本中移除
