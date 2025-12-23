#!/usr/bin/env -S uv run
"""
Standalone Bedrock integration test.

Run with:
    uv run /Users/katz/workspace/open-webui/backend/test_bedrock_standalone.py

Or:
    cd /Users/katz/workspace/open-webui/backend
    ./test_bedrock_standalone.py
"""

# /// script
# dependencies = [
#     "boto3>=1.34.0",
#     "pydantic>=2.0.0",
# ]
# ///

import asyncio
import json
import os
import sys
import time
import uuid
from typing import AsyncIterable, Optional

import boto3
from botocore.config import Config as BotoConfig
from pydantic import BaseModel, Field


####################################
# Schema (minimal subset)
####################################


class ResponseFunction(BaseModel):
    name: Optional[str] = None
    arguments: str


class ToolCall(BaseModel):
    index: Optional[int] = None
    id: Optional[str] = None
    type: str = "function"
    function: ResponseFunction


class Usage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatResponseMessage(BaseModel):
    role: Optional[str] = None
    content: Optional[str] = None
    tool_calls: Optional[list[ToolCall]] = None


class Choice(BaseModel):
    index: int
    message: Optional[ChatResponseMessage] = None
    delta: Optional[ChatResponseMessage] = None
    finish_reason: Optional[str] = None


class ChatResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str
    choices: list[Choice]
    usage: Optional[Usage] = None


class ChatStreamResponse(BaseModel):
    id: str
    object: str = "chat.completion.chunk"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str
    choices: list[Choice] = []
    usage: Optional[Usage] = None
    system_fingerprint: Optional[str] = "fp"


####################################
# BedrockChatModel (simplified)
####################################


