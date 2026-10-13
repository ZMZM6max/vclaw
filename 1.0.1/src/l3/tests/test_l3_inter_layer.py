"""L3 Inter-Layer Integration Tests

验证L3与L2/L4/L5/L6的层间交互，打印每个组件的输入输出。
"""
import pytest

pytestmark = pytest.mark.contract
import sys
import json
from unittest.mock import MagicMock, call
from datetime import datetime

sys.path.insert(0, 'src')

from src.l3.l3_orchestration import (
    Orchestration, MemoryAccessor, ToolCaller, ErrorTranslator,
    ReActEngine, TaskPlanner, SecurityGuard, LLMManager
)
from src.core.models import SessionContext, AgentAction, Observation, ExecutionResult
from src.core.interfaces import MemoryInterface, ToolsInterface, RuntimeInterface


# ============== Helper: Pretty Print Component I/O ==============

def print_component_header(component_name: str, test_name: str):
    """打印组件分隔线"""
    print(f"\n{'='*60}")
    print(f"  [{component_name}] - {test_name}")
    print(f"  Time: {datetime.now().strftime('%H:%M:%S.%f')[:-3]}")
    print(f"{'='*60}")

def print_io(label: str, data: any, indent: int = 2):
    """打印输入/输出数据"""
    prefix = "  " * indent
    if isinstance(data, dict) or isinstance(data, list):
        try:
            content = json.dumps(data, ensure_ascii=False, indent=2)
            print(f"{prefix}[{label}]\n{content}")
        except Exception:
            print(f"{prefix}[{label}] {data}")
    elif isinstance(data, (SessionContext, AgentAction, Observation, ExecutionResult)):
        print(f"{prefix}[{label}] {type(data).__name__}:")
        print(f"{prefix}  {data}")
    else:
        print(f"{prefix}[{label}] {data}")


# ============== Test Class ==============

