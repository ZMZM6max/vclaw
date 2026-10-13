"""
VClaw 端到端测试框架
====================
使用六个大模型分别模拟L1-L6层，进行端到端测试。

功能：
1. 顺序调用六个大模型
2. 传递上下文数据
3. 收集每一层的处理过程和输出
4. 保存结果到mock文件夹
"""

import json
import os
import sys
import time
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional, Callable
from pathlib import Path
from dataclasses import dataclass, field

# 导入提示词和协议
from layer_prompts import LAYER_PROMPTS, LAYER_IO_TYPES
from layer_protocol import (
    LayerStatus, ErrorCode,
    L1Output, L2Output, L3Output, L4SearchOutput, L5Output, L6Output,
    StandardEvent, SessionContext, AgentAction, Observation, ExecutionResult,
    LayerConnectionProtocol
)

# 尝试导入真实L4实现（优雅降级）
# 确保 repo root 在 sys.path 中，以便从 src.l4 导入
_repo_root = Path(__file__).parent.parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

try:
    from src.l4.config.l4_config import get_l4_memory_development
    L4_AVAILABLE = True
except ImportError:
    L4_AVAILABLE = False
    get_l4_memory_development = None


# =============================================================================
# 数据类定义
# =============================================================================
@dataclass
class LayerExecutionResult:
    """单层执行结果"""
    layer_name: str
    input_data: Dict[str, Any]
    output_data: Dict[str, Any]
    processing_log: List[str]
    execution_time: float
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    error: Optional[str] = None


@dataclass
@dataclass
class LayerTransferData:
    """层间传输数据"""
    from_layer: str
    to_layer: str
    data_type: str  # 数据类型描述
    data: Dict[str, Any]
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class EndToEndResult:
    """端到端执行结果"""
    request_id: str
    start_time: str
    end_time: Optional[str] = None
    layer_results: List[LayerExecutionResult] = field(default_factory=list)
    layer_transfers: List[LayerTransferData] = field(default_factory=list)
    final_response: Optional[str] = None
    status: str = "running"  # running, completed, failed
    error_message: Optional[str] = None


