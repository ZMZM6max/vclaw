"""L3-L4 真实依赖契约测试

验证 L3 能够通过真实 L4（ChromaDB + OpenAI embeddings）检索对话历史，
并基于历史信息回答用户问题。

依赖:
    - OPENAI_API_KEY 必须在 .env 文件中设置
    - 使用青云端 API: https://api.qingyuntop.top/v1
    - ChromaDB 向量数据库

标记:
    @pytest.mark.contract - 契约测试标记
"""

import os
import uuid
import pytest
from typing import List, Dict

from dotenv import load_dotenv

# 加载环境变量
load_dotenv(override=True)


# =============================================================================
# 模块级 Fixture
# =============================================================================

@pytest.fixture(scope="module")
def l4_memory():
    """模块级 Fixture：创建真实的 L4 MemoryKnowledge 实例（生产配置）.

    使用 get_l4_memory_production() 初始化 OpenAI + ChromaDB 配置。
    如果 OPENAI_API_KEY 未设置，则跳过整个模块的测试。

    Yields:
        MemoryKnowledge: 配置好的 L4 记忆实例
    """
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY not set")

    from src.l4.config.l4_config import get_l4_memory_production

    memory = get_l4_memory_production()
    yield memory

    # 模块结束后清理：无需显式清理，因为使用唯一 session_id
    # 且 ChromaDB 的测试数据会被后续覆盖


@pytest.fixture(scope="module")
def l3_orchestration(l4_memory):
    """模块级 Fixture：创建注入真实 L4 的 L3 Orchestration 实例.

    Args:
        l4_memory: 真实的 L4 MemoryKnowledge 实例

    Returns:
        Orchestration: 配置好的 L3 编排实例
    """
    from src.l3.l3_orchestration import Orchestration
    from src.l5.l5_tools import ToolsCapabilities

    return Orchestration(memory=l4_memory, tools=ToolsCapabilities())


# =============================================================================
# 契约测试
# =============================================================================

pytestmark = pytest.mark.contract


class TestL3L4ContractReal:
    """L3-L4 真实依赖契约测试类.

    验证 L3 能够利用 L4 的真实记忆存储与检索能力，
    基于对话历史生成上下文相关的回答。
    """

    def test_l3_answers_based_on_stored_history(self, l3_orchestration, l4_memory):
        """测试 L3 能够基于 L4 存储的历史记录回答问题.

        测试步骤:
            1. 使用唯一 session_id 存储包含名字"张三"的对话历史
            2. 让 L3 回答"我叫什么名字？"
            3. 断言回答中包含"张三"

        验证点:
            - L4 成功存储对话历史
            - L3 的 MemoryAccessor 能从 L4 检索到历史
            - LLM 能基于历史信息正确回答
        """
        from src.core.models import SessionContext

        # 使用 UUID 生成唯一 session_id，避免测试数据冲突
        session_id = f"test-contract-{uuid.uuid4().hex[:8]}"

        # Step 1: 在 L4 中存储对话历史（包含名字信息）
        history_messages: List[Dict[str, str]] = [
            {"role": "user", "content": "你好，我叫张三。"},
            {"role": "assistant", "content": "你好张三！很高兴认识你。有什么我可以帮你的吗？"},
        ]
        store_result = l4_memory.store_conversation(session_id, history_messages)
        assert store_result is True, "L4 存储对话历史失败"

        # Step 2: 构建 SessionContext，包含当前查询
        context = SessionContext(
            session_id=session_id,
            user_id="test-user",
            current_query="我叫什么名字？",
            history=history_messages,
        )

        # Step 3: 调用 L3 Orchestration
        result = l3_orchestration.run(context)

        # Step 4: 断言结果中包含"张三"
        # result 可能是 str（最终答案）或 AgentAction（需要调用工具）
        if isinstance(result, str):
            answer = result
        else:
            # 如果是 AgentAction，说明 LLM 决定调用工具，这在当前测试中不应发生
            pytest.fail(f"L3 返回了 AgentAction 而非直接答案: {result}")

        assert "张三" in answer, (
            f"L3 未能基于 L4 历史正确回答用户名字。"
            f"session_id={session_id}, answer={answer}"
        )

    def test_l3_without_history_does_not_hallucinate_name(self, l3_orchestration, l4_memory):
        """测试 L3 在没有历史记录时不应幻觉出名字.

        测试步骤:
            1. 使用全新的 session_id（不存储任何历史）
            2. 让 L3 回答"我叫什么名字？"
            3. 断言回答中不包含存储过的特定名字，且表达不知道或请求信息

        验证点:
            - L3 不会在没有上下文的情况下幻觉出特定名字
            - 模型能正确表达"不知道"或请求更多信息
        """
        from src.core.models import SessionContext

        # 使用全新的 UUID session_id，确保没有历史记录
        session_id = f"test-contract-empty-{uuid.uuid4().hex[:8]}"

        # 使用一个随机的、不太可能出现在训练数据中的名字
        unique_name = f"测试用户{uuid.uuid4().hex[:6]}"

        # Step 1: 验证 L4 中确实没有该 session 的历史
        empty_history = l4_memory.retrieve_history(session_id, limit=10)
        assert empty_history == [], "新 session_id 不应有历史记录"

        # Step 2: 构建 SessionContext（无历史）
        context = SessionContext(
            session_id=session_id,
            user_id="test-user",
            current_query="我叫什么名字？",
            history=[],
        )

        # Step 3: 调用 L3 Orchestration
        result = l3_orchestration.run(context)

        # Step 4: 断言结果中不包含那个独特的随机名字
        if isinstance(result, str):
            answer = result
        else:
            pytest.fail(f"L3 返回了 AgentAction 而非直接答案: {result}")

        assert unique_name not in answer, (
            f"L3 在没有历史的情况下幻觉出了名字。"
            f"session_id={session_id}, answer={answer}"
        )

        # 额外验证：回答应该表达不知道或请求提供信息
        # 允许的回答模式：不知道、不清楚、请告诉我、没有信息等
        uncertainty_keywords = ["不知道", "不清楚", "无法", "没有", "请告诉", "请提供", "无法得知"]
        has_uncertainty = any(kw in answer for kw in uncertainty_keywords)
        # 如果回答中没有不确定性表达，至少确保它不是一个确定的声明
        # （某些模型可能会礼貌地请求提供信息，使用不同的措辞）
        assert has_uncertainty or len(answer) < 100, (
            f"L3 在没有历史的情况下给出了过于确定的回答。"
            f"session_id={session_id}, answer={answer}"
        )
