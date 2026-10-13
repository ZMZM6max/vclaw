"""L3: Orchestration Layer - Task planning, ReAct loop, LLM management."""
import os
import json
import time
import re
import logging
from enum import Enum
from typing import List, Dict, Any, Optional, Union, Iterator
from abc import ABC, abstractmethod
from src.core.models import SessionContext, AgentAction, Observation
from src.core.interfaces import MemoryInterface, ToolsInterface
from src.l4 import MemoryKnowledge
from src.l5.l5_tools import ToolsCapabilities


from src.core.exceptions import (
    LLMError, MaxIterationsExceeded, ToolExecutionError
)

# Re-export for backward compatibility
__all__ = ['LLMError', 'MaxIterationsExceeded', 'ToolExecutionError']


class ProviderType(str, Enum):
    """Enum for LLM provider types."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    CLAUDE = "claude"  # Alias for anthropic
    KIMI = "kimi"
    MOONSHOT = "moonshot"  # Alias for kimi


# Constants for fallback plan
FALLBACK_PLAN_STEP = 1
FALLBACK_PLAN_ACTION = "llm"
FALLBACK_PLAN_DESCRIPTION = "Process user request directly"


def create_fallback_plan(query: str) -> List[Dict]:
    """Create a fallback plan when task planning fails."""
    return [{
        "step": FALLBACK_PLAN_STEP,
        "action": FALLBACK_PLAN_ACTION,
        "description": FALLBACK_PLAN_DESCRIPTION,
        "input": {"query": query},
        "depends_on": []
    }]


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def complete(self, messages: List[Dict], tools: List[Dict] = None, **kwargs) -> Union[str, AgentAction]:
        """Call LLM for completion."""
        pass

    @abstractmethod
    def stream(self, messages: List[Dict], **kwargs) -> Iterator[str]:
        """Stream LLM response."""
        pass


class OpenAICompatibleProvider(LLMProvider):
    """Base class for OpenAI-compatible API providers (OpenAI, Kimi, etc.)."""

    def __init__(self, api_key: str, model: str, base_url: str = None,
                 provider_name: str = "OpenAI"):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.provider_name = provider_name
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                from openai import OpenAI
                kwargs = {"api_key": self.api_key}
                if self.base_url:
                    kwargs["base_url"] = self.base_url
                self._client = OpenAI(**kwargs)
            except ImportError:
                raise LLMError(f"OpenAI package not installed. Run: pip install openai")
        return self._client

    def complete(self, messages: List[Dict], tools: List[Dict] = None, **kwargs) -> Union[str, AgentAction]:
        """Call API for completion."""
        try:
            client = self._get_client()
            response = client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=tools,
                tool_choice="auto" if tools else None,
                **kwargs
            )

            message = response.choices[0].message

            # Check if there's a tool call
            if message.tool_calls:
                tool_call = message.tool_calls[0]
                return AgentAction(
                    action=tool_call.function.name,
                    action_input=json.loads(tool_call.function.arguments),
                    thought=message.content or "Using tool to complete the task"
                )

            return message.content

        except Exception as e:
            raise LLMError(f"{self.provider_name} API error: {str(e)}")

    def stream(self, messages: List[Dict], **kwargs) -> Iterator[str]:
        """Stream LLM response."""
        try:
            client = self._get_client()
            stream = client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=True,
                **kwargs
            )

            for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            raise LLMError(f"{self.provider_name} streaming error: {str(e)}")


class OpenAIProvider(OpenAICompatibleProvider):
    """OpenAI GPT provider."""

    def __init__(self, api_key: str = None, model: str = "gpt-4o", base_url: str = None):
        super().__init__(
            api_key=api_key or os.getenv("OPENAI_API_KEY"),
            model=model,
            base_url=base_url or os.getenv("OPENAI_BASE_URL") or os.getenv("API_BASE_URL"),
            provider_name="OpenAI"
        )


class AnthropicProvider(LLMProvider):
    """Anthropic Claude provider."""

    def __init__(self, api_key: str = None, model: str = "claude-3-sonnet-20240229"):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.model = model
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=self.api_key)
            except ImportError:
                raise LLMError("Anthropic package not installed. Run: pip install anthropic")
        return self._client

    def complete(self, messages: List[Dict], tools: List[Dict] = None, **kwargs) -> Union[str, AgentAction]:
        """Call Anthropic API for completion."""
        try:
            client = self._get_client()

            # Convert OpenAI format to Anthropic format
            system_msg = ""
            anthropic_messages = []

            for msg in messages:
                if msg["role"] == "system":
                    system_msg += msg["content"] + "\n"
                else:
                    anthropic_messages.append(msg)

            # Convert tools format if provided
            anthropic_tools = None
            if tools:
                anthropic_tools = []
                for tool in tools:
                    anthropic_tools.append({
                        "name": tool["function"]["name"],
                        "description": tool["function"]["description"],
                        "input_schema": tool["function"]["parameters"]
                    })

            response = client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=system_msg.strip() if system_msg else None,
                messages=anthropic_messages,
                tools=anthropic_tools,
                **kwargs
            )

            # Check for tool use
            for content in response.content:
                if content.type == "tool_use":
                    return AgentAction(
                        action=content.name,
                        action_input=content.input,
                        thought="Using tool to complete the task"
                    )

            # Return text response
            text_content = " ".join([c.text for c in response.content if c.type == "text"])
            return text_content

        except Exception as e:
            raise LLMError(f"Anthropic API error: {str(e)}")

    def stream(self, messages: List[Dict], **kwargs) -> Iterator[str]:
        """Stream LLM response from Anthropic."""
        try:
            client = self._get_client()

            # Convert OpenAI format to Anthropic format
            system_msg = ""
            anthropic_messages = []

            for msg in messages:
                if msg["role"] == "system":
                    system_msg += msg["content"] + "\n"
                else:
                    anthropic_messages.append(msg)

            with client.messages.stream(
                model=self.model,
                max_tokens=4096,
                system=system_msg.strip() if system_msg else None,
                messages=anthropic_messages,
                **kwargs
            ) as stream:
                for text in stream.text_stream:
                    yield text

        except Exception as e:
            raise LLMError(f"Anthropic streaming error: {str(e)}")


class KimiProvider(OpenAICompatibleProvider):
    """Moonshot Kimi provider."""

    def __init__(self, api_key: str = None, model: str = "moonshot-v1-128k"):
        super().__init__(
            api_key=api_key or os.getenv("KIMI_API_KEY"),
            model=model,
            base_url="https://api.moonshot.cn/v1",
            provider_name="Kimi"
        )


class LLMManager:
    """LLM manager supporting multiple providers with retry and streaming."""

    PROVIDERS = {
        ProviderType.OPENAI: OpenAIProvider,
        ProviderType.ANTHROPIC: AnthropicProvider,
        ProviderType.CLAUDE: AnthropicProvider,  # Alias
        ProviderType.KIMI: KimiProvider,
        ProviderType.MOONSHOT: KimiProvider  # Alias
    }

    def __init__(self, provider: Union[str, ProviderType] = ProviderType.OPENAI,
                 model: str = None, api_key: str = None, base_url: str = None,
                 max_retries: int = 3, retry_delay: float = 1.0):
        """Initialize LLM manager.

        Args:
            provider: Provider name or ProviderType enum
            model: Model name (optional, uses provider default if not set)
            api_key: API key (optional, reads from env if not set)
            base_url: API base URL (optional, for third-party API platforms)
            max_retries: Maximum number of retries on failure
            retry_delay: Initial delay between retries (doubles each retry)
        """
        # Convert string to enum if needed
        if isinstance(provider, str):
            try:
                self.provider_name = ProviderType(provider.lower())
            except ValueError:
                raise LLMError(f"Unknown provider: {provider}. Available: {[p.value for p in ProviderType]}")
        else:
            self.provider_name = provider

        if self.provider_name not in self.PROVIDERS:
            raise LLMError(f"Unknown provider: {provider}")

        self.max_retries = max_retries
        self.retry_delay = retry_delay
        provider_class = self.PROVIDERS[self.provider_name]
        kwargs = {}
        if api_key:
            kwargs["api_key"] = api_key
        if model:
            kwargs["model"] = model
        if base_url:
            kwargs["base_url"] = base_url
        self.provider = provider_class(**kwargs) if kwargs else provider_class()

    def complete(self, messages: List[Dict], tools: List[Dict] = None, **kwargs) -> Union[str, AgentAction]:
        """Call LLM for completion with retry logic."""
        last_error = None
        delay = self.retry_delay
        max_delay = 60  # Cap at 60 seconds

        for attempt in range(self.max_retries):
            try:
                return self.provider.complete(messages, tools, **kwargs)
            except LLMError as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    # Add jitter (±25%) and cap delay
                    import random
                    jittered_delay = delay * (0.75 + random.random() * 0.5)
                    time.sleep(min(jittered_delay, max_delay))
                    delay *= 2  # Exponential backoff
                continue

        raise LLMError(f"Failed after {self.max_retries} attempts: {str(last_error)}")

    def stream(self, messages: List[Dict], **kwargs) -> Iterator[str]:
        """Stream LLM response with retry logic."""
        last_error = None
        delay = self.retry_delay
        max_delay = 60

        for attempt in range(self.max_retries):
            try:
                yield from self.provider.stream(messages, **kwargs)
                return
            except LLMError as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    import random
                    jittered_delay = delay * (0.75 + random.random() * 0.5)
                    time.sleep(min(jittered_delay, max_delay))
                    delay *= 2
                continue

        raise LLMError(f"Streaming failed after {self.max_retries} attempts: {str(last_error)}")

    def switch_provider(self, provider: Union[str, ProviderType], model: str = None, api_key: str = None):
        """Switch to a different provider."""
        if isinstance(provider, str):
            try:
                self.provider_name = ProviderType(provider.lower())
            except ValueError:
                raise LLMError(f"Unknown provider: {provider}")
        else:
            self.provider_name = provider

        if self.provider_name not in self.PROVIDERS:
            raise LLMError(f"Unknown provider: {provider}")

        provider_class = self.PROVIDERS[self.provider_name]
        self.provider = provider_class(api_key=api_key, model=model) if model or api_key else provider_class()


class TaskPlanner:
    """Task planner using a small model for planning."""

    def __init__(self, llm_manager: LLMManager = None, planning_llm: LLMManager = None):
        self.llm_manager = llm_manager or LLMManager()
        # planning_llm can be configured separately (e.g., a lighter/smaller model)
        # If not provided, reuse the main llm_manager
        self.planning_llm = planning_llm or self.llm_manager

    def create_plan(self, query: str, context: str = "", available_tools: List[Dict] = None) -> List[Dict]:
        """Create a task plan for the given query.

        Returns a list of steps, each with:
        - step: step number
        - action: tool name or "llm"
        - description: what this step does
        - depends_on: list of step numbers this depends on
        """
        tools_desc = ""
        if available_tools:
            tools_desc = "\nAvailable tools:\n" + json.dumps(available_tools, indent=2)

        planning_prompt = f"""You are a task planner. Break down the following user request into a sequence of steps.
