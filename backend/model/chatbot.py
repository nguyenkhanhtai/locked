import json
import urllib.request
import asyncio
import os
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
class ChatBot:
    def __init__(self, provider: str, api_key: str, model_name: str, system_prompt: str, temperature: float = 0.7, top_k: int = 40, top_p: float = 0.9):
        self.provider = provider
        self.api_key = api_key
        self.model_name = model_name
        self.system_prompt = system_prompt
        self.temperature = temperature
        self.top_k = top_k
        self.top_p = top_p

    def send_message(self, messages: list) -> tuple[str, int]:
        # Chạy logic MCP Agent trong một Event Loop để tương thích với luồng đồng bộ hiện hành
        return asyncio.run(self.async_send_message(messages))

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
                    elif self.provider in ["openai", "openrouter"]:
                        return await self._run_openai(messages, session, mcp_tools)
                    else:
                        raise ValueError(f"Provider '{self.provider}' is not supported.")
        except Exception as e:
            print(f"MCP Fallback/Warning: {e}")
            # Khởi chạy Fallback cơ bản khi MCP Server không chạy được
            if self.provider == "gemini":
                return await self._run_gemini(messages, None, [])
            elif self.provider in ["openai", "openrouter"]:
                return await self._run_openai(messages, None, [])
            else:
                raise ValueError(f"Provider '{self.provider}' is not supported.")

    def _make_request(self, url: str, payload: dict, headers: dict) -> dict:
        req = urllib.request.Request(url, method="POST", data=json.dumps(payload).encode("utf-8"), headers=headers)
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode())

    async def _run_gemini(self, messages: list, mcp_session, mcp_tools) -> tuple[str, int]:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent?key={self.api_key}"
        headers = {"Content-Type": "application/json"}
        
        formatted_messages = []
        for message in messages:
            role = "model" if message["role"] in ["assistant", "model", "bot"] else "user"
            formatted_messages.append({"role": role, "parts": [{"text": message["content"]}]})

        gemini_tools = []
        if mcp_tools:
            gemini_tools.append({
                "functionDeclarations": [
                    {
                        "name": tool.name,
                        "description": tool.description or "",
                        "parameters": tool.inputSchema
                    }
                    for tool in mcp_tools
                ]
            })
            
        gemini_tools.append({"google_search": {}})

        payload = {
            "systemInstruction": {"parts": [{"text": self.system_prompt}]},
            "contents": formatted_messages,
            "tools": gemini_tools,
            "generationConfig": {
                "temperature": self.temperature,
                "topK": self.top_k,
                "topP": self.top_p
            }
        }

        res_data = self._make_request(url, payload, headers)
        total_tokens = res_data.get("usageMetadata", {}).get("totalTokenCount", 0)
        try:
            parts = res_data["candidates"][0]["content"]["parts"]
        except (KeyError, IndexError):
            return "Error: Unexpected response format from Gemini.", total_tokens

        import re
        agent_content = ""
        func_calls = []
        
        for part in parts:
            if "text" in part:
                agent_content += part["text"]
            if "functionCall" in part:
                func_calls.append(part["functionCall"])

        reasoning_list = []
        think_match = re.search(r'<think>(.*?)</think>', agent_content, re.DOTALL)
        if think_match:
            reasoning_list.append(think_match.group(1).strip())
            agent_content = re.sub(r'<think>.*?</think>', '', agent_content, flags=re.DOTALL).strip()

        print(f"Gemini model Answer: {parts}")
        print(f"Gemini model Thought: {agent_content}")
        # LLM Request gọi function
        if func_calls:
            formatted_messages.append({
                "role": "model",
                "parts": parts
            })
            
            function_responses = []
            for func_call in func_calls:
                func_name = func_call["name"]
                func_args = func_call.get("args", {})
                
                if mcp_session:
                    try:
                        result = await mcp_session.call_tool(func_name, arguments=func_args)
                        tool_output = result.content[0].text if result.content else "Success"
                    except Exception as e:
                        tool_output = f"Error: {str(e)}"
                else:
                    tool_output = "Error: MCP session is not active."
                
                function_responses.append({
                    "functionResponse": {
                        "name": func_name,
                        "response": {"result": tool_output}
                    }
                })
                
            formatted_messages.append({
                "role": "function",
                "parts": function_responses
            })
            
            payload["contents"] = formatted_messages
            res_data = self._make_request(url, payload, headers)
            total_tokens += res_data.get("usageMetadata", {}).get("totalTokenCount", 0)
        
            try:
                final_parts = res_data["candidates"][0]["content"]["parts"]
                final_text = "".join([p.get("text", "") for p in final_parts])
                
                final_think_match = re.search(r'<think>(.*?)</think>', final_text, re.DOTALL)
                if final_think_match:
                    reasoning_list.append(final_think_match.group(1).strip())
                    final_text = re.sub(r'<think>.*?</think>', '', final_text, flags=re.DOTALL).strip()
            except (KeyError, IndexError):
                final_text = "Error getting final response."
                
            if agent_content:
                final_text = agent_content + "\n\n" + final_text
                
            combined_reasoning = "\n\n".join(reasoning_list).strip()
            if combined_reasoning:
                return f"<think>{combined_reasoning}</think>\n\n{final_text}", total_tokens
            return final_text, total_tokens
        
        combined_reasoning = "\n\n".join(reasoning_list).strip()
        if combined_reasoning:
            return f"<think>{combined_reasoning}</think>\n\n{agent_content}", total_tokens
        return agent_content, total_tokens

    async def _run_openai(self, messages: list, mcp_session, mcp_tools) -> tuple[str, int]:
        endpoint = "https://api.openai.com/v1/chat/completions" if self.provider == "openai" else "https://openrouter.ai/api/v1/chat/completions"
        
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        if self.provider == "openrouter":
            headers["HTTP-Referer"] = "http://localhost:8765"
            headers["X-Title"] = "Locked App"

        formatted_messages = []
        for message in messages:
            role = "assistant" if message["role"] in ["assistant", "model", "bot"] else "user"
            formatted_messages.append({"role": role, "content": message["content"]})

        openai_tools = [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description or "",
                    "parameters": tool.inputSchema
                }
            }
            for tool in mcp_tools
        ]

        payload = {
            "model": self.model_name, 
            "messages": [{"role": "system", "content": self.system_prompt}] + formatted_messages,
            "temperature": self.temperature,
            "top_p": self.top_p
        }
        if openai_tools:
            payload["tools"] = openai_tools

        res_data = self._make_request(endpoint, payload, headers)
        total_tokens = res_data.get("usage", {}).get("total_tokens", 0)
        try:
            response_msg = res_data["choices"][0]["message"]
        except (KeyError, IndexError):
            return "Error: Unexpected response format from OpenAI/OpenRouter."
            
        reasoning_list = []
        if response_msg.get("reasoning"):
            reasoning_list.append(response_msg.get("reasoning"))

        # Kiểm tra xem có thẻ <think> trong content không
        agent_content = response_msg.get("content") or ""
        import re
        think_match = re.search(r'<think>(.*?)</think>', agent_content, re.DOTALL)
        if think_match:
            reasoning_list.append(think_match.group(1).strip())
            agent_content = re.sub(r'<think>.*?</think>', '', agent_content, flags=re.DOTALL).strip()

        # LLM Request gọi function
        if "tool_calls" in response_msg and response_msg["tool_calls"]:
            # Xóa các tool_calls khỏi payload sau khi đã xử lý (chỉ để append vào format)
            # Thêm message của bot
            formatted_messages.append(response_msg)
            
            for tool_call in response_msg["tool_calls"]:
                func_name = tool_call["function"]["name"]
                args_str = tool_call["function"]["arguments"]
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
                
                formatted_messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "content": tool_output
                })
            
            payload["messages"] = [{"role": "system", "content": self.system_prompt}] + formatted_messages
            if "tools" in payload:
                del payload["tools"]
            res_data = self._make_request(endpoint, payload, headers)
            total_tokens += res_data.get("usage", {}).get("total_tokens", 0)
            
            try:
                final_msg = res_data["choices"][0]["message"]
                final_text = final_msg.get("content") or ""
                if final_msg.get("reasoning"):
                    reasoning_list.append(final_msg.get("reasoning"))
                final_think_match = re.search(r'<think>(.*?)</think>', final_text, re.DOTALL)
                if final_think_match:
                    reasoning_list.append(final_think_match.group(1).strip())
                    final_text = re.sub(r'<think>.*?</think>', '', final_text, flags=re.DOTALL).strip()
            except (KeyError, IndexError):
                final_text = "Error getting final response."
                
            if agent_content:
                final_text = agent_content + "\n\n" + final_text
                
            combined_reasoning = "\n\n".join(reasoning_list).strip()
            if combined_reasoning:
                return f"<think>{combined_reasoning}</think>\n\n{final_text}", total_tokens
            return final_text, total_tokens
            
        combined_reasoning = "\n\n".join(reasoning_list).strip()
        if combined_reasoning:
            return f"<think>{combined_reasoning}</think>\n\n{agent_content}", total_tokens
        return agent_content, total_tokens
