import json
import urllib.request
import asyncio
import os
import logging
from logging.handlers import RotatingFileHandler
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Set up Logger for ChatBot
log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
os.makedirs(log_dir, exist_ok=True)

chatbot_logger = logging.getLogger("chatbot_api")
chatbot_logger.setLevel(logging.INFO)
if not chatbot_logger.handlers:
    fh = RotatingFileHandler(
        os.path.join(log_dir, "chatbot.log"), maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    fh.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    chatbot_logger.addHandler(fh)


class ChatBot:
    def __init__(
        self,
        provider: str,
        api_key: str,
        model_name: str,
        system_prompt: str,
        temperature: float = 0.7,
        top_k: int = 40,
        top_p: float = 0.9,
        max_tool_rounds: int = 8,
    ):
        self.provider = provider
        self.api_key = api_key
        self.model_name = model_name
        self.system_prompt = system_prompt
        self.temperature = temperature
        self.top_k = top_k
        self.top_p = top_p
        self.max_tool_rounds = max(1, int(max_tool_rounds or 8))

    def send_message(self, messages: list) -> tuple[str, int]:
        chatbot_logger.info(f"--- API CALL START [Provider: {self.provider}, Model: {self.model_name}] ---")
        try:
            if messages:
                first_msg = messages[0].content if hasattr(messages[0], "content") else str(messages[0])
                chatbot_logger.info(f"Input: {first_msg[:200]}...")

            response, tokens = asyncio.run(self.async_send_message(messages))
            chatbot_logger.info(f"Response success. Tokens used: {tokens}")
            chatbot_logger.info(f"Output: {response[:500]}...")
            return response, tokens
        except Exception as e:
            chatbot_logger.error(f"Error in send_message: {str(e)}", exc_info=True)
            raise e
        finally:
            chatbot_logger.info("--- API CALL END ---")

    async def async_send_message(self, messages: list) -> tuple[str, int]:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        tools_script = os.path.join(script_dir, "tools.py")

        server_params = StdioServerParameters(
            command="python",
            args=[tools_script],
        )

        try:
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    mcp_tools_response = await session.list_tools()
                    mcp_tools = mcp_tools_response.tools

                    if self.provider == "gemini":
                        return await self._run_gemini(messages, session, mcp_tools)
                    if self.provider in ["openai", "openrouter"]:
                        return await self._run_openai(messages, session, mcp_tools)
                    raise ValueError(f"Provider '{self.provider}' is not supported.")
        except Exception as e:
            print(f"MCP Fallback/Warning: {e}")
            # Khởi chạy Fallback cơ bản khi MCP Server không chạy được
            if self.provider == "gemini":
                return await self._run_gemini(messages, None, [])
            if self.provider in ["openai", "openrouter"]:
                return await self._run_openai(messages, None, [])
            raise ValueError(f"Provider '{self.provider}' is not supported.")

    def _make_request(self, url: str, payload: dict, headers: dict) -> dict:
        req = urllib.request.Request(url, method="POST", data=json.dumps(payload).encode("utf-8"), headers=headers)
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode())

    async def _run_gemini(self, messages: list, mcp_session, mcp_tools) -> tuple[str, int]:
        """
        Runs Gemini generateContent and loops tool/function calls until completion.

        The loop works like this:
        - Call Gemini
        - If candidate contains functionCall parts -> execute them via MCP -> append functionResponse parts
        - Send updated contents back to Gemini
        - Repeat until no functionCall is returned (or max rounds reached)
        """
        import re

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent?key={self.api_key}"
        headers = {"Content-Type": "application/json"}

        formatted_messages = []
        for message in messages:
            m_role = message.role if hasattr(message, "role") else message.get("role", "user")
            m_content = message.content if hasattr(message, "content") else message.get("content", "")
            role = "model" if m_role in ["assistant", "model", "bot"] else "user"
            formatted_messages.append({"role": role, "parts": [{"text": m_content}]})

        gemini_tools = []
        if mcp_tools:
            gemini_tools.append(
                {
                    "functionDeclarations": [
                        {
                            "name": tool.name,
                            "description": tool.description or "",
                            "parameters": tool.inputSchema,
                        }
                        for tool in mcp_tools
                    ]
                }
            )

        gemini_tools.append({"google_search": {}})

        payload = {
            "systemInstruction": {"parts": [{"text": self.system_prompt}]},
            "contents": formatted_messages,
            "tools": gemini_tools,
            "generationConfig": {"temperature": self.temperature, "topK": self.top_k, "topP": self.top_p},
        }

        total_tokens = 0
        reasoning_list = []
        final_text_parts = []

        for _ in range(self.max_tool_rounds):
            res_data = self._make_request(url, payload, headers)
            total_tokens += res_data.get("usageMetadata", {}).get("totalTokenCount", 0)

            try:
                parts = res_data["candidates"][0]["content"]["parts"]
            except (KeyError, IndexError):
                return "Error: Unexpected response format from Gemini.", total_tokens

            agent_content = ""
            func_calls = []
            for part in parts:
                if "text" in part:
                    agent_content += part["text"]
                if "functionCall" in part:
                    func_calls.append(part["functionCall"])

            think_match = re.search(r"<think>(.*?)</think>", agent_content, re.DOTALL)
            if think_match:
                reasoning_list.append(think_match.group(1).strip())
                agent_content = re.sub(r"<think>.*?</think>", "", agent_content, flags=re.DOTALL).strip()

            if agent_content:
                final_text_parts.append(agent_content)

            if not func_calls:
                break

            formatted_messages.append({"role": "model", "parts": parts})

            function_responses = []
            for func_call in func_calls:
                func_name = func_call.get("name", "")
                func_args = func_call.get("args", {}) or {}

                if mcp_session:
                    try:
                        result = await mcp_session.call_tool(func_name, arguments=func_args)
                        tool_output = result.content[0].text if result.content else "Success"
                    except Exception as e:
                        tool_output = f"Error: {str(e)}"
                else:
                    tool_output = "Error: MCP session is not active."

                function_responses.append(
                    {"functionResponse": {"name": func_name, "response": {"result": tool_output}}}
                )

            formatted_messages.append({"role": "function", "parts": function_responses})
            payload["contents"] = formatted_messages

        combined_reasoning = "\n\n".join([r for r in reasoning_list if r]).strip()
        final_text = "\n\n".join([t for t in final_text_parts if t]).strip()
        if combined_reasoning:
            return f"<think>{combined_reasoning}</think>\n\n{final_text}", total_tokens
        return final_text, total_tokens

    async def _run_openai(self, messages: list, mcp_session, mcp_tools) -> tuple[str, int]:
        """
        Runs OpenAI/OpenRouter Chat Completions API and loops tool calls until completion.

        The loop works like this:
        - Call /chat/completions with tools
        - If assistant message contains tool_calls -> execute them via MCP -> append tool messages
        - Re-call the model with the expanded conversation
        - Repeat until no tool_calls are returned (or max rounds reached)
        """
        import re

        endpoint = (
            "https://api.openai.com/v1/chat/completions"
            if self.provider == "openai"
            else "https://openrouter.ai/api/v1/chat/completions"
        )

        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        if self.provider == "openrouter":
            headers["HTTP-Referer"] = "http://localhost:8765"
            headers["X-Title"] = "Locked App"

        formatted_messages = []
        for message in messages:
            m_role = message.role if hasattr(message, "role") else message.get("role", "user")
            m_content = message.content if hasattr(message, "content") else message.get("content", "")
            role = "assistant" if m_role in ["assistant", "model", "bot"] else "user"
            formatted_messages.append({"role": role, "content": m_content})

        openai_tools = [
            {
                "type": "function",
                "function": {"name": tool.name, "description": tool.description or "", "parameters": tool.inputSchema},
            }
            for tool in mcp_tools
        ]

        payload = {"model": self.model_name, "temperature": self.temperature, "top_p": self.top_p}

        total_tokens = 0
        reasoning_list = []
        final_text_parts = []

        for _ in range(self.max_tool_rounds):
            payload["messages"] = [{"role": "system", "content": self.system_prompt}] + formatted_messages
            if openai_tools:
                payload["tools"] = openai_tools

            res_data = self._make_request(endpoint, payload, headers)
            total_tokens += res_data.get("usage", {}).get("total_tokens", 0)

            try:
                response_msg = res_data["choices"][0]["message"]
            except (KeyError, IndexError):
                return "Error: Unexpected response format from OpenAI/OpenRouter.", total_tokens

            response_msg.setdefault("role", "assistant")

            if response_msg.get("reasoning"):
                reasoning_list.append(response_msg.get("reasoning"))

            agent_content = response_msg.get("content") or ""
            think_match = re.search(r"<think>(.*?)</think>", agent_content, re.DOTALL)
            if think_match:
                reasoning_list.append(think_match.group(1).strip())
                agent_content = re.sub(r"<think>.*?</think>", "", agent_content, flags=re.DOTALL).strip()

            formatted_messages.append(response_msg)
            if agent_content:
                final_text_parts.append(agent_content)

            tool_calls = response_msg.get("tool_calls") or []
            if not tool_calls:
                break

            for tool_call in tool_calls:
                func_name = tool_call.get("function", {}).get("name", "")
                args_str = tool_call.get("function", {}).get("arguments", "")
                try:
                    func_args = json.loads(args_str) if args_str else {}
                except Exception:
                    func_args = {}

                if mcp_session:
                    try:
                        result = await mcp_session.call_tool(func_name, arguments=func_args)
                        tool_output = result.content[0].text if result.content else "Success"
                    except Exception as e:
                        tool_output = f"Error executing tool: {str(e)}"
                else:
                    tool_output = "Error: MCP session is not active."

                formatted_messages.append(
                    {"role": "tool", "tool_call_id": tool_call.get("id", ""), "content": tool_output}
                )

        combined_reasoning = "\n\n".join([r for r in reasoning_list if r]).strip()
        final_text = "\n\n".join([t for t in final_text_parts if t]).strip()
        if combined_reasoning:
            return f"<think>{combined_reasoning}</think>\n\n{final_text}", total_tokens
        return final_text, total_tokens