class BedrockChatModel:
    def __init__(self, region: str):
        self.region = region
        config = BotoConfig(
            connect_timeout=60,
            read_timeout=900,
            retries={'max_attempts': 8, 'mode': 'adaptive'},
            max_pool_connections=50
        )
        self.runtime = boto3.client("bedrock-runtime", region_name=region, config=config)
        self.client = boto3.client("bedrock", region_name=region, config=config)
        self.profile_metadata = {}
        self._refresh_models()

    def _refresh_models(self):
        """Refresh available models including inference profiles."""
        try:
            paginator = self.client.get_paginator('list_inference_profiles')
            for page in paginator.paginate(maxResults=1000, typeEquals="SYSTEM_DEFINED"):
                for profile in page.get("inferenceProfileSummaries", []):
                    profile_id = profile.get("inferenceProfileId")
                    if not profile_id:
                        continue
                    models = profile.get("models", [])
                    if models:
                        model_arn = models[0].get("modelArn", "")
                        if model_arn:
                            self.profile_metadata[profile_id] = {
                                "underlying_model_id": model_arn.split('/')[-1],
                                "profile_type": "SYSTEM_DEFINED",
                            }
        except Exception as e:
            print(f"Warning: Failed to list inference profiles: {e}")

    def list_models(self) -> list[dict]:
        return [{"id": pid, "object": "model", "owned_by": "bedrock"} for pid in self.profile_metadata]

    @staticmethod
    def generate_message_id() -> str:
        return "chatcmpl-" + str(uuid.uuid4())[:8]

    def _parse_messages(self, messages: list[dict]) -> tuple[list[dict], list[dict]]:
        system_prompts = []
        bedrock_messages = []

        for msg in messages:
            role = msg.get("role")
            content = msg.get("content")

            if role == "system":
                if isinstance(content, str):
                    system_prompts.append({"text": content})
            elif role == "user":
                bedrock_messages.append({"role": "user", "content": [{"text": content}]})
            elif role == "assistant":
                if content:
                    bedrock_messages.append({"role": "assistant", "content": [{"text": content}]})
                tool_calls = msg.get("tool_calls")
                if tool_calls:
                    for tc in tool_calls:
                        tool_input = json.loads(tc["function"]["arguments"])
                        bedrock_messages.append({
                            "role": "assistant",
                            "content": [{"toolUse": {"toolUseId": tc["id"], "name": tc["function"]["name"], "input": tool_input}}],
                        })
            elif role == "tool":
                bedrock_messages.append({
                    "role": "user",
                    "content": [{"toolResult": {"toolUseId": msg.get("tool_call_id"), "content": [{"text": content}]}}],
                })

        # Merge consecutive same-role messages
        merged = []
        current_role = None
        current_content = []
        for msg in bedrock_messages:
            if msg["role"] != current_role:
                if current_content:
                    merged.append({"role": current_role, "content": current_content})
                current_role = msg["role"]
                current_content = []
            current_content.extend(msg["content"])
        if current_content:
            merged.append({"role": current_role, "content": current_content})

        return merged, system_prompts

    def _convert_tool_spec(self, func: dict) -> dict:
        return {
            "toolSpec": {
                "name": func.get("name", ""),
                "description": func.get("description", ""),
                "inputSchema": {"json": func.get("parameters", {})}
            }
        }

    def _parse_request(self, payload: dict) -> dict:
        model_id = payload.get("model", "")
        messages = payload.get("messages", [])
        bedrock_messages, system_prompts = self._parse_messages(messages)

        inference_config = {"maxTokens": payload.get("max_tokens", 4096)}
        if payload.get("temperature") is not None:
            inference_config["temperature"] = payload["temperature"]
        if payload.get("top_p") is not None:
            inference_config["topP"] = payload["top_p"]

        args = {"modelId": model_id, "messages": bedrock_messages, "inferenceConfig": inference_config}
        if system_prompts:
            args["system"] = system_prompts

        tools = payload.get("tools")
        if tools:
            tool_config = {"tools": [self._convert_tool_spec(t.get("function", t)) for t in tools]}
            tool_choice = payload.get("tool_choice")
            if tool_choice == "required":
                tool_config["toolChoice"] = {"any": {}}
            elif tool_choice:
                tool_config["toolChoice"] = {"auto": {}}
            args["toolConfig"] = tool_config

        return args

    def _convert_finish_reason(self, reason: str) -> str:
        return {"end_turn": "stop", "stop_sequence": "stop", "max_tokens": "length", "tool_use": "tool_calls"}.get(reason, reason)

    async def chat(self, payload: dict) -> ChatResponse:
        args = self._parse_request(payload)
        response = self.runtime.converse(**args)

        output_message = response["output"]["message"]
        usage = response["usage"]
        finish_reason = response["stopReason"]

        message = ChatResponseMessage(role="assistant")
        if finish_reason == "tool_use":
            tool_calls = []
            for part in output_message["content"]:
                if "toolUse" in part:
                    tool = part["toolUse"]
                    tool_calls.append(ToolCall(id=tool["toolUseId"], function=ResponseFunction(name=tool["name"], arguments=json.dumps(tool["input"]))))
            message.tool_calls = tool_calls
        else:
            for c in output_message["content"]:
                if "text" in c:
                    message.content = c["text"]

        return ChatResponse(
            id=self.generate_message_id(),
            model=payload.get("model", ""),
            choices=[Choice(index=0, message=message, finish_reason=self._convert_finish_reason(finish_reason))],
            usage=Usage(prompt_tokens=usage.get("inputTokens", 0), completion_tokens=usage.get("outputTokens", 0), total_tokens=usage.get("totalTokens", 0)),
        )

    async def chat_stream(self, payload: dict) -> AsyncIterable[bytes]:
        args = self._parse_request(payload)
        response = self.runtime.converse_stream(**args)
        stream = response.get("stream")
        message_id = self.generate_message_id()
        model = payload.get("model", "")

        for chunk in stream:
            stream_response = self._create_stream_response(model, message_id, chunk)
            if stream_response and stream_response.choices:
                data = stream_response.model_dump_json(exclude_unset=True)
                yield f"data: {data}\n\n".encode("utf-8")

        yield b"data: [DONE]\n\n"

    def _create_stream_response(self, model: str, message_id: str, chunk: dict) -> Optional[ChatStreamResponse]:
        message = None
        finish_reason = None

        if "messageStart" in chunk:
            message = ChatResponseMessage(role=chunk["messageStart"]["role"], content="")
        if "contentBlockStart" in chunk:
            delta = chunk["contentBlockStart"]["start"]
            if "toolUse" in delta:
                message = ChatResponseMessage(tool_calls=[ToolCall(index=0, id=delta["toolUse"]["toolUseId"], function=ResponseFunction(name=delta["toolUse"]["name"], arguments=""))])
        if "contentBlockDelta" in chunk:
            delta = chunk["contentBlockDelta"]["delta"]
            if "text" in delta:
                message = ChatResponseMessage(content=delta["text"])
            elif "toolUse" in delta:
                message = ChatResponseMessage(tool_calls=[ToolCall(index=0, function=ResponseFunction(arguments=delta["toolUse"]["input"]))])
        if "messageStop" in chunk:
            message = ChatResponseMessage()
            finish_reason = self._convert_finish_reason(chunk["messageStop"]["stopReason"])

        if message is None:
            return None

        return ChatStreamResponse(id=message_id, model=model, choices=[Choice(index=0, delta=message, finish_reason=finish_reason)])


