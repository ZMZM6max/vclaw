"""
VClaw Mock测试模块
==================

用于端到端测试的mock数据和工具。

目录结构:
    tests/mock/
    ├── __init__.py              # 模块导出
    ├── README.md                # 主文档
    ├── requirements.txt         # 依赖列表
    │
    ├── Core Files (核心文件)
    ├── e2e_framework.py         # 端到端测试框架
    ├── layer_prompts.py         # L1-L6提示词定义
    ├── layer_protocol.py        # 层间数据协议
    ├── test_cases.py            # 32个测试用例定义
    └── run_e2e_tests.py         # 测试主运行器
    │
    ├── docs/ (文档)
    │   ├── SETUP_GUIDE.md       # 快速设置指南
    │   ├── QUICKSTART.md        # 快速开始
    │   ├── API_CONFIG.md        # API配置说明
    │   ├── TEST_FRAMEWORK_GUIDE.md  # 测试框架使用指南
    │   └── TRANSFER_LOG.md      # 层间传输日志说明
    │
    ├── examples/ (示例)
    │   ├── config_example.py    # 配置示例
    │   ├── my_config.py         # 个人配置模板
    │   ├── run_real_llm.py      # 真实LLM运行示例
    │   └── quick_test.py        # 快速测试示例
    │
    └── results/ (测试结果 - 自动生成)
        ├── TC-01/               # 每个用例独立文件夹
        ├── TC-02/
        └── test_report.json     # 汇总报告

快速开始:
    # 列出所有测试用例
    python run_e2e_tests.py --list

    # 运行P0必过套件
    python run_e2e_tests.py --suite p0

    # 运行可自动化测试
    python run_e2e_tests.py --suite automated

    # 运行指定用例
    python run_e2e_tests.py --cases TC-01 TC-04 TC-06

使用方式:
    from tests.mock import EndToEndRunner, TestCaseGenerator
    from tests.mock.test_cases import get_test_case, P0_REQUIRED_SUITE
"""

from .e2e_framework import (
    EndToEndRunner,
    TestCaseGenerator,
    LayerExecutionResult,
    EndToEndResult,
    LayerTransferData,
    LLMClient,
    LayerSimulator,
)

from .layer_protocol import (
    LayerStatus,
    ErrorCode,
    L1Output,
    L2Output,
    L3Output,
    L5Output,
    L6Output,
    StandardEvent,
    SessionContext,
    AgentAction,
    Observation,
    ExecutionResult,
    LayerConnectionProtocol,
)

__all__ = [
    # 框架类
    "EndToEndRunner",
    "TestCaseGenerator",
    "LayerExecutionResult",
    "EndToEndResult",
    "LLMClient",
    "LayerSimulator",

    # 协议类
    "LayerStatus",
    "ErrorCode",
    "L1Output",
    "L2Output",
    "L3Output",
    "L5Output",
    "L6Output",
    "StandardEvent",
    "SessionContext",
    "AgentAction",
    "Observation",
    "ExecutionResult",
    "LayerConnectionProtocol",
]
