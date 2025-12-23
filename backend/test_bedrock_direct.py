#!/usr/bin/env python3
"""
Direct integration test for BedrockChatModel.

Run with:
    cd /Users/katz/workspace/open-webui/backend
    python test_bedrock_direct.py

Requires AWS credentials (env vars or IAM role).
"""

import asyncio
import json
import os
import sys

# Add the backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from open_webui.routers.bedrock import BedrockChatModel


async def test_non_streaming():
    """Test non-streaming chat completion."""
    print("\n=== Testing Non-Streaming ===\n")

    region = os.environ.get("AWS_REGION", "us-east-1")
    model = BedrockChatModel(region)

    # List available models
    print("Available models:")
    models = model.list_models()
    for m in models[:5]:  # Show first 5
        print(f"  - {m['id']}")
    if len(models) > 5:
        print(f"  ... and {len(models) - 5} more")

    # Pick a model - use cross-region Sonnet 4.5 if available
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
    """Test streaming chat completion."""
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
        "messages": [
            {"role": "user", "content": "Count from 1 to 5, one number per line."},
        ],
        "max_tokens": 100,
        "stream": True,
    }

    print(f"\nStreaming response:")
    print("-" * 40)

    full_content = ""
    async for chunk in model.chat_stream(payload):
        # Parse SSE data
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
    """Test tool calling support."""
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

    # Define a simple tool
    payload = {
        "model": model_id,
        "messages": [
            {"role": "user", "content": "What's the weather in New York? Use the get_weather tool."},
        ],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "description": "Get the current weather for a location",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "location": {
                                "type": "string",
                                "description": "The city name"
                            }
                        },
                        "required": ["location"]
                    }
                }
            }
        ],
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
    print("Bedrock Router Direct Integration Test")
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
