"""Test that TaskPlanner output feeds into ReActEngine."""
import sys
sys.path.insert(0, 'src')

from unittest.mock import Mock, patch
from src.core.models import SessionContext
from src.l3.l3_orchestration import Orchestration, TaskPlanner, ReActEngine


class TestTaskPlannerIntegration:
    """Verify TaskPlanner creates plan and ReActEngine uses it."""

    def test_plan_created_before_react_loop(self):
        """Orchestration._run_react_loop() must call task_planner.create_plan() before ReAct."""
        orch = Orchestration()

        with patch.object(orch.task_planner, 'create_plan', return_value=[
            {"step": 1, "action": "llm", "description": "Answer directly"}
        ]) as mock_plan:
            with patch.object(orch.react_engine, 'generate_thought', return_value={
                "thought": "ok",
                "action_type": "final_answer",
                "action": "Final Answer",
                "action_input": {"text": "done"}
            }):
                context = SessionContext(
                    session_id="s1",
                    user_id="u1",
                    current_query="hello"
                )
                orch._run_react_loop(context)

        mock_plan.assert_called_once()

    def test_plan_passed_to_react_engine(self):
        """ReActEngine.generate_thought must receive the current plan."""
        engine = ReActEngine()

        with patch.object(engine.llm_manager, 'complete', return_value={
            "thought": "Plan says to answer directly",
            "action_type": "final_answer",
            "action": "Final Answer",
            "action_input": {"text": "Hello!"}
        }) as mock_complete:
            result = engine.generate_thought(
                query="hello",
                available_tools=[],
                plan_steps=[{"step": 1, "action": "llm", "description": "Greet user"}]
            )

        # Check that the prompt included plan information
        call_args = mock_complete.call_args
        messages = call_args[1].get('messages', call_args[0][0])
        prompt_text = messages[-1]["content"]
        assert "Plan" in prompt_text or "plan" in prompt_text or "step" in prompt_text