Each step should use either a tool or LLM reasoning.

User request: {query}
Context: {context}{tools_desc}

Output a JSON array of steps with this format:
[
    {{
        "step": 1,
        "action": "tool_name or 'llm'",
        "description": "what this step does",
        "input": {{"key": "value"}},
        "depends_on": []
    }}
]

Rules:
- Use tools when specific capabilities are needed (calculator, web search, code execution)
- Use 'llm' for reasoning, summarization, or when no tool fits
- Number steps sequentially starting from 1
- Use depends_on to indicate dependencies between steps
- The LAST step must ALWAYS be delivering the final result to the user
- NEVER end the plan at an intermediate data-gathering step (e.g., "get the data", "search for files")
- If tools are needed, include actual tool execution steps, not just "plan to use tool"
- After tool results are obtained, always include a step to present/summarize the result to the user

Output only valid JSON:"""

        messages = [
            {"role": "system", "content": "You are a helpful task planning assistant."},
            {"role": "user", "content": planning_prompt}
        ]

        try:
            response = self.planning_llm.complete(messages, temperature=0.2)
            if isinstance(response, AgentAction):
                response = response.action_input.get("code", "[]")

            # Parse the plan
            if isinstance(response, str):
                # Try to extract JSON from the response
                try:
                    # Find JSON array in the response
                    start = response.find("[")
                    end = response.rfind("]") + 1
                    if start >= 0 and end > start:
                        plan = json.loads(response[start:end])
                    else:
                        plan = json.loads(response)
                except (json.JSONDecodeError, ValueError):
                    # Fallback: simple single-step plan
                    return create_fallback_plan(query)
            else:
                plan = response if isinstance(response, list) else []

            # Ensure plan is not empty
            if not plan:
                return create_fallback_plan(query)

            return plan

        except Exception as e:
            # Fallback to simple plan
            return create_fallback_plan(query)

    def get_next_step(self, plan: List[Dict], completed_steps: List[int]) -> Optional[Dict]:
        """Get the next executable step from the plan."""
        for step in plan:
            step_num = step.get("step")
            if step_num in completed_steps:
                continue

            # Check if dependencies are satisfied
            depends_on = step.get("depends_on", [])
            if all(dep in completed_steps for dep in depends_on):
                return step

        return None


class ReActEngine:
    """ReAct循环引擎 - 实现真正的Thought-Action-Observation闭环。

    ReAct (Reasoning + Acting) 循环:
    1. Thought: LLM分析当前状态，决定下一步行动
    2. Action: 执行决策（调用工具或直接回复）
    3. Observation: 观察执行结果，更新状态
    4. 循环直到得到最终答案或达到最大迭代次数

    Attributes:
        llm_manager: LLM管理器，用于生成Thought
        thought_history: 思考历史记录
        max_iterations: 最大迭代次数
    """

    def __init__(self, llm_manager: LLMManager = None):
        self.llm_manager = llm_manager or LLMManager()
        self.thought_history: List[Dict] = []
        self.max_iterations = 5

    # 文件查询意图关键词
    FILE_QUERY_KEYWORDS = ["找", "查找", "搜索", "定位", "有没有", "在哪", "寻找", "搜一下",
                           "search", "find", "look for", "locate"]

    def _is_file_query(self, query: str) -> bool:
        """检测用户查询是否为文件查询意图。"""
        query_lower = query.lower()
        return any(kw.lower() in query_lower for kw in self.FILE_QUERY_KEYWORDS)

    def _enforce_mandatory_pre_action_rules(self, query: str, react_result: Dict,
                                             observation: Observation,
                                             available_tools: List[Dict]) -> Dict:
        """显式强制执行MandatoryPreActionRules。

        当用户意图为文件查询且是第一次调用（无Observation）时，
        禁止直接返回final_answer，必须至少尝试一次工具调用。
        """
        if observation is not None:
            # 已有Observation，说明已经尝试过工具调用，允许final_answer
            return react_result

        if react_result.get("action_type") != "final_answer":
            # 已经是tool调用，无需干预
            return react_result

        if not self._is_file_query(query):
            # 不是文件查询，不干预
            return react_result

        if not available_tools:
            # 没有可用工具，无法强制
            return react_result

        # 强制将final_answer改为tool调用：尝试调用file_search或search_web
        tool_names = []
        for tool in available_tools:
            if 'function' in tool:
                tool_names.append(tool['function'].get('name', ''))

        target_tool = None
        for candidate in ['file_search', 'search_web', 'file_read', 'search']:
            if candidate in tool_names:
                target_tool = candidate
                break

        if target_tool is None:
            return react_result

        # 强制修改为工具调用
        return {
            "thought": react_result.get("thought", "") + f"\n[MandatoryRule] File query detected, must attempt tool call first.",
            "action_type": "tool",
            "action": target_tool,
            "action_input": {"keyword": query, "query": query}
        }

    def generate_thought(self,
                        query: str,
                        observation: Observation = None,
                        available_tools: List[Dict] = None,
                        knowledge: List[str] = None,
                        history: List[Dict[str, str]] = None,
                        plan_steps: List[Dict] = None) -> Dict:
        """生成ReAct Thought。

        使用专门的提示词引导LLM进行推理，决定下一步行动。

        Args:
            query: 用户查询
            observation: 之前的工具执行结果
            available_tools: LLM可用的工具定义
            knowledge: 相关知识片段
            history: 对话历史
            plan_steps: TaskPlanner步骤，用于结构化指导

        Returns:
            {
                "thought": "分析思考过程",
                "action_type": "tool" or "final_answer",
                "action": "工具名称或回答内容",
                "action_input": {}  # 工具参数
            }
        """
        tools_desc = ""
        if available_tools:
            tools_desc = "\nAvailable tools:\n"
            for tool in available_tools:
                if 'function' in tool:
                    name = tool['function'].get('name', 'unknown')
                    desc = tool['function'].get('description', '')
                    tools_desc += f"- {name}: {desc}\n"

        knowledge_desc = ""
        if knowledge:
            knowledge_desc = f"\nRelevant knowledge:\n" + "\n".join(knowledge)

        observation_desc = ""
        if observation:
            observation_desc = f"""