# =============================================================================
# LLM调用接口（支持真实API）
# =============================================================================
class LLMClient:
    """
    LLM客户端 - 支持OpenAI, Anthropic Claude, Kimi(Moonshot)
    """

    # 支持的模型提供商
    PROVIDER_OPENAI = "openai"
    PROVIDER_ANTHROPIC = "anthropic"
    PROVIDER_MOONSHOT = "moonshot"

    def __init__(
        self,
        model_name: str,
        api_key: Optional[str] = None,
        provider: Optional[str] = None,
        base_url: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 2000,
        timeout: int = 60
    ):
        """
        初始化LLM客户端

        Args:
            model_name: 模型名称 (如 gpt-4, claude-3-opus, moonshot-v1-8k)
            api_key: API密钥
            provider: 提供商 (openai/anthropic/moonshot)，自动检测
            base_url: 自定义API基础URL
            temperature: 温度参数 (0-1)
            max_tokens: 最大token数
            timeout: 请求超时时间（秒）
        """
        self.model_name = model_name
        self.api_key = api_key
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.base_url = base_url

        # 自动检测提供商
        if provider:
            self.provider = provider
        else:
            self.provider = self._detect_provider(model_name)

        # 初始化客户端
        self._client = None

    def _detect_provider(self, model_name: str) -> str:
        """根据模型名称检测提供商"""
        model_lower = model_name.lower()

        if any(x in model_lower for x in ["gpt", "text-embedding"]):
            return self.PROVIDER_OPENAI
        elif any(x in model_lower for x in ["claude"]):
            return self.PROVIDER_ANTHROPIC
        elif any(x in model_lower for x in ["moonshot", "kimi"]):
            return self.PROVIDER_MOONSHOT
        else:
            # 默认使用OpenAI
            return self.PROVIDER_OPENAI

    def _get_client(self):
        """获取或创建API客户端"""
        if self._client is None:
            if self.provider == self.PROVIDER_OPENAI:
                self._client = self._create_openai_client()
            elif self.provider == self.PROVIDER_ANTHROPIC:
                self._client = self._create_anthropic_client()
            elif self.provider == self.PROVIDER_MOONSHOT:
                self._client = self._create_moonshot_client()
            else:
                raise ValueError(f"不支持的提供商: {self.provider}")
        return self._client

    def _create_openai_client(self):
        """创建OpenAI客户端"""
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("请安装OpenAI SDK: pip install openai")

        kwargs = {"api_key": self.api_key}
        if self.base_url:
            kwargs["base_url"] = self.base_url

        return OpenAI(**kwargs)

    def _create_anthropic_client(self):
        """创建Anthropic客户端"""
        try:
            from anthropic import Anthropic
        except ImportError:
            raise ImportError("请安装Anthropic SDK: pip install anthropic")

        kwargs = {"api_key": self.api_key}
        if self.base_url:
            kwargs["base_url"] = self.base_url

        return Anthropic(**kwargs)

    def _create_moonshot_client(self):
        """创建Moonshot(Kimi)客户端"""
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("请安装OpenAI SDK: pip install openai")

        # Moonshot使用OpenAI兼容的API
        kwargs = {
            "api_key": self.api_key,
            "base_url": self.base_url or "https://api.moonshot.cn/v1"
        }

        return OpenAI(**kwargs)

    def _build_prompt(self, system_prompt: str, input_data: Dict[str, Any]) -> str:
        """构建完整提示词"""
        return f"""{system_prompt}

【输入数据】
```json
{json.dumps(input_data, ensure_ascii=False, indent=2)}
```

【要求】
1. 严格按照上述规则处理输入数据
2. 返回格式必须是有效的JSON
3. 必须包含processing_log字段记录处理过程
4. 不要添加任何JSON之外的文本
5. 不要添加Markdown代码块标记（如 ```json），直接返回JSON内容

【输出】
"""

    def _extract_json(self, text: str) -> Dict[str, Any]:
        """从文本中提取JSON"""
        import re

        # 尝试直接解析
        text = text.strip()

        # 移除Markdown代码块标记
        if text.startswith("```"):
            # 找到第一个换行和最后一个```
            lines = text.split("\n")
            if len(lines) > 1:
                # 移除开头的 ```json 或 ```
                if lines[0].strip().startswith("```"):
                    lines = lines[1:]
                # 移除结尾的 ```
                if lines[-1].strip() == "```":
                    lines = lines[:-1]
                text = "\n".join(lines)

        text = text.strip()

        # 尝试解析JSON
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # 尝试查找JSON块
        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        # 尝试修复常见的JSON错误
        try:
            # 移除尾部逗号
            fixed = re.sub(r',(\s*[}\]])', r'\1', text)
            return json.loads(fixed)
        except json.JSONDecodeError:
            pass

        raise ValueError(f"无法从响应中解析JSON: {text[:200]}...")

    def call(self, prompt: str, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        调用LLM模型

        Args:
            prompt: 系统提示词（层次提示词）
            input_data: 输入数据

        Returns:
            Dict: 解析后的JSON响应
        """
        full_prompt = self._build_prompt(prompt, input_data)

        try:
            if self.provider == self.PROVIDER_OPENAI:
                return self._call_openai(full_prompt)
            elif self.provider == self.PROVIDER_ANTHROPIC:
                return self._call_anthropic(full_prompt)
            elif self.provider == self.PROVIDER_MOONSHOT:
                return self._call_moonshot(full_prompt)
            else:
                raise ValueError(f"不支持的提供商: {self.provider}")
        except Exception as e:
            error_msg = str(e)
            # 添加更详细的错误信息
            if "Connection" in error_msg or "connect" in error_msg.lower():
                error_detail = (
                    f"连接错误。请检查:\n"
                    f"  1. 网络连接是否正常\n"
                    f"  2. API地址是否正确: {self.base_url or 'https://api.openai.com/v1'}\n"
                    f"  3. 是否需要设置代理\n"
                    f"  4. API密钥是否有效"
                )
            elif "Authentication" in error_msg or "auth" in error_msg.lower():
                error_detail = "认证失败，请检查API密钥是否正确"
            elif "Rate limit" in error_msg or "rate" in error_msg.lower():
                error_detail = "请求频率超限，请稍后再试"
            else:
                error_detail = error_msg

            return {
                "status": "error",
                "error_code": "LLM_CALL_ERROR",
                "error_message": f"{self.provider} API调用失败: {error_detail}",
                "processing_log": [
                    f"[错误] LLM调用失败",
                    f"[错误] 提供商: {self.provider}",
                    f"[错误] 模型: {self.model_name}",
                    f"[错误] API地址: {self.base_url or 'https://api.openai.com/v1'}",
                    f"[错误] 详情: {error_msg}"
                ]
            }

    def _call_openai(self, prompt: str) -> Dict[str, Any]:
        """调用OpenAI API"""
        client = self._get_client()

        response = client.chat.completions.create(
            model=self.model_name,
            messages=[
                {"role": "system", "content": "You are a helpful assistant. Always respond with valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            timeout=self.timeout
        )

        result_text = response.choices[0].message.content
        return self._extract_json(result_text)

    def _call_anthropic(self, prompt: str) -> Dict[str, Any]:
        """调用Anthropic Claude API"""
        client = self._get_client()

        response = client.messages.create(
            model=self.model_name,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            system="You are a helpful assistant. Always respond with valid JSON.",
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        result_text = response.content[0].text
        return self._extract_json(result_text)

    def _call_moonshot(self, prompt: str) -> Dict[str, Any]:
        """调用Moonshot(Kimi) API"""
        client = self._get_client()

        response = client.chat.completions.create(
            model=self.model_name,
            messages=[
                {"role": "system", "content": "You are a helpful assistant. Always respond with valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            timeout=self.timeout
        )

        result_text = response.choices[0].message.content
        return self._extract_json(result_text)


# =============================================================================
# 层次模拟器
# =============================================================================
class LayerSimulator:
    """
    层次模拟器
    使用大模型模拟每一层的功能
    """

    def __init__(
        self,
        layer_name: str,
        llm_client: LLMClient,
        output_dir: Path
    ):
        self.layer_name = layer_name
        self.llm_client = llm_client
        self.output_dir = output_dir
        self.prompt = LAYER_PROMPTS[layer_name]
        self.protocol = LayerConnectionProtocol()

    def execute(self, input_data: Dict[str, Any]) -> LayerExecutionResult:
        """
        执行该层的处理

        Args:
            input_data: 输入数据（来自上一层）

        Returns:
            LayerExecutionResult: 执行结果
        """
        start_time = time.time()
        timestamp = datetime.now().isoformat()

        try:
            # 调用LLM模型
            output_data = self.llm_client.call(self.prompt, input_data)

            # 提取处理日志
            processing_log = output_data.get("processing_log", [])

            execution_time = time.time() - start_time

            result = LayerExecutionResult(
                layer_name=self.layer_name,
                input_data=input_data,
                output_data=output_data,
                processing_log=processing_log,
                execution_time=execution_time,
                timestamp=timestamp
            )

            # 保存结果到文件
            self._save_result(result)

            return result

        except Exception as e:
            execution_time = time.time() - start_time
            return LayerExecutionResult(
                layer_name=self.layer_name,
                input_data=input_data,
                output_data={},
                processing_log=[f"错误: {str(e)}"],
                execution_time=execution_time,
                timestamp=timestamp,
                error=str(e)
            )

    def _save_result(self, result: LayerExecutionResult):
        """保存执行结果到文件"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{self.layer_name}_{timestamp}.json"
        filepath = self.output_dir / filename

        data = {
            "layer_name": result.layer_name,
            "timestamp": result.timestamp,
            "execution_time": result.execution_time,
            "input_data": result.input_data,
            "output_data": result.output_data,
            "processing_log": result.processing_log,
            "error": result.error
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


# =============================================================================
# 端到端测试运行器
# =============================================================================
class EndToEndRunner:
    """
    端到端测试运行器
    协调六个层次的LLM模型，完成完整的请求处理流程
    """

    def __init__(
        self,
        llm_configs: Dict[str, Dict[str, str]],
        output_dir: Optional[Path] = None
    ):
        """
        初始化端到端运行器

        Args:
            llm_configs: LLM配置，格式为 {
                "L1": {"model": "gpt-4", "api_key": "xxx"},
                "L2": {"model": "claude-3", "api_key": "xxx"},
                ...
            }
            output_dir: 输出目录
        """
        self.llm_configs = llm_configs
        self.output_dir = output_dir or Path(__file__).parent / "results"
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 创建每层的模拟器
        self.simulators = {}
        for layer_name in ["L1", "L2", "L3", "L4", "L5", "L6"]:
            config = llm_configs.get(layer_name, {})
            if not config:
                print(f"警告: {layer_name} 未配置，将使用默认配置")
                config = {"model": "gpt-4o-mini", "api_key": "", "provider": "openai"}

            llm_client = LLMClient(
                model_name=config.get("model", "gpt-4o-mini"),
                api_key=config.get("api_key", ""),
                provider=config.get("provider"),
                base_url=config.get("base_url"),
                temperature=config.get("temperature", 0.3),
                max_tokens=config.get("max_tokens", 2000)
            )
            self.simulators[layer_name] = LayerSimulator(
                layer_name=layer_name,
                llm_client=llm_client,
                output_dir=self.output_dir
            )

        self.protocol = LayerConnectionProtocol()

        # Initialize real L4 memory layer (mock embedding + in-memory storage)
        if L4_AVAILABLE:
            self.memory = get_l4_memory_development()
        else:
            self.memory = None

    def run(
        self,
        raw_payload: Dict[str, Any],
        request_id: Optional[str] = None
    ) -> EndToEndResult:
        """
        运行端到端测试

        Args:
            raw_payload: 原始输入数据（L1的输入）
            request_id: 请求ID（可选）

        Returns:
            EndToEndResult: 端到端执行结果
        """
        request_id = request_id or f"req_{int(time.time())}"

        # 创建任务专属目录
        task_dir = self.output_dir / request_id
        task_dir.mkdir(parents=True, exist_ok=True)
        print(f"[任务目录] {task_dir}")

        result = EndToEndResult(
            request_id=request_id,
            start_time=datetime.now().isoformat()
        )

        try:
            # ===== L1: 用户接入层 =====
            l1_result = self._run_l1(raw_payload)
            result.layer_results.append(l1_result)
            self._save_layer_result_to_task(l1_result, task_dir)

            if l1_result.output_data.get("status") != "success":
                result.status = "failed"
                result.error_message = f"L1错误: {l1_result.output_data.get('error_message')}"
                return self._finalize_result(result, task_dir)

            standard_event = l1_result.output_data.get("standard_event")

            # Ensure session_id is present for L2 and L4 consistency
            if "session_id" not in standard_event.get("metadata", {}):
                standard_event.setdefault("metadata", {})["session_id"] = str(uuid.uuid4())

            # 记录 L1 -> L2 传输
            result.layer_transfers.append(LayerTransferData(
                from_layer="L1",
                to_layer="L2",
                data_type="StandardEvent",
                data={"standard_event": standard_event}
            ))
            print(f"  [传输] L1 -> L2: StandardEvent (user_id={standard_event.get('user_id')}, content={standard_event.get('content', '')[:30]}...)")

            # ===== L2: 控制网关层 =====
            l2_result, l4_sim_result = self._run_l2(standard_event, task_dir)
            result.layer_results.append(l2_result)
            result.layer_results.append(l4_sim_result)
            self._save_layer_result_to_task(l2_result, task_dir)
            self._save_layer_result_to_task(l4_sim_result, task_dir)

            if l2_result.output_data.get("status") != "success":
                result.status = "failed"
                result.error_message = f"L2错误: {l2_result.output_data.get('error_message')}"
                return self._finalize_result(result, task_dir)

            # L2输出完整的L3输入（包含session_context、available_tools、relevant_memories）
            l3_input = l2_result.output_data.get("l3_input", {})
            session_context = l3_input.get("session_context", {})

            # 记录 L2 -> L3 传输
            result.layer_transfers.append(LayerTransferData(
                from_layer="L2",
                to_layer="L3",
                data_type="L3CompleteInput",
                data={
                    "session_context": session_context,
                    "available_tools_count": len(l3_input.get("available_tools", [])),
                    "relevant_memories_count": len(l3_input.get("relevant_memories", []))
                }
            ))
            print(f"  [传输] L2 -> L3: L3CompleteInput (session_id={session_context.get('session_id')}, query={session_context.get('current_query', '')[:30]}...)")

            # ===== L3: 逻辑编排层 =====
            l3_result = self._run_l3(l3_input)
            result.layer_results.append(l3_result)
            self._save_layer_result_to_task(l3_result, task_dir)

            l3_status = l3_result.output_data.get("status")

            # 如果L3返回直接回复
            if l3_status == "direct_response":
                result.final_response = l3_result.output_data.get("response")
                result.status = "completed"
                # 存储对话
                self._store_conversation(session_context, result.final_response)

                # 添加响应回传链路 L3 -> L2 -> L1 -> User
                # L3 -> L2: 将回复传递给L2更新会话
                result.layer_transfers.append(LayerTransferData(
                    from_layer="L3",
                    to_layer="L2",
                    data_type="ResponseForSession",
                    data={"response": result.final_response, "session_id": session_context.get("session_id")}
                ))
                print(f"  [传输] L3 -> L2: ResponseForSession (session_id={session_context.get('session_id')})")

                # L2 -> L1: 将会话更新后的响应传递给L1
                result.layer_transfers.append(LayerTransferData(
                    from_layer="L2",
                    to_layer="L1",
                    data_type="ResponseWithHistory",
                    data={
                        "response": result.final_response,
                        "session_id": session_context.get("session_id"),
                        "history_updated": True,
                        "history_length": len(session_context.get("history", [])) + 2  # +2 for this Q&A
                    }
                ))
                print(f"  [传输] L2 -> L1: ResponseWithHistory")

                # L1 -> User: 格式化后的最终输出
                result.layer_transfers.append(LayerTransferData(
                    from_layer="L1",
                    to_layer="User",
                    data_type="FinalOutput",
                    data={
                        "channel": standard_event.get("channel"),
                        "user_id": standard_event.get("user_id"),
                        "output": result.final_response,
                        "format": "telegram" if standard_event.get("channel") == "telegram" else "default"
                    }
                ))
                print(f"  [传输] L1 -> User: FinalOutput ({len(result.final_response)} 字符)")

                return self._finalize_result(result, task_dir)

            # 如果需要工具调用
            if l3_status == "action_required":
                agent_action = l3_result.output_data.get("agent_action")
                
                # 路径安全检查与转换（L3输出 → L5输入前）
                if agent_action and agent_action.get("action") in ["file_write", "file_read"]:
                    action_input = agent_action.get("action_input", {})
                    original_path = action_input.get("path", "")
                    sanitized_path = self._sanitize_path(original_path)
                    if original_path != sanitized_path:
                        print(f"  [路径转换] '{original_path}' → '{sanitized_path}'")
                        agent_action["action_input"]["path"] = sanitized_path
                        # 记录转换到processing_log
                        agent_action["_path_sanitized"] = True
                        agent_action["_original_path"] = original_path

                # 记录 L3 -> L5 传输
                result.layer_transfers.append(LayerTransferData(
                    from_layer="L3",
                    to_layer="L5",
                    data_type="AgentAction",
                    data={"agent_action": agent_action}
                ))
                print(f"  [传输] L3 -> L5: AgentAction (action={agent_action.get('action')})")

                # ===== L5: 能力抽象层 =====
                l5_result = self._run_l5(agent_action, session_context)
                result.layer_results.append(l5_result)
                self._save_layer_result_to_task(l5_result, task_dir)

                # 补充L6模拟调用，生成L6.json和component_trace
                # 无论是否实际执行代码，L6都需要记录环境状态
                l6_sim_input = {
                    "operation": "environment_prepare",
                    "action_type": agent_action.get("action"),
                    "action_input": agent_action.get("action_input", {}),
                    "requested_by": "L5",
                    "context": f"Tool execution requested: {agent_action.get('action')}"
                }
                l6_sim_result = self.simulators["L6"].execute(l6_sim_input)
                result.layer_results.append(l6_sim_result)
                self._save_layer_result_to_task(l6_sim_result, task_dir)
                print(f"  [L6] 模拟调用完成，component_trace 已保存")

                l5_status = l5_result.output_data.get("status")

                # 处理高危操作的二次确认
                if l5_status == "confirmation_required":
                    observation = l5_result.output_data.get("observation", {})
                    confirmation_message = observation.get("result", "请确认此操作")

                    # 返回确认请求给用户
                    result.final_response = confirmation_message
                    result.status = "awaiting_confirmation"
                    result.pending_action = agent_action  # 保存待执行的操作

                    # 记录传输
                    result.layer_transfers.append(LayerTransferData(
                        from_layer="L5",
                        to_layer="User",
                        data_type="ConfirmationRequest",
                        data={
                            "message": confirmation_message,
                            "action": agent_action.get("action"),
                            "params": agent_action.get("action_input")
                        }
                    ))
                    print(f"  [传输] L5 -> User: ConfirmationRequest (action={agent_action.get('action')})")
                    print(f"  [状态] 等待用户确认...")

                    return self._finalize_result(result, task_dir)

                if l5_status != "success":
                    result.status = "failed"
                    result.error_message = f"L5错误: {l5_result.output_data.get('error_message')}"
                    return self._finalize_result(result, task_dir)

                observation = l5_result.output_data.get("observation")

                # 如果L5需要调用L6（代码执行）
                if agent_action.get("action") in ["python_repl", "terminal"]:
                    l6_request = self.protocol.l5_to_l6(AgentAction(**agent_action))

                    if l6_request:
                        # 记录 L5 -> L6 传输
                        result.layer_transfers.append(LayerTransferData(
                            from_layer="L5",
                            to_layer="L6",
                            data_type="ExecutionRequest",
                            data={"execution_request": l6_request}
                        ))

                        # ===== L6: 环境执行层 =====
                        l6_result = self._run_l6(l6_request)
                        result.layer_results.append(l6_result)
                        self._save_layer_result_to_task(l6_result, task_dir)

                        if l6_result.output_data.get("status") != "success":
                            result.status = "failed"
                            result.error_message = f"L6错误: {l6_result.output_data.get('error_message')}"
                            return self._finalize_result(result, task_dir)

                        execution_result = l6_result.output_data.get("execution_result", {})

                        # 记录 L6 -> L5 传输
                        result.layer_transfers.append(LayerTransferData(
                            from_layer="L6",
                            to_layer="L5",
                            data_type="ExecutionResult",
                            data={"execution_result": execution_result}
                        ))
                        print(f"  [传输] L6 -> L5: ExecutionResult (exit_code={execution_result.get('exit_code')})")

                        # L6结果返回给L5
                        observation["result"] = execution_result.get("stdout", "")

                # 记录 L5 -> L3 传输
                result.layer_transfers.append(LayerTransferData(
                    from_layer="L5",
                    to_layer="L3",
                    data_type="Observation",
                    data={"observation": observation}
                ))
                print(f"  [传输] L5 -> L3: Observation (status={observation.get('status')})")

                # L3接收Observation，生成最终回复
                l3_input_with_observation = dict(l3_input)
                l3_input_with_observation["observation"] = observation
                l3_input_with_observation["agent_action"] = agent_action
                l3_result_2 = self._run_l3(l3_input_with_observation)
                result.layer_results.append(l3_result_2)
                self._save_layer_result_to_task(l3_result_2, task_dir)

                if l3_result_2.output_data.get("status") == "direct_response":
                    result.final_response = l3_result_2.output_data.get("response")
                else:
                    result.final_response = f"工具执行结果: {observation.get('result', '')}"
                result.status = "completed"
                # 存储对话
                self._store_conversation(session_context, result.final_response)

                # 添加响应回传链路 L3 -> L2 -> L1 -> User (工具执行路径)
                # L3 -> L2: 将工具执行结果传递给L2更新会话
                result.layer_transfers.append(LayerTransferData(
                    from_layer="L3",
                    to_layer="L2",
                    data_type="ToolResultForSession",
                    data={
                        "response": result.final_response,
                        "session_id": session_context.get("session_id"),
                        "tool_used": agent_action.get("action"),
                        "observation": observation.get("result", "")[:200]  # 截断避免太长
                    }
                ))
                print(f"  [传输] L3 -> L2: ToolResultForSession (tool={agent_action.get('action')})")

                # L2 -> L1: 将会话更新后的响应传递给L1
                result.layer_transfers.append(LayerTransferData(
                    from_layer="L2",
                    to_layer="L1",
                    data_type="ResponseWithHistory",
                    data={
                        "response": result.final_response,
                        "session_id": session_context.get("session_id"),
                        "history_updated": True,
                        "tool_executed": True
                    }
                ))
                print(f"  [传输] L2 -> L1: ResponseWithHistory")

                # L1 -> User: 格式化后的最终输出
                result.layer_transfers.append(LayerTransferData(
                    from_layer="L1",
                    to_layer="User",
                    data_type="FinalOutput",
                    data={
                        "channel": standard_event.get("channel"),
                        "user_id": standard_event.get("user_id"),
                        "output": result.final_response,
                        "format": "telegram" if standard_event.get("channel") == "telegram" else "default"
                    }
                ))
                print(f"  [传输] L1 -> User: FinalOutput ({len(result.final_response)} 字符)")

            return self._finalize_result(result, task_dir)

        except Exception as e:
            result.status = "failed"
            result.error_message = f"执行异常: {str(e)}"
            return self._finalize_result(result, task_dir)

    def _run_l1(self, raw_payload: Dict[str, Any]) -> LayerExecutionResult:
        """运行L1层"""
        print("[L1] 用户接入层 - 处理原始输入...")
        return self.simulators["L1"].execute(raw_payload)

    def _run_l2(self, standard_event: Dict[str, Any], task_dir: Path) -> tuple[LayerExecutionResult, LayerExecutionResult]:
        """运行L2层 - 组装完整的L3输入（从L5获取工具定义，从L4获取真实记忆）"""
        print("[L2] 控制网关层 - 限流检查、会话管理与L3输入组装...")
        # L2从L5层获取工具注册表（模拟L5.ToolRegistry.list_tools()）
        all_tools = self._get_l5_tools()

        # 从L4获取真实的对话历史和记忆搜索结果
        user_id = standard_event.get("user_id", "unknown")
        query = standard_event.get("content", "")
        session_id = standard_event.get("metadata", {}).get("session_id", str(uuid.uuid4()))

        real_conversation_history = []
        real_search_results = []
        if self.memory is not None:
            try:
                real_conversation_history = self.memory.retrieve_history(session_id, limit=10)
                real_search_results = self.memory.search(query, top_k=3)
                print(f"  [L4] 历史检索: {len(real_conversation_history)} 条")
                print(f"  [L4] 记忆搜索: {len(real_search_results)} 条")
            except Exception as e:
                print(f"  [L4] 记忆层调用失败: {e}")

        # 补充L4模拟调用，生成独立的L4.json和component_trace
        l4_sim_input = {
            "operation": "retrieve_and_search",
            "session_id": session_id,
            "query": query,
            "history_count": len(real_conversation_history),
            "search_count": len(real_search_results),
            "real_conversation_history": real_conversation_history,
            "real_search_results": real_search_results,
            "context": "L2 requested memory retrieval for L3 input assembly"
        }
        l4_sim_result = self.simulators["L4"].execute(l4_sim_input)
        self._save_layer_result_to_task(l4_sim_result, task_dir)
        print(f"  [L4] 模拟调用完成，component_trace 已保存")

        l2_input = {
            "standard_event": standard_event,
            "client_ip": "127.0.0.1",
            "available_tools_from_l5": all_tools,  # L5层提供的工具定义
            "real_conversation_history": real_conversation_history,
            "real_search_results": real_search_results,
        }
        l2_result = self.simulators["L2"].execute(l2_input)
        return l2_result, l4_sim_result

    def _get_l5_tools(self) -> List[Dict[str, Any]]:
        """获取L5层注册的所有工具定义（模拟L5.ToolRegistry.list_tools()）"""
        return [
            {
                "name": "calculator",
                "description": "数学计算，支持加减乘除和复杂表达式",
                "parameters": {"expression": "string"},
                "required_permission": None  # 无需权限
            },
            {
                "name": "file_read",
                "description": "读取文件内容",
                "parameters": {"path": "string"},
                "required_permission": "file_read"
            },
            {
                "name": "file_write",
                "description": "写入文件内容",
                "parameters": {"path": "string", "content": "string"},
                "required_permission": "file_write"
            },
            {
                "name": "python_repl",
                "description": "执行Python代码，通过L6沙盒安全执行",
                "parameters": {"code": "string"},
                "required_permission": "execute_code"
            },
            {
                "name": "terminal",
                "description": "执行终端命令",
                "parameters": {"command": "string"},
                "required_permission": "execute_command"
            },
            {
                "name": "search_web",
                "description": "搜索网络获取最新信息",
                "parameters": {"query": "string"},
                "required_permission": "web_access"
            }
        ]

    def _run_l3(self, l3_input: Dict[str, Any]) -> LayerExecutionResult:
        """运行L3层 - 直接使用L2组装好的完整输入"""
        print("[L3] 逻辑编排层 - 任务规划与ReAct循环...")
        # L3输入已由L2层完整组装，包含:
        # - session_context: 会话上下文
        # - available_tools: 根据权限筛选的可用工具列表
        # - relevant_memories: 从L4检索的相关记忆
        return self.simulators["L3"].execute(l3_input)

    def _run_l5(
        self,
        agent_action: Dict[str, Any],
        session_context: Dict[str, Any]
    ) -> LayerExecutionResult:
        """运行L5层"""
        print("[L5] 能力抽象层 - 工具路由与参数验证...")
        l5_input = {
            "agent_action": agent_action,
            "user_permissions": session_context.get("user_permissions", []),
            "session_id": session_context.get("session_id", ""),
            "timeout": 30
        }
        return self.simulators["L5"].execute(l5_input)

    def _run_l6(self, execution_request: Dict[str, Any]) -> LayerExecutionResult:
        """运行L6层"""
        print("[L6] 环境执行层 - 沙盒代码执行...")
        return self.simulators["L6"].execute(execution_request)

    def _store_conversation(
        self,
        session_context: Dict[str, Any],
        final_response: str
    ):
        """将本轮对话存储到L4记忆层"""
        if self.memory is None or not session_context:
            return
        session_id = session_context.get("session_id")
        query = session_context.get("current_query", "")
        if not session_id or not query:
            return
        try:
            messages = [
                {"role": "user", "content": query},
                {"role": "assistant", "content": final_response},
            ]
            self.memory.store_conversation(session_id, messages)
            print(f"  [L4] 对话已存储到 session {session_id}")
        except Exception as e:
            print(f"  [L4] 对话存储失败: {e}")

    def _sanitize_path(self, path: str) -> str:
        """
        路径安全检查与转换
        
        将用户友好的路径转换为沙盒安全路径：
        - "桌面/xxx" → "documents/desktop/xxx"
        - "下载/xxx" → "documents/downloads/xxx"
        - "documents/xxx" → "documents/xxx" (已是安全路径，保持不变)
        
        Args:
            path: 原始路径（可能包含中文目录名）
            
        Returns:
            转换后的沙盒安全路径
        """
        if not path:
            return "documents/"
        
        # 如果已经是安全路径，直接返回
        if path.startswith("documents/"):
            return path
        
        # 路径映射表
        path_mappings = {
            "桌面/": "documents/desktop/",
            "桌面": "documents/desktop/",
            "下载/": "documents/downloads/",
            "下载": "documents/downloads/",
            "download/": "documents/downloads/",
            "downloads/": "documents/downloads/",
            "文档/": "documents/",
            "documents/": "documents/",
        }
        
        # 检查并转换路径前缀
        for old_prefix, new_prefix in path_mappings.items():
            if path.startswith(old_prefix):
                return path.replace(old_prefix, new_prefix, 1)
        
        # 如果路径不包含斜杠（只是文件名），默认放入documents/
        if "/" not in path and "\\" not in path:
            return f"documents/{path}"
        
        # 其他情况，强制加上documents/前缀
        return f"documents/{path}"

    def _save_layer_result_to_task(self, layer_result: LayerExecutionResult, task_dir: Path):
        """保存层结果到任务目录"""
        filename = f"{layer_result.layer_name}.json"
        filepath = task_dir / filename

        data = {
            "layer_name": layer_result.layer_name,
            "timestamp": layer_result.timestamp,
            "execution_time": layer_result.execution_time,
            "input_data": layer_result.input_data,
            "output_data": layer_result.output_data,
            "processing_log": layer_result.processing_log,
            "component_trace": layer_result.output_data.get("component_trace", []),
            "error": layer_result.error
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _finalize_result(self, result: EndToEndResult, task_dir: Path) -> EndToEndResult:
        """完成结果记录"""
        result.end_time = datetime.now().isoformat()

        # 保存完整结果
        filename = f"e2e_{result.request_id}.json"
        filepath = task_dir / filename

        data = {
            "request_id": result.request_id,
            "start_time": result.start_time,
            "end_time": result.end_time,
            "status": result.status,
            "error_message": result.error_message,
            "final_response": result.final_response,
            "layer_results": [
                {
                    "layer_name": lr.layer_name,
                    "timestamp": lr.timestamp,
                    "execution_time": lr.execution_time,
                    "processing_log": lr.processing_log,
                    "component_trace": lr.output_data.get("component_trace", []),
                    "error": lr.error
                }
                for lr in result.layer_results
            ],
            "layer_transfers": [
                {
                    "from_layer": lt.from_layer,
                    "to_layer": lt.to_layer,
                    "data_type": lt.data_type,
                    "data": lt.data,
                    "timestamp": lt.timestamp
                }
                for lt in result.layer_transfers
            ]
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        # 同时保存一个专门的层间传输记录文件
        if result.layer_transfers:
            transfer_filename = f"transfers_{result.request_id}.json"
            transfer_filepath = task_dir / transfer_filename
            transfers_data = {
                "request_id": result.request_id,
                "description": "层间数据传输记录",
                "transfers": [
                    {
                        "step": i + 1,
                        "from": lt.from_layer,
                        "to": lt.to_layer,
                        "type": lt.data_type,
                        "timestamp": lt.timestamp,
                        "data": lt.data
                    }
                    for i, lt in enumerate(result.layer_transfers)
                ]
            }
            with open(transfer_filepath, "w", encoding="utf-8") as f:
                json.dump(transfers_data, f, ensure_ascii=False, indent=2)
            print(f"[完成] 层间传输记录已保存到: {transfer_filepath}")

        print(f"\n[完成] 结果已保存到任务目录: {task_dir}")
        print(f"  - 完整结果: {filepath.name}")
        if result.layer_transfers:
            print(f"  - 传输记录: {transfer_filename}")
        return result


# =============================================================================
# 测试用例生成器
# =============================================================================
class TestCaseGenerator:
    """生成端到端测试用例"""

    @staticmethod
    def telegram_message(text: str, user_id: str = "12345") -> Dict[str, Any]:
        """生成Telegram消息格式的测试用例"""
        return {
            "channel": "telegram",
            "raw_data": {
                "update_id": 123456789,
                "message": {
                    "message_id": 1,
                    "from": {"id": user_id, "first_name": "TestUser"},
                    "chat": {"id": user_id, "type": "private"},
                    "date": int(time.time()),
                    "text": text
                }
            },
            "client_ip": "192.168.1.1"
        }

    @staticmethod
    def websocket_message(text: str, user_id: str = "user_123") -> Dict[str, Any]:
        """生成WebSocket消息格式的测试用例"""
        return {
            "channel": "websocket",
            "raw_data": {
                "user_id": user_id,
                "content": text,
                "timestamp": time.time(),
                "metadata": {"client_version": "1.0"}
            },
            "client_ip": "192.168.1.100"
        }

    @staticmethod
    def webhook_message(text: str, user_id: str = "user_456") -> Dict[str, Any]:
        """生成Webhook消息格式的测试用例"""
        return {
            "channel": "webhook",
            "raw_data": {
                "event": "message",
                "payload": {
                    "user_id": user_id,
                    "message": text,
                    "timestamp": time.time()
                }
            },
            "client_ip": "10.0.0.1"
        }


# =============================================================================
# 使用示例
# =============================================================================
def main():
    """
    端到端测试框架使用示例

    注意：运行前需要配置LLM API密钥
    """
    # 配置六个层次的LLM模型
    # 可以混合使用不同厂商的模型
    llm_configs = {
        "L1": {
            "provider": "openai",
            "model": "gpt-4o-mini",
            "api_key": os.getenv("OPENAI_API_KEY", "sk-xxx"),
            "temperature": 0.3
        },
        "L2": {
            "provider": "anthropic",
            "model": "claude-3-haiku-20240307",
            "api_key": os.getenv("ANTHROPIC_API_KEY", "sk-xxx"),
            "temperature": 0.3
        },
        "L3": {
            "provider": "openai",
            "model": "gpt-4o",
            "api_key": os.getenv("OPENAI_API_KEY", "sk-xxx"),
            "temperature": 0.3
        },
        "L4": {
            "provider": "moonshot",
            "model": "moonshot-v1-8k",
            "api_key": os.getenv("MOONSHOT_API_KEY", "sk-xxx"),
            "temperature": 0.3
        },
        "L5": {
            "provider": "anthropic",
            "model": "claude-3-sonnet-20240229",
            "api_key": os.getenv("ANTHROPIC_API_KEY", "sk-xxx"),
            "temperature": 0.3
        },
        "L6": {
            "provider": "openai",
            "model": "gpt-4o-mini",
            "api_key": os.getenv("OPENAI_API_KEY", "sk-xxx"),
            "temperature": 0.3
        },
    }

    # 检查API密钥
    if llm_configs["L1"]["api_key"] == "sk-xxx":
        print("错误: 请设置环境变量 OPENAI_API_KEY 或修改配置文件")
        print("示例: export OPENAI_API_KEY=sk-your-api-key")
        return

    # 创建端到端运行器
    runner = EndToEndRunner(llm_configs)

    # 生成测试用例
    test_cases = [
        TestCaseGenerator.telegram_message("计算Fibonacci(10)"),
        TestCaseGenerator.telegram_message("你好，请介绍一下自己"),
        TestCaseGenerator.websocket_message("帮我写一个Python排序算法"),
    ]

    # 运行端到端测试
    for i, test_case in enumerate(test_cases):
        print(f"\n{'='*60}")
        print(f"测试用例 {i+1}: {test_case['raw_data']['message']['text']}")
        print('='*60)

        result = runner.run(test_case, request_id=f"test_{i+1}")

        print(f"\n状态: {result.status}")
        if result.final_response:
            print(f"最终回复: {result.final_response}")
        if result.error_message:
            print(f"错误: {result.error_message}")


if __name__ == "__main__":
    print("""
VClaw 端到端测试框架
====================

使用说明：
1. 配置每个层次的LLM模型（在llm_configs中设置API密钥）
2. 准备测试用例（使用TestCaseGenerator生成）
3. 运行EndToEndRunner进行测试
4. 查看tests/mock/results/目录下的输出结果

使用方法1 - 使用交互式脚本（推荐）:
    python run_real_llm.py

使用方法2 - 代码中调用:
    from tests.mock import EndToEndRunner, TestCaseGenerator
    runner = EndToEndRunner(llm_configs)
    result = runner.run(test_case)

使用方法3 - 使用配置示例:
    from config_example import CONFIG_HYBRID
    from e2e_framework import EndToEndRunner
    runner = EndToEndRunner(CONFIG_HYBRID)

注意：
- 支持OpenAI, Anthropic Claude, Kimi(Moonshot)
- 可以为不同层次配置不同的大模型
- 每层的处理过程和输出结果会自动保存到mock/results文件夹

依赖安装:
    pip install openai anthropic pydantic
""")