####################################
# Tests
####################################


async def test_non_streaming():
    print("\n=== Testing Non-Streaming ===\n")

    region = os.environ.get("AWS_REGION", "us-east-1")
    model = BedrockChatModel(region)

    print("Available models:")
    models = model.list_models()
    for m in models[:5]:
        print(f"  - {m['id']}")
    if len(models) > 5:
        print(f"  ... and {len(models) - 5} more")

    model_id = None
    for m in models:
        if "claude-sonnet-4-5" in m["id"]:
            model_id = m["id"]
            break
    if not model_id and models:
        model_id = models[0]["id"]

    if not model_id:
        print("\nNo models available. Check AWS credentials and region.")
        return

    print(f"\nUsing model: {model_id}")

    payload = {
        "model": model_id,
        "messages": [
            {"role": "system", "content": "You are a helpful assistant. Be concise."},
            {"role": "user", "content": "What is 2 + 2? Answer in one word."},
        ],
        "max_tokens": 100,
        "temperature": 0.0,
    }

    print(f"\nSending request...")
    response = await model.chat(payload)

    print(f"\nResponse:")
    print(f"  ID: {response.id}")
    print(f"  Model: {response.model}")
    print(f"  Content: {response.choices[0].message.content}")
    print(f"  Finish reason: {response.choices[0].finish_reason}")
    if response.usage:
        print(f"  Tokens: {response.usage.prompt_tokens} prompt, {response.usage.completion_tokens} completion")


async def test_streaming():
    print("\n=== Testing Streaming ===\n")

    region = os.environ.get("AWS_REGION", "us-east-1")
    model = BedrockChatModel(region)

    models = model.list_models()
    model_id = None
    for m in models:
        if "claude-sonnet-4-5" in m["id"]:
            model_id = m["id"]
            break
    if not model_id and models:
        model_id = models[0]["id"]

    if not model_id:
        print("No models available.")
        return

    print(f"Using model: {model_id}")

    payload = {
        "model": model_id,
        "messages": [{"role": "user", "content": "Count from 1 to 5, one number per line."}],
        "max_tokens": 100,
    }

    print(f"\nStreaming response:")
    print("-" * 40)

    full_content = ""
    async for chunk in model.chat_stream(payload):
        chunk_str = chunk.decode("utf-8")
        if chunk_str.startswith("data: "):
            data = chunk_str[6:].strip()
            if data == "[DONE]":
                break
            try:
                parsed = json.loads(data)
                if parsed.get("choices"):
                    delta = parsed["choices"][0].get("delta", {})
                    content = delta.get("content", "")
                    if content:
                        print(content, end="", flush=True)
                        full_content += content
            except json.JSONDecodeError:
                pass

    print("\n" + "-" * 40)
    print(f"\nFull content: {repr(full_content)}")


async def test_tool_calling():
    print("\n=== Testing Tool Calling ===\n")

    region = os.environ.get("AWS_REGION", "us-east-1")
    model = BedrockChatModel(region)

    models = model.list_models()
    model_id = None
    for m in models:
        if "claude-sonnet-4-5" in m["id"]:
            model_id = m["id"]
            break
    if not model_id and models:
        model_id = models[0]["id"]

    if not model_id:
        print("No models available.")
        return

    print(f"Using model: {model_id}")

    payload = {
        "model": model_id,
        "messages": [{"role": "user", "content": "What's the weather in New York? Use the get_weather tool."}],
        "tools": [{
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get the current weather for a location",
                "parameters": {
                    "type": "object",
                    "properties": {"location": {"type": "string", "description": "The city name"}},
                    "required": ["location"]
                }
            }
        }],
        "max_tokens": 500,
    }

    print(f"\nSending request with tool...")
    response = await model.chat(payload)

    print(f"\nResponse:")
    print(f"  Finish reason: {response.choices[0].finish_reason}")

    message = response.choices[0].message
    if message.tool_calls:
        print(f"  Tool calls:")
        for tc in message.tool_calls:
            print(f"    - {tc.function.name}({tc.function.arguments})")
            print(f"      ID: {tc.id}")
    else:
        print(f"  Content: {message.content}")


async def main():
    print("=" * 50)
    print("Bedrock Router Standalone Integration Test")
    print("=" * 50)

    try:
        await test_non_streaming()
        await test_streaming()
        await test_tool_calling()
        print("\n" + "=" * 50)
        print("All tests completed!")
        print("=" * 50)
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