Previous tool execution result:
Status: {observation.status}
Result: {observation.result}
"""

        thought_history_desc = ""
        if self.thought_history:
            thought_history_desc = "\nPrevious thoughts and actions:\n"
            for i, entry in enumerate(self.thought_history[-3:], 1):  # 最近3条
                thought_history_desc += f"{i}. Thought: {entry.get('thought', 'N/A')}\n"
                if entry.get('action'):
                    thought_history_desc += f"   Action: {entry.get('action')}\n"

        plan_desc = ""
        if plan_steps:
            plan_desc = "\nTask Plan:\n"
            for step in plan_steps:
                plan_desc += f"  Step {step.get('step', '?')}: {step.get('action', 'unknown')} - {step.get('description', '')}\n"
            plan_desc += "\nFollow the plan steps above when deciding your next action.\n"

        react_prompt = f"""You are an AI assistant that follows the ReAct (Reasoning + Acting) pattern.

Your task is to analyze the user's request and decide the next step.{thought_history_desc}

User request: {query}{knowledge_desc}{observation_desc}{plan_desc}{tools_desc}

Follow this format in your response:

Thought: [Your step-by-step reasoning about what to do next]

Action: [If you need to use a tool, write the tool name. If you have the final answer, write "Final Answer"]

Action Input: [If using a tool, provide the input parameters as JSON. If final answer, provide the answer text]