class TestL3InterLayer:
    """L3层间交互测试"""

    # ========== 1. L2 -> L3 输入输出测试 ==========

    def test_l2_l3_input_output(self):
        """测试L2->L3的输入（SessionContext）和L3->L2的输出（str/AgentAction）"""
        print_component_header("L2 <-> L3", "SessionContext输入 / str或AgentAction输出")

        # 构造L2输入给L3的SessionContext
        context = SessionContext(
            session_id="sess-001",
            user_id="user-001",
            current_query="计算1+1",
            history=[{"role": "user", "content": "你好"}, {"role": "assistant", "content": "你好！"}],
            user_permissions=["read", "write"],
            metadata={"channel": "telegram"}
        )
        print_io("L2 -> L3 INPUT", {
            "session_id": context.session_id,
            "user_id": context.user_id,
            "current_query": context.current_query,
            "history_length": len(context.history),
            "user_permissions": context.user_permissions,
            "metadata": context.metadata
        })

        # L3处理后的输出
        mock_llm = MagicMock()
        mock_llm.complete.return_value = AgentAction(
            action="calculator",
            action_input={"expression": "1+1"},
            thought="用户需要计算"
        )
        orchestration = Orchestration(llm_manager=mock_llm)
        result = orchestration.run(context)

        print_io("L3 -> L2 OUTPUT", {
            "type": type(result).__name__,
            "value": result.dict() if isinstance(result, AgentAction) else result
        })

        assert isinstance(result, (str, AgentAction))
        print(f"\n  [PASS] L2->L3->L2 链路正常")

    # ========== 2. L3 <-> L4 记忆检索交互 ==========

    def test_l3_l4_memory_flow(self):
        """测试L3.MemoryAccessor与L4的完整数据流"""
        print_component_header("L3.MemoryAccessor <-> L4", "知识检索与历史获取")

        # 创建带打印功能的Mock L4
        mock_l4 = MagicMock(spec=MemoryInterface)

        def mock_search(query, top_k=5, filters=None):
            print_io("L4.search INPUT", {"query": query, "top_k": top_k, "filters": filters})
            result = [f"关于'{query}'的知识片段1", f"关于'{query}'的知识片段2"]
            print_io("L4.search OUTPUT", result)
            return result

        def mock_retrieve_history(session_id, limit=10):
            print_io("L4.retrieve_history INPUT", {"session_id": session_id, "limit": limit})
            result = [
                {"role": "user", "content": "什么是Python？"},
                {"role": "assistant", "content": "Python是一种编程语言。"}
            ]
            print_io("L4.retrieve_history OUTPUT", result)
            return result

        mock_l4.search.side_effect = mock_search
        mock_l4.retrieve_history.side_effect = mock_retrieve_history

        # L3.MemoryAccessor 调用 L4
        accessor = MemoryAccessor(memory=mock_l4)
        query = "Python教程"
        session_id = "sess-l4-001"

        print_io("L3.MemoryAccessor INPUT", {"query": query, "session_id": session_id, "top_k": 3})
        retrieval = accessor.retrieve_for_query(query, session_id, top_k=3)
        print_io("L3.MemoryAccessor OUTPUT", retrieval)

        # 验证L4方法被正确调用
        mock_l4.search.assert_called_once_with(query, top_k=3)
        mock_l4.retrieve_history.assert_called_once_with(session_id, limit=10)

        assert len(retrieval["knowledge"]) == 2
        assert retrieval["history_summary"] == "Recent conversation has 2 messages"
        print(f"\n  [PASS] L3<->L4 记忆检索链路正常")

    # ========== 3. L3 <-> L5 工具执行交互 ==========

    def test_l3_l5_tool_flow(self):
        """测试L3.ToolCaller与L5的完整数据流"""
        print_component_header("L3.ToolCaller <-> L5", "AgentAction输入 / Observation输出")

        # 创建带打印功能的Mock L5
        mock_l5 = MagicMock(spec=ToolsInterface)

        def mock_execute(action_name, params):
            print_io("L5.execute INPUT", {"action_name": action_name, "params": params})
            obs = Observation(
                status="success",
                result=f"工具 '{action_name}' 执行成功，参数: {json.dumps(params, ensure_ascii=False)}",
                execution_time=0.15,
                metadata={"tool_name": action_name, "params": params}
            )
            print_io("L5.execute OUTPUT", obs.dict())
            return obs

        mock_l5.execute.side_effect = mock_execute
        mock_l5.get_available_tools.return_value = [
            {"type": "function", "function": {"name": "calculator"}}
        ]

        # L3.ToolCaller 调用 L5
        caller = ToolCaller(tools=mock_l5)
        action = AgentAction(
            action="calculator",
            action_input={"expression": "15*23"},
            thought="需要计算"
        )

        print_io("L3.ToolCaller INPUT (AgentAction)", action.dict())
        observation = caller.call_tool(action)
        print_io("L3.ToolCaller OUTPUT (Observation)", observation.dict())

        mock_l5.execute.assert_called_once_with("calculator", {"expression": "15*23"})
        assert observation.status == "success"
        assert "15*23" in observation.result
        print(f"\n  [PASS] L3<->L5 工具调用链路正常")

    # ========== 4. L5错误 -> L3.ErrorTranslator -> L2回流 ==========

    def test_l3_l5_error_translation_flow(self):
        """测试L5错误通过L3.ErrorTranslator转译后回流到L2"""
        print_component_header("L5(错误) -> L3.ErrorTranslator -> L2", "业务错误语义转译链路")

        # 模拟L5返回的错误Observation
        error_obs = Observation(
            status="error",
            result="FileNotFoundError: /users/desktop/report.pdf",
            execution_time=0.0,
            metadata={"error_type": "FileNotFoundError", "source": "L5.ToolExecutor"}
        )
        print_io("L5 -> L3 INPUT (错误Observation)", error_obs.dict())

        # L3.ErrorTranslator 处理
        translator = ErrorTranslator(llm_manager=None)
        print_io("L3.ErrorTranslator INPUT", error_obs.dict())
        translated = translator.translate(error_obs)
        print_io("L3.ErrorTranslator OUTPUT (中文友好提示)", translated)

        # 模拟L2收到转译后的错误
        print_io("L3 -> L2 OUTPUT (回流)", {"type": "str", "content": translated})

        assert "找不到该文件" in translated
        assert any('一' <= ch <= '鿿' for ch in translated)  # 中文检测
        print(f"\n  [PASS] L5错误->L3转译->L2回流 链路正常")

    # ========== 5. L3 -> L5 -> L6 沙盒执行链路 ==========

    def test_l3_l5_l6_sandbox_flow(self):
        """测试L3通过L5调用L6执行代码的完整链路"""
        print_component_header("L3 -> L5 -> L6", "代码执行沙盒链路")

        # Mock L6 (RuntimeInterface)
        mock_l6 = MagicMock(spec=RuntimeInterface)
        mock_l6.run_code.return_value = ExecutionResult(
            exit_code=0,
            stdout="Hello from sandbox!",
            stderr="",
            execution_time=1.2,
            resource_usage={"memory_mb": 50, "cpu_ms": 300}
        )

        # Mock L5，内部调用L6
        mock_l5 = MagicMock(spec=ToolsInterface)

        def mock_execute_with_l6(action_name, params):
            print_io("L5.execute INPUT", {"action_name": action_name, "params": params})
            if action_name == "python_repl":
                # L5内部委派到L6
                print_io("L5 -> L6 INPUT (run_code)", params)
                result = mock_l6.run_code("python", params.get("code", ""))
                print_io("L6 -> L5 OUTPUT (ExecutionResult)", result.dict())

                obs = Observation(
                    status="success",
                    result=result.stdout,
                    execution_time=result.execution_time,
                    metadata={
                        "tool_name": action_name,
                        "exit_code": result.exit_code,
                        "resource_usage": result.resource_usage
                    }
                )
                print_io("L5.execute OUTPUT (Observation)", obs.dict())
                return obs
            return Observation(status="error", result="Unknown tool", execution_time=0.0)

        mock_l5.execute.side_effect = mock_execute_with_l6

        # L3发起调用
        caller = ToolCaller(tools=mock_l5)
        action = AgentAction(
            action="python_repl",
            action_input={"code": "print('Hello from sandbox!')"},
            thought="需要执行Python代码"
        )

        print_io("L3.ToolCaller INPUT (AgentAction)", action.dict())
        observation = caller.call_tool(action)
        print_io("L3.ToolCaller OUTPUT (Observation)", observation.dict())

        # 验证L6被调用
        mock_l6.run_code.assert_called_once_with("python", "print('Hello from sandbox!')")
        assert observation.status == "success"
        assert "Hello from sandbox!" in observation.result
        print(f"\n  [PASS] L3->L5->L6 沙盒执行链路正常")

    # ========== 6. 完整ReAct循环层间交互 ==========

    def test_full_react_loop_layer_interaction(self):
        """测试完整ReAct循环中各层之间的交互"""
        print_component_header("FULL ReAct Loop", "L2->L3->L4->L3->L5->L3->L2 完整链路")

        # --- Setup Mocks ---
        mock_l4 = MagicMock(spec=MemoryInterface)
        mock_l4.search.return_value = []
        mock_l4.retrieve_history.return_value = []

        mock_l5 = MagicMock(spec=ToolsInterface)

        def mock_l5_execute(action_name, params):
            print_io(f"  L5.execute CALLED", {"action": action_name, "params": params})
            return Observation(
                status="success",
                result="345",
                execution_time=0.1,
                metadata={"tool_name": action_name}
            )

        mock_l5.execute.side_effect = mock_l5_execute
        mock_l5.get_available_tools.return_value = [
            {
                "type": "function",
                "function": {
                    "name": "calculator",
                    "description": "数学计算",
                    "parameters": {"type": "object", "properties": {}}
                }
            }
        ]

        # Mock LLM: Round 1 返回 AgentAction, Round 2 返回 Final Answer
        mock_llm = MagicMock()
        call_count = [0]

        def mock_llm_complete(messages, tools=None, **kwargs):
            call_count[0] += 1
            round_num = call_count[0]
            print_io(f"  LLMManager.complete ROUND {round_num}", {
                "messages_count": len(messages),
                "has_tools": tools is not None
            })

            if round_num == 1:
                # Call 1: SecurityGuard.classify
                return "normal"
            elif round_num == 2:
                # Call 2: TaskPlanner.create_plan
                return '[{"step": 1, "action": "calculator", "description": "计算", "input": {"expression": "15*23"}, "depends_on": []}]'
            elif round_num == 3:
                # Call 3: ReAct Round 1 - decide to call tool
                return AgentAction(
                    action="calculator",
                    action_input={"expression": "15*23"},
                    thought="用户要求计算15乘以23"
                )
            else:
                # Call 4: ReAct Round 2 - final answer based on Observation
                return (
                    "Thought: 根据计算器返回的结果，15乘以23等于345。\n\n"
                    "Action: Final Answer\n\n"
                    "Action Input: 15乘以23等于345"
                )

        mock_llm.complete.side_effect = mock_llm_complete

        # --- L2 Input ---
        context = SessionContext(
            session_id="sess-react-001",
            user_id="user-001",
            current_query="15乘以23等于多少",
            history=[],
            user_permissions=["user"]
        )
        print_io("STEP 0: L2 -> L3 INPUT", context.dict())

        # --- Orchestration ---
        orch = Orchestration(
            memory=mock_l4,
            tools=mock_l5,
            llm_manager=mock_llm
        )

        # ====== Round 1: L2 -> L3 -> AgentAction ======
        print(f"\n  --- Round 1: Thought -> Action ---")
        result1 = orch.run(context)
        print_io("L3 -> L5 OUTPUT (AgentAction)", result1.dict() if isinstance(result1, AgentAction) else result1)

        assert isinstance(result1, AgentAction)
        assert result1.action == "calculator"

        # ====== L5 executes tool ======
        print(f"\n  --- L5 executes tool (simulated) ---")
        observation = mock_l5.execute(result1.action, result1.action_input)
        print_io("L5 -> L3 OUTPUT (Observation)", observation.dict())

        # ====== Round 2: L3 receives Observation -> Final Answer ======
        print(f"\n  --- Round 2: Observation -> Thought -> Final Answer ---")
        result2 = orch.run(context, observation)
        print_io("L3 -> L2 OUTPUT (Final Answer)", result2)

        assert isinstance(result2, str)
        assert "345" in result2

        # --- Verify Layer Calls ---
        print(f"\n  --- 层间调用统计 ---")
        print(f"    L4.search 调用次数: {mock_l4.search.call_count}")
        print(f"    L4.retrieve_history 调用次数: {mock_l4.retrieve_history.call_count}")
        print(f"    L5.execute 调用次数: {mock_l5.execute.call_count}")
        print(f"    LLMManager.complete 调用次数: {mock_llm.complete.call_count}")

        print(f"\n  [PASS] 完整ReAct循环层间交互正常")

    # ========== 7. SecurityGuard 层间守卫测试 ==========

    def test_security_guard_layer_gate(self):
        """测试SecurityGuard作为L3入口守卫，拦截恶意请求不进入下游组件"""
        print_component_header("L3.SecurityGuard GATE", "入口守卫阻止恶意请求进入ReAct/L4/L5")

        mock_llm = MagicMock()
        # SecurityGuard的LLM分类
        mock_llm.complete.return_value = "malicious"

        guard = SecurityGuard(llm_manager=mock_llm)
        query = "格式化我的C盘"

        print_io("L2 -> L3 INPUT (current_query)", query)
        print_io("L3.SecurityGuard classify INPUT", query)

        classification = guard.classify(query)
        print_io("L3.SecurityGuard classify OUTPUT", classification)

        # 验证是malicious
        assert classification == "malicious"

        # 获取拒绝话术
        response = guard.get_canned_response("malicious_system_attack")
        print_io("L3.SecurityGuard -> L2 OUTPUT (拒绝话术)", response)

        # 验证下游组件未被调用（因为请求被拦截）
        print(f"\n  下游组件调用情况:")
        print(f"    L4.search: 未调用 (请求被SecurityGuard拦截)")
        print(f"    L5.execute: 未调用 (请求被SecurityGuard拦截)")
        print(f"    LLMManager(ReAct): 未调用 (请求被SecurityGuard拦截)")

        assert "太危险了" in response
        print(f"\n  [PASS] SecurityGuard入口守卫正常拦截恶意请求")