Rules:
1. Break down complex problems into steps
2. Use tools when they can help (calculator, search, file operations, code execution, etc.)
3. If previous tool result is available, analyze it before deciding next step
4. When you have enough information to answer, use "Final Answer" as the action
5. For file operations, use natural language paths (e.g., "桌面/文件.txt", "文档/报告.md")
6. IMPORTANT: When the user asks to "use python", "run python", "execute code", or similar, you MUST use the python_repl tool to execute the code and return the actual output. Do not just describe the code.
7. When using python_repl, the Action Input MUST be valid JSON with a "code" key containing the Python code to run. Example: {{"code": "print('hello')"}}

Respond with Thought, Action, and Action Input:"""

        messages = [
            {"role": "system", "content": "You are a helpful assistant that thinks step by step before acting."}
        ]

        # Include conversation history so the model has memory across turns
        if history:
            for msg in history[-10:]:  # Keep last 10 messages to manage token usage
                role = msg.get("role")
                content = msg.get("content")
                if role in ("user", "assistant") and content:
                    messages.append({"role": role, "content": content})

        messages.append({"role": "user", "content": react_prompt})

        try:
            # Pass available_tools to LLM for function calling
            response = self.llm_manager.complete(messages, tools=available_tools, temperature=0.3)

            if isinstance(response, AgentAction):
                # LLM decided to use a tool directly
                result = {
                    "thought": response.thought or "Using tool to complete the task",
                    "action_type": "tool",
                    "action": response.action,
                    "action_input": response.action_input
                }
            else:
                # Parse text response
                result = self._parse_react_response(response)

            # 显式强制执行MandatoryPreActionRules
            result = self._enforce_mandatory_pre_action_rules(
                query, result, observation, available_tools
            )
            return result

        except Exception as e:
            # Fallback: return final answer with error info
            return {
                "thought": f"Error generating thought: {str(e)}",
                "action_type": "final_answer",
                "action": f"I encountered an error: {str(e)}",
                "action_input": {}
            }

    def _parse_react_response(self, response: str) -> Dict:
        """解析ReAct格式的响应。

        从LLM响应中提取 Thought, Action, Action Input。
        """
        thought = ""
        action = ""
        action_input = {}

        # Extract Thought
        thought_match = re.search(r'Thought:\s*(.+?)(?=\n\n|Action:|$)', response, re.DOTALL | re.IGNORECASE)
        if thought_match:
            thought = thought_match.group(1).strip()

        # Extract Action
        action_match = re.search(r'Action:\s*(.+?)(?=\n\n|Action Input:|$)', response, re.DOTALL | re.IGNORECASE)
        if action_match:
            action = action_match.group(1).strip()

        # Extract Action Input
        action_input_match = re.search(r'Action Input:\s*(.+?)(?=\n\n|$)', response, re.DOTALL | re.IGNORECASE)
        if action_input_match:
            input_text = action_input_match.group(1).strip()
            # Try to parse as JSON
            try:
                if input_text.startswith('{'):
                    action_input = json.loads(input_text)
                else:
                    action_input = {"text": input_text}
            except json.JSONDecodeError:
                action_input = {"text": input_text}

        # Determine action type
        # "llm" is a TaskPlanner marker for "use LLM reasoning", translate to final_answer
        action_lower = action.lower().strip()
        is_final = (
            action_lower in ["final answer", "final_answer", "llm"]
            or action_lower.startswith("llm ")
        )
        action_type = "final_answer" if is_final else "tool"

        return {
            "thought": thought,
            "action_type": action_type,
            "action": action,
            "action_input": action_input
        }

    def add_to_history(self, thought: str, action: str, observation: str = None):
        """记录思考历史。"""
        entry = {
            "thought": thought,
            "action": action,
            "observation": observation,
            "timestamp": time.time()
        }
        self.thought_history.append(entry)

    def reset(self):
        """重置ReAct引擎状态。"""
        self.thought_history = []


class MemoryAccessor:
    """Memory accessor for retrieving relevant context."""

    def __init__(self, memory: MemoryInterface = None):
        self.memory = memory or MemoryKnowledge()

    def retrieve_for_query(self, query: str, session_id: str,
                          top_k: int = 3, include_history: bool = True) -> Dict[str, Any]:
        """Retrieve relevant information for a query.

        Returns:
            Dictionary with:
            - knowledge: list of relevant knowledge snippets
            - history_summary: summary of recent conversation
            - related_queries: similar past queries
        """
        result = {
            "knowledge": [],
            "history_summary": "",
            "related_queries": []
        }

        # Search knowledge base
        try:
            knowledge = self.memory.search(query, top_k=top_k)
            result["knowledge"] = knowledge
        except Exception:
            pass

        # Retrieve conversation history
        if include_history:
            try:
                history = self.memory.retrieve_history(session_id, limit=10)
                if history:
                    # Summarize history
                    user_msgs = [h["content"] for h in history if h.get("role") == "user"]
                    result["related_queries"] = user_msgs[-3:] if len(user_msgs) > 0 else []
                    result["history_summary"] = f"Recent conversation has {len(history)} messages"
            except Exception:
                pass

        return result

    def format_context(self, retrieval_result: Dict[str, Any]) -> str:
        """Format retrieved context for LLM consumption."""
        context_parts = []

        if retrieval_result.get("knowledge"):
            context_parts.append("Relevant knowledge:")
            for i, item in enumerate(retrieval_result["knowledge"], 1):
                context_parts.append(f"  [{i}] {item}")

        if retrieval_result.get("history_summary"):
            context_parts.append(f"\nConversation: {retrieval_result['history_summary']}")

        if retrieval_result.get("related_queries"):
            context_parts.append("Related previous queries:")
            for q in retrieval_result["related_queries"]:
                context_parts.append(f"  - {q}")

        return "\n".join(context_parts) if context_parts else ""


class Orchestration:
    """L3 implementation - Orchestration and ReAct loop."""

    MAX_ITERATIONS = 5

    def __init__(self, memory: MemoryInterface = None,
                 tools: ToolsInterface = None,
                 llm_manager: LLMManager = None):
        self.memory = memory or MemoryKnowledge()
        self.tools = tools or ToolsCapabilities()
        self.llm_manager = llm_manager or LLMManager()
        self.task_planner = TaskPlanner(self.llm_manager)
        self.memory_accessor = MemoryAccessor(self.memory)
        self.react_engine = ReActEngine(self.llm_manager)
        self.security_guard = SecurityGuard(llm_manager=self.llm_manager)
        self.error_translator = ErrorTranslator(llm_manager=self.llm_manager)
        self.iteration_count = 0
        self.current_plan: List[Dict] = []
        self.completed_steps: List[int] = []
        self.pending_confirmation: Optional[Dict] = None
        self.session_context: Optional[SessionContext] = None

    def run(self, context: SessionContext,
            observation: Observation = None) -> Union[str, AgentAction]:
        """Run orchestration logic with true ReAct loop.

        Implements the ReAct pattern: Thought -> Action -> Observation -> Thought...
        Continues until a final answer is reached or max iterations exceeded.

        SecurityGuard is called as a mandatory pre-gate before any processing.

        Args:
            context: Session context with user query and history
            observation: Result from previous tool execution (for ReAct loop continuation)

        Returns:
            AgentAction if a tool needs to be called
            str if we have the final answer
        """
        # === Mandatory SecurityGuard Check ===
        if observation is None:  # Only on first entry, not during ReAct loop
            classification = self.security_guard.classify(context.current_query)

            if classification == "malicious":
                return self.security_guard.get_canned_response("malicious_request")

            if classification == "high-risk":
                return (
                    f"您的请求「{context.current_query}」被识别为高危操作。"
                    f"请确认是否继续？（回复\"是\"继续，\"否\"取消）"
                )

            if classification == "sensitive":
                # Log sensitive request but proceed
                logger = logging.getLogger(__name__)
                logger.info(f"Sensitive request from user {context.user_id}: {context.current_query}")

            # "normal" falls through to ReAct loop

        return self._run_react_loop(context, observation)

    def _run_react_loop(self, context: SessionContext,
                        observation: Observation = None) -> Union[str, AgentAction]:
        """Internal ReAct loop (extracted from original run() method)."""
        # Handle pending confirmation state
        if self.pending_confirmation:
            return self._handle_confirmation(context.current_query)

        # Handle confirmation_required observation
        if observation and observation.status == "confirmation_required":
            tool_name = observation.metadata.get("tool", "该操作")
            return f"执行 {tool_name} 需要您的确认。是否继续？（回复\"是\"继续，\"否\"取消）"

        # Handle error observation
        if observation and observation.status == "error":
            return self._translate_error(observation)

        # Check max iterations
        if self.iteration_count >= self.MAX_ITERATIONS:
            raise MaxIterationsExceeded("Maximum iterations reached")

        # Store session context for later use
        if not self.session_context:
            self.session_context = context

        # Retrieve relevant context using MemoryAccessor
        retrieval_result = self.memory_accessor.retrieve_for_query(
            context.current_query,
            context.session_id
        )

        # Get available tools
        available_tools = self.tools.get_available_tools(context.user_permissions)

        # Create plan on first entry if empty
        if not self.current_plan and observation is None:
            self.current_plan = self.task_planner.create_plan(
                query=context.current_query,
                context="",
                available_tools=available_tools
            )

        # === ReAct Loop ===
        # If observation exists, we have a tool result to analyze
        if observation:
            # Record observation in ReAct history
            self.react_engine.add_to_history(
                thought="Received tool execution result",
                action=f"Observation: {observation.status}",
                observation=observation.result
            )

            # Generate new thought based on observation
            react_result = self.react_engine.generate_thought(
                query=context.current_query,
                observation=observation,
                available_tools=available_tools,
                knowledge=retrieval_result["knowledge"],
                history=context.history,
                plan_steps=self.current_plan
            )

            self.iteration_count += 1

            # Record the thought
            self.react_engine.add_to_history(
                thought=react_result["thought"],
                action=react_result["action"],
                observation=None
            )

            # Decide next step based on ReAct result
            if react_result["action_type"] == "final_answer":
                # We have the final answer - extract actual content from action_input
                action_input = react_result.get("action_input", {})
                if isinstance(action_input, dict):
                    text = action_input.get("text")
                    if text:
                        return text
                    # Fallback when action_input is empty or lacks text
                    return react_result.get("action", "") or "I have no response."
                return str(action_input)
            else:
                # Need to call another tool
                return AgentAction(
                    action=react_result["action"],
                    action_input=react_result["action_input"],
                    thought=react_result["thought"]
                )

        # First iteration: generate initial thought
        react_result = self.react_engine.generate_thought(
            query=context.current_query,
            observation=None,
            available_tools=available_tools,
            knowledge=retrieval_result["knowledge"],
            history=context.history,
            plan_steps=self.current_plan
        )

        self.iteration_count += 1

        # Record the thought
        self.react_engine.add_to_history(
            thought=react_result["thought"],
            action=react_result["action"],
            observation=None
        )

        # Decide next step
        if react_result["action_type"] == "final_answer":
            # Direct answer, no tool needed - extract actual content from action_input
            action_input = react_result.get("action_input", {})
            if isinstance(action_input, dict):
                text = action_input.get("text")
                if text:
                    return text
                # Fallback when action_input is empty or lacks text
                return react_result.get("action", "") or "I have no response."
            return str(action_input)
        else:
            # Need to call a tool
            return AgentAction(
                action=react_result["action"],
                action_input=react_result["action_input"],
                thought=react_result["thought"]
            )

    def run_streaming(self, context: SessionContext) -> Iterator[str]:
        """Run orchestration with streaming response.

        This is used for chat interfaces where you want to show
        the response as it's being generated.
        """
        # Retrieve context
        retrieval_result = self.memory_accessor.retrieve_for_query(
            context.current_query,
            context.session_id
        )

        # Build messages
        messages = self._build_messages(context, None, retrieval_result["knowledge"])

        # Stream response
        yield from self.llm_manager.stream(messages)

    def _build_messages(self, context: SessionContext,
                       observation: Observation = None,
                       knowledge: List[str] = None) -> List[Dict]:
        """Build messages for LLM."""
        messages = []

        # Add system prompt
        messages.append({
            "role": "system",
            "content": """You are a helpful AI assistant with access to tools.

SECURITY POLICY:
If the user request involves malicious operations (destroying system, deleting important data, hacking, etc.),
you MUST refuse the request politely and explain why.

Examples of malicious requests to refuse:
- Formatting disk, deleting system files
- Hacking, cracking, unauthorized access
- Creating malware, viruses
- Any operation that could harm the system or data

FILE PATH HANDLING:
When the user mentions a file path in natural language (e.g., "桌面", "下载", "文档"),
simply pass the path as-is in the tool parameters. The system will automatically resolve it.
Examples:
- "桌面/文件.txt" -> the user's real Desktop
- "下载/报告.pdf" -> the user's real Downloads folder
- "文档/笔记.md" -> the user's real Documents folder
- Single filename like "test.txt" -> defaults to Documents folder
- "documents/..." -> project sandbox directory (backward compatible)

For normal requests, assist the user as usual."""
        })

        # Add knowledge if available
        if knowledge:
            messages.append({
                "role": "system",
                "content": f"Relevant knowledge: {' '.join(knowledge)}"
            })

        # Add history
        for msg in context.history[-5:]:  # Last 5 messages
            messages.append(msg)

        # Add current query
        messages.append({
            "role": "user",
            "content": context.current_query
        })

        # Add observation if available
        if observation:
            messages.append({
                "role": "system",
                "content": f"Tool result: {observation.result}"
            })

        return messages

    def format_response(self, content: str, include_thoughts: bool = False) -> str:
        """Format response for output."""
        if include_thoughts:
            return f"[Thought Process]\n{content}"
        return content

    def reset_plan(self):
        """Reset the current task plan and ReAct state."""
        self.current_plan = []
        self.completed_steps = []
        self.iteration_count = 0
        self.react_engine.reset()
        self.session_context = None

    def _translate_error(self, observation: Observation) -> str:
        """Translate L5 error to user-friendly Chinese message."""
        return self.error_translator.translate(observation)

    def _handle_confirmation(self, user_response: str) -> Union[str, AgentAction]:
        """Handle user confirmation response for pending operations."""
        if not self.pending_confirmation:
            return "没有待处理的操作"

        confirmation_keywords = ["是", "创建", "好", "yes", "y", "确定"]
        cancel_keywords = ["否", "不", "取消", "no", "n", "算了"]

        user_lower = user_response.lower()

        if any(kw in user_lower for kw in confirmation_keywords):
            pending = self.pending_confirmation
            self.pending_confirmation = None

            if pending["action"] == "file_writer":
                return AgentAction(
                    action="file_writer",
                    action_input={"path": pending["path"], "content": pending.get("content", "")},
                    thought="User confirmed directory creation, proceeding with file operation"
                )
            elif pending["action"] == "file_reader":
                return AgentAction(
                    action="file_reader",
                    action_input={"path": pending["path"]},
                    thought="User confirmed directory creation, proceeding with file read"
                )
            else:
                return f"未知的操作类型: {pending['action']}"

        elif any(kw in user_lower for kw in cancel_keywords):
            self.pending_confirmation = None
            return "已取消操作"
        else:
            return '请回复"是"创建目录并继续，或"否"取消操作'


class SecurityGuard:
    """L3 安全判断组件

    对用户请求进行安全分类（正常/敏感/恶意/高危）。
    作为L3入口强制守卫，必须在ReActEngine/TaskPlanner之前执行。
    """

    CLASSIFICATIONS = {"normal", "sensitive", "malicious", "high-risk"}

    KEYWORD_RULES = [
        ("malicious", ["格式化", "format", "删系统文件", "病毒", "virus", "木马", "trojan", "黑客", "hack", "破解", "crack"]),
        ("high-risk", ["删除", "delete", "清空", "删掉", "全部删除", "覆盖", "overwrite"]),
        ("sensitive", ["薪资", "salary", "工资", "密码", "password", "身份证号"]),
    ]

    def __init__(self, llm_manager: LLMManager = None):
        self.llm_manager = llm_manager

    def classify(self, request: str) -> str:
        """对请求进行安全分类

        策略: 关键词规则优先 → LLM分类 → fallback到normal

        Args:
            request: 用户请求文本

        Returns:
            安全分类: normal / sensitive / malicious / high-risk
        """
        # Step 1: 关键词规则快速分类
        keyword_result = self._classify_by_keywords(request)
        if keyword_result:
            return keyword_result

        # Step 2: LLM分类（如果配置了LLMManager）
        if self.llm_manager:
            llm_result = self._classify_by_llm(request)
            if llm_result in self.CLASSIFICATIONS:
                return llm_result

        # Step 3: fallback
        return "normal"

    def _classify_by_keywords(self, request: str) -> str:
        """基于关键词的分类回退逻辑。"""
        request_lower = request.lower()
        for category, keywords in self.KEYWORD_RULES:
            for kw in keywords:
                if kw.lower() in request_lower:
                    return category
        return None

    def _classify_by_llm(self, request: str) -> str:
        """基于LLM的安全分类。"""
        prompt = f"""You are a security classifier for an AI assistant. Classify the following user request into one of four categories:

Categories:
- normal: Regular user requests (file read, query, calculation, advice, create new files)
- sensitive: Involves privacy or sensitive data (salary files, encrypted docs, personal info)
- malicious: Clearly harmful system operations that the user wants the AI to perform (format disk, delete system files, create malware, hacking, attack systems)
- high-risk: User-initiated operations on their own data that may cause data loss (delete their own files, clear their own folders, overwrite their own existing files)

Critical distinctions:
- "high-risk" vs "malicious":
  * high-risk = user managing their OWN files/data (e.g., "delete my desktop files", "clear my downloads folder")
  * malicious = attacking the SYSTEM or creating harm (e.g., "format C drive", "create a virus", "hack a website")
- "normal" vs "high-risk":
  * normal = reading, creating NEW files, giving advice, calculating
  * high-risk = deleting, overwriting EXISTING files, batch clearing folders

Examples:
- "帮我整理桌面建议" -> normal
- "删除我桌面的旧文件" -> high-risk
- "格式化硬盘" -> malicious
- "帮我写个病毒" -> malicious
- "打开我的薪资表" -> sensitive
- "1+1等于几" -> normal
- "覆盖已有的报告.docx" -> high-risk

Rules:
1. "high-risk" is for legitimate user operations that need confirmation, NOT for malicious attacks
2. Do NOT upgrade low-risk requests to high-risk
3. File creation on NEW paths is "normal"
4. File creation on EXISTING paths (overwrite) is "high-risk"
5. Requests to delete user files or clear folders are "high-risk", not "malicious"
6. Advice/suggestions about organizing files are "normal", even if they mention "delete" in the context of advice

User request: {request}

Respond with ONLY one word: normal, sensitive, malicious, or high-risk"""

        messages = [
            {"role": "user", "content": prompt}
        ]
        try:
            response = self.llm_manager.complete(messages, temperature=0.1)
            if isinstance(response, AgentAction):
                return "normal"
            result = response.strip().lower()
            # Extract classification word from response
            for cls in self.CLASSIFICATIONS:
                if cls in result:
                    return cls
            return "normal"
        except Exception:
            return "normal"

    def get_canned_response(self, scenario: str) -> str:
        """获取固定拒绝话术

        Args:
            scenario: 拒绝场景标识

        Returns:
            固定拒绝文本
        """
        responses = {
            "malicious_system_attack": "这种操作太危险了，可能会毁掉您的电脑数据，我绝对不能这么做！",
            "wechat_forward": "抱歉，我无法代您发送微信消息或冒充您联系他人。如果您需要发送消息，请直接使用微信应用操作。",
            "sensitive_content": "抱歉，我不支持搜索此类内容哦，换个话题吧？",
            "permission_denied": "抱歉，您没有权限执行此操作。如需授权，请联系管理员。",
        }
        return responses.get(scenario, "请求被拒绝")


class ToolCaller:
    """L3 工具调用器

    与L5交互执行工具，负责按顺序调用L5内部组件完成工具执行。
    """

    def __init__(self, tools: ToolsInterface = None):
        self.tools = tools or ToolsCapabilities()

    def call_tool(self, action: AgentAction, user_permissions: list = None) -> Observation:
        """调用工具并返回Observation

        Args:
            action: 包含工具名称和参数的AgentAction
            user_permissions: 用户权限列表

        Returns:
            工具执行结果Observation
        """
        try:
            result = self.tools.execute(action.action, action.action_input)
            return result
        except Exception as e:
            error_type = type(e).__name__
            return Observation(
                status="error",
                result=str(e),
                execution_time=0.0,
                metadata={
                    "tool_name": action.action,
                    "error_type": error_type,
                    "source": "ToolCaller"
                }
            )

    def format_tools_for_llm(self) -> List[Dict]:
        """格式化工具列表供LLM使用

        Returns:
            OpenAI格式的工具定义列表
        """
        return self.tools.get_available_tools()


class ErrorTranslator:
    """L3 错误转译器

    将L5返回的业务级技术错误转译为用户友好的中文提示，
    并通过L2回流至L1规范化返回。
    """

    TRANSLATIONS = {
        "502 Bad Gateway": "外部服务暂时不可用，请稍后重试",
        "ToolNotFoundError": "系统暂时不支持该工具，请尝试其他方式",
        "FileNotFoundError": "找不到该文件，请确认路径是否正确或文件是否已移动",
        "FileExistsError": "该位置已有同名文件，请选择覆盖、重命名或保存到其他位置",
        "PermissionError": "抱歉，您没有权限执行此操作",
        "TimeoutError": "操作超时了，请稍后重试或简化请求",
    }

    def __init__(self, llm_manager: LLMManager = None):
        self.llm_manager = llm_manager

    def translate(self, observation: Observation) -> str:
        """将Observation中的错误转译为用户友好提示

        策略: 固定映射优先 → LLM转译 → fallback通用提示

        Args:
            observation: 包含错误的Observation

        Returns:
            中文友好错误提示
        """
        if observation.status != "error":
            return observation.result

        error_text = observation.result

        # Step 1: 固定映射
        for key, translated in self.TRANSLATIONS.items():
            if key in error_text:
                return translated

        # Step 2: LLM转译（如果配置了LLMManager）
        if self.llm_manager:
            llm_result = self._translate_by_llm(observation)
            if llm_result:
                return llm_result

        # Step 3: fallback
        return f"操作失败: {error_text}"

    def _translate_by_llm(self, observation: Observation) -> str:
        """使用LLM将未知错误转译为中文友好提示。"""
        error_prompt = f"""The tool execution failed with the following error:

Error details: {observation.result}
Error metadata: {observation.metadata}

Please provide a user-friendly explanation in Chinese of what went wrong.
Keep it concise (1-2 sentences), polite and helpful.
If it's a file not found error, suggest checking the path.
If it's a permission error, explain access is denied.
If it's a timeout, suggest simplifying the request.

Important: Only explain the error, do not provide unrelated information."""

        messages = [
            {"role": "system", "content": "You are a helpful assistant that explains technical errors in simple, friendly Chinese."},
            {"role": "user", "content": error_prompt}
        ]

        try:
            response = self.llm_manager.complete(messages, temperature=0.3)
            if isinstance(response, AgentAction):
                return ""
            return response.strip()
        except Exception:
            return ""
