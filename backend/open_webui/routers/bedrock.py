"""
AWS Bedrock Router for OpenWebUI

Native Bedrock integration using AWS Converse API.
Provides OpenAI-compatible endpoints for chat completions.

This router enables tool calling support for Bedrock models,
which was not possible with the pipe-based approach.
"""

import json
import logging
import time
import uuid
from typing import AsyncIterable, Optional

import boto3
from botocore.config import Config as BotoConfig
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from open_webui.models.models import Models
from open_webui.models.users import UserModel
from open_webui.utils.auth import get_admin_user, get_verified_user
from open_webui.utils.access_control import has_access
from open_webui.env import SRC_LOG_LEVELS, BYPASS_MODEL_ACCESS_CONTROL


log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS.get("BEDROCK", logging.INFO))


router = APIRouter()


####################################
# Boto3 Client Configuration
####################################


def get_bedrock_clients(region: str):
    """Create Bedrock clients with appropriate configuration."""
    config = BotoConfig(
        connect_timeout=60,
        read_timeout=900,  # 15 minutes for long streaming responses
        retries={
            'max_attempts': 8,
            'mode': 'adaptive'
        },
        max_pool_connections=50
    )

    runtime = boto3.client(
        service_name="bedrock-runtime",
        region_name=region,
        config=config,
    )
    client = boto3.client(
        service_name="bedrock",
        region_name=region,
        config=config,
    )
    return runtime, client


####################################
# Schema Definitions (OpenAI-compatible)
####################################


class ResponseFunction(BaseModel):
    name: Optional[str] = None
    arguments: str


class ToolCall(BaseModel):
    index: Optional[int] = None
    id: Optional[str] = None
    type: str = "function"
    function: ResponseFunction


class Function(BaseModel):
    name: str
    description: Optional[str] = None
    parameters: dict


class Tool(BaseModel):
    type: str = "function"
    function: Function


class StreamOptions(BaseModel):
    include_usage: bool = True


class PromptTokensDetails(BaseModel):
    cached_tokens: int = 0
    audio_tokens: int = 0


class CompletionTokensDetails(BaseModel):
    reasoning_tokens: int = 0
    audio_tokens: int = 0


class Usage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    prompt_tokens_details: Optional[PromptTokensDetails] = None
    completion_tokens_details: Optional[CompletionTokensDetails] = None


class ChatResponseMessage(BaseModel):
    role: Optional[str] = None
    content: Optional[str] = None
    tool_calls: Optional[list[ToolCall]] = None
    reasoning_content: Optional[str] = None


class Choice(BaseModel):
    index: int
    message: Optional[ChatResponseMessage] = None
    delta: Optional[ChatResponseMessage] = None
    finish_reason: Optional[str] = None
    logprobs: Optional[dict] = None


class ChatResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str
    choices: list[Choice]
    usage: Optional[Usage] = None
    system_fingerprint: Optional[str] = "fp"


class ChatStreamResponse(BaseModel):
    id: str
    object: str = "chat.completion.chunk"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str
    choices: list[Choice] = []
    usage: Optional[Usage] = None
    system_fingerprint: Optional[str] = "fp"


####################################
# Bedrock Model Implementation
####################################


# Global profile metadata cache
profile_metadata: dict = {}

# Models that don't support both temperature and topP simultaneously
TEMPERATURE_TOPP_CONFLICT_MODELS = {
    "claude-sonnet-4-5",
    "claude-haiku-4-5",
}


class BedrockChatModel:
    """
    Bedrock chat model implementation using AWS Converse API.

    Handles:
    - OpenAI-compatible request/response format
    - Tool calling
    - Streaming responses
    - Cross-region inference profiles
    """

    def __init__(self, region: str):
        self.region = region
        self.runtime, self.client = get_bedrock_clients(region)
        self.think_emitted = False
        self._refresh_models()

    def _refresh_models(self):
        """Refresh the available model list including inference profiles."""
        global profile_metadata
        try:
            # List cross-region inference profiles
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
                            model_id = model_arn.split('/')[-1]
                            profile_metadata[profile_id] = {
                                "underlying_model_id": model_id,
                                "profile_type": "SYSTEM_DEFINED",
                                "profile_name": profile.get("inferenceProfileName", profile_id),
                            }
        except Exception as e:
            log.warning(f"Failed to list inference profiles: {e}")

    def list_models(self) -> list[dict]:
        """Return list of available models."""
        self._refresh_models()
        models = []

        # Add cross-region inference profiles
        for profile_id, metadata in profile_metadata.items():
            models.append({
                "id": profile_id,
                "name": metadata.get("profile_name", profile_id),
                "object": "model",
                "created": int(time.time()),
                "owned_by": "bedrock",
            })

        return models

    def _resolve_to_foundation_model(self, model_id: str) -> str:
        """Resolve profile ID to foundation model for feature detection."""
        if model_id in profile_metadata:
            return profile_metadata[model_id]["underlying_model_id"]
        return model_id

    def validate(self, model_id: str):
        """Validate that the model is available."""
        if model_id not in profile_metadata:
            # Try direct model ID
            return

    @staticmethod
    def generate_message_id() -> str:
        return "chatcmpl-" + str(uuid.uuid4())[:8]

    @staticmethod
    def stream_response_to_bytes(response: Optional[ChatStreamResponse] = None) -> bytes:
        if response is None:
            return b"data: [DONE]\n\n"

        response.system_fingerprint = "fp"
        response.object = "chat.completion.chunk"
        response.created = int(time.time())
        data = response.model_dump_json(exclude_unset=True)
        return f"data: {data}\n\n".encode("utf-8")

    def _parse_messages(self, messages: list[dict], model_id: str) -> tuple[list[dict], list[dict]]:
        """
        Parse OpenAI-format messages into Bedrock Converse API format.

        Returns:
            Tuple of (messages, system_prompts)
        """
        system_prompts = []
        bedrock_messages = []

        for msg in messages:
            role = msg.get("role")
            content = msg.get("content")

            if role == "system":
                if isinstance(content, str):
                    system_prompts.append({"text": content})
                continue

            if role == "user":
                bedrock_content = self._parse_content_parts(content, model_id)
                bedrock_messages.append({
                    "role": "user",
                    "content": bedrock_content,
                })

            elif role == "assistant":
                tool_calls = msg.get("tool_calls")

                if content:
                    bedrock_content = self._parse_content_parts(content, model_id)
                    bedrock_messages.append({
                        "role": "assistant",
                        "content": bedrock_content,
                    })

                if tool_calls:
                    for tc in tool_calls:
                        tool_input = json.loads(tc["function"]["arguments"])
                        bedrock_messages.append({
                            "role": "assistant",
                            "content": [{
                                "toolUse": {
                                    "toolUseId": tc["id"],
                                    "name": tc["function"]["name"],
                                    "input": tool_input,
                                }
                            }],
                        })

            elif role == "tool":
                tool_content = self._extract_tool_content(content)
                bedrock_messages.append({
                    "role": "user",
                    "content": [{
                        "toolResult": {
                            "toolUseId": msg.get("tool_call_id"),
                            "content": [{"text": tool_content}],
                        }
                    }],
                })

        # Merge consecutive messages from same role
        merged = self._merge_consecutive_messages(bedrock_messages)

        return merged, system_prompts

    def _parse_content_parts(self, content, model_id: str) -> list[dict]:
        """Parse content into Bedrock format."""
        if isinstance(content, str):
            return [{"text": content}]

        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, str):
                    parts.append({"text": item})
                elif isinstance(item, dict):
                    if item.get("type") == "text":
                        parts.append({"text": item.get("text", "")})
                    elif item.get("type") == "image_url":
                        # Handle image content
                        image_url = item.get("image_url", {})
                        url = image_url.get("url", "")
                        if url.startswith("data:"):
                            # Base64 encoded image
                            parts.append(self._parse_base64_image(url))
            return parts if parts else [{"text": ""}]

        return [{"text": str(content) if content else ""}]

    def _parse_base64_image(self, data_url: str) -> dict:
        """Parse a data URL into Bedrock image format."""
        import base64

        # Parse data:image/png;base64,... format
        if "," in data_url:
            header, data = data_url.split(",", 1)
            # Extract media type
            media_type = "image/png"  # default
            if "image/" in header:
                media_type = header.split("image/")[1].split(";")[0]
                media_type = f"image/{media_type}"
        else:
            data = data_url
            media_type = "image/png"

        return {
            "image": {
                "format": media_type.split("/")[1],
                "source": {
                    "bytes": base64.b64decode(data)
                }
            }
        }

    def _extract_tool_content(self, content) -> str:
        """Extract text from tool message content."""
        if isinstance(content, str):
            return content

        if isinstance(content, list):
            texts = []
            for item in content:
                if isinstance(item, dict) and "text" in item:
                    texts.append(item["text"])
                elif isinstance(item, str):
                    texts.append(item)
            return "\n".join(texts)

        return str(content) if content else ""

    def _merge_consecutive_messages(self, messages: list[dict]) -> list[dict]:
        """Merge consecutive messages from the same role (required by Bedrock)."""
        if not messages:
            return []

        merged = []
        current_role = None
        current_content = []

        for msg in messages:
            role = msg["role"]
            content = msg["content"]

            if role != current_role:
                if current_content:
                    merged.append({"role": current_role, "content": current_content})
                current_role = role
                current_content = []

            if isinstance(content, list):
                current_content.extend(content)
            else:
                current_content.append({"text": str(content)})

        if current_content:
            merged.append({"role": current_role, "content": current_content})

        return merged

    def _convert_tool_spec(self, func: dict) -> dict:
        """Convert OpenAI function spec to Bedrock tool spec."""
        return {
            "toolSpec": {
                "name": func.get("name", ""),
                "description": func.get("description", ""),
                "inputSchema": {
                    "json": func.get("parameters", {})
                }
            }
        }

    def _parse_request(self, payload: dict) -> dict:
        """Convert OpenAI chat request to Bedrock Converse API format."""
        model_id = payload.get("model", "")
        messages = payload.get("messages", [])

        bedrock_messages, system_prompts = self._parse_messages(messages, model_id)

        # Inference config
        inference_config = {}

        if payload.get("max_tokens"):
            inference_config["maxTokens"] = payload["max_tokens"]
        elif payload.get("max_completion_tokens"):
            inference_config["maxTokens"] = payload["max_completion_tokens"]
        else:
            inference_config["maxTokens"] = 4096  # Default

        if payload.get("temperature") is not None:
            inference_config["temperature"] = payload["temperature"]

        if payload.get("top_p") is not None:
            inference_config["topP"] = payload["top_p"]

        # Handle models that conflict with temperature + topP
        resolved_model = self._resolve_to_foundation_model(model_id).lower()
        if "temperature" in inference_config and "topP" in inference_config:
            if any(m in resolved_model for m in TEMPERATURE_TOPP_CONFLICT_MODELS):
                inference_config.pop("topP", None)

        if payload.get("stop"):
            stop = payload["stop"]
            if isinstance(stop, str):
                stop = [stop]
            inference_config["stopSequences"] = stop

        args = {
            "modelId": model_id,
            "messages": bedrock_messages,
            "inferenceConfig": inference_config,
        }

        if system_prompts:
            args["system"] = system_prompts

        # Add tools if present
        tools = payload.get("tools")
        if tools:
            tool_config = {
                "tools": [self._convert_tool_spec(t.get("function", t)) for t in tools]
            }

            tool_choice = payload.get("tool_choice")
            if tool_choice:
                if isinstance(tool_choice, str):
                    if tool_choice == "required":
                        tool_config["toolChoice"] = {"any": {}}
                    else:
                        tool_config["toolChoice"] = {"auto": {}}
                elif isinstance(tool_choice, dict) and "function" in tool_choice:
                    tool_config["toolChoice"] = {
                        "tool": {"name": tool_choice["function"].get("name", "")}
                    }

            args["toolConfig"] = tool_config

        return args

    def _convert_finish_reason(self, bedrock_reason: str) -> str:
        """Convert Bedrock stop reason to OpenAI finish_reason."""
        mapping = {
            "end_turn": "stop",
            "stop_sequence": "stop",
            "max_tokens": "length",
            "tool_use": "tool_calls",
        }
        return mapping.get(bedrock_reason, bedrock_reason)

    async def chat(self, payload: dict) -> ChatResponse:
        """Handle non-streaming chat completion."""
        args = self._parse_request(payload)

        try:
            response = await run_in_threadpool(self.runtime.converse, **args)
        except self.runtime.exceptions.ValidationException as e:
            raise HTTPException(status_code=400, detail=str(e))
        except self.runtime.exceptions.ThrottlingException as e:
            raise HTTPException(status_code=429, detail=str(e))
        except Exception as e:
            log.error(f"Bedrock error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

        output_message = response["output"]["message"]
        usage = response["usage"]
        finish_reason = response["stopReason"]

        message = self._create_response_message(output_message["content"], finish_reason)

        return ChatResponse(
            id=self.generate_message_id(),
            model=payload.get("model", ""),
            choices=[
                Choice(
                    index=0,
                    message=message,
                    finish_reason=self._convert_finish_reason(finish_reason),
                )
            ],
            usage=Usage(
                prompt_tokens=usage.get("inputTokens", 0),
                completion_tokens=usage.get("outputTokens", 0),
                total_tokens=usage.get("totalTokens", 0),
            ),
        )

    def _create_response_message(self, content: list[dict], finish_reason: str) -> ChatResponseMessage:
        """Create ChatResponseMessage from Bedrock content blocks."""
        message = ChatResponseMessage(role="assistant")

        if finish_reason == "tool_use":
            tool_calls = []
            for part in content:
                if "toolUse" in part:
                    tool = part["toolUse"]
                    tool_calls.append(
                        ToolCall(
                            id=tool["toolUseId"],
                            type="function",
                            function=ResponseFunction(
                                name=tool["name"],
                                arguments=json.dumps(tool["input"]),
                            ),
                        )
                    )
            message.tool_calls = tool_calls
            message.content = None
        else:
            text_content = ""
            for c in content:
                if "text" in c:
                    text_content = c["text"]
                elif "reasoningContent" in c:
                    reasoning = c["reasoningContent"]["reasoningText"].get("text", "")
                    text_content = f"<think>{reasoning}</think>{text_content}"
            message.content = text_content

        return message

    async def chat_stream(self, payload: dict) -> AsyncIterable[bytes]:
        """Handle streaming chat completion."""
        args = self._parse_request(payload)
        message_id = self.generate_message_id()
        model = payload.get("model", "")

        try:
            response = await run_in_threadpool(self.runtime.converse_stream, **args)
            stream = response.get("stream")

            self.think_emitted = False

            for chunk in stream:
                stream_response = self._create_stream_response(model, message_id, chunk)
                if stream_response and stream_response.choices:
                    yield self.stream_response_to_bytes(stream_response)

            # Send [DONE]
            yield self.stream_response_to_bytes(None)

        except self.runtime.exceptions.ValidationException as e:
            error_response = ChatStreamResponse(
                id=message_id,
                model=model,
                choices=[Choice(index=0, delta=ChatResponseMessage(content=f"Error: {e}"))]
            )
            yield self.stream_response_to_bytes(error_response)
        except Exception as e:
            log.error(f"Stream error: {e}")
            error_response = ChatStreamResponse(
                id=message_id,
                model=model,
                choices=[Choice(index=0, delta=ChatResponseMessage(content=f"Error: {e}"))]
            )
            yield self.stream_response_to_bytes(error_response)

    def _create_stream_response(self, model: str, message_id: str, chunk: dict) -> Optional[ChatStreamResponse]:
        """Create streaming response from Bedrock chunk."""
        finish_reason = None
        message = None

        if "messageStart" in chunk:
            message = ChatResponseMessage(
                role=chunk["messageStart"]["role"],
                content="",
            )

        if "contentBlockStart" in chunk:
            delta = chunk["contentBlockStart"]["start"]
            if "toolUse" in delta:
                index = chunk["contentBlockStart"]["contentBlockIndex"] - 1
                message = ChatResponseMessage(
                    tool_calls=[
                        ToolCall(
                            index=index,
                            type="function",
                            id=delta["toolUse"]["toolUseId"],
                            function=ResponseFunction(
                                name=delta["toolUse"]["name"],
                                arguments="",
                            ),
                        )
                    ]
                )

        if "contentBlockDelta" in chunk:
            delta = chunk["contentBlockDelta"]["delta"]
            if "text" in delta:
                message = ChatResponseMessage(content=delta["text"])
            elif "reasoningContent" in delta:
                if "text" in delta["reasoningContent"]:
                    content = delta["reasoningContent"]["text"]
                    if not self.think_emitted:
                        content = "<think>" + content
                        self.think_emitted = True
                    message = ChatResponseMessage(content=content)
                elif "signature" in delta["reasoningContent"]:
                    if self.think_emitted:
                        message = ChatResponseMessage(content="</think>\n\n")
                    else:
                        return None
            elif "toolUse" in delta:
                index = chunk["contentBlockDelta"]["contentBlockIndex"] - 1
                message = ChatResponseMessage(
                    tool_calls=[
                        ToolCall(
                            index=index,
                            function=ResponseFunction(
                                arguments=delta["toolUse"]["input"],
                            ),
                        )
                    ]
                )

        if "messageStop" in chunk:
            message = ChatResponseMessage()
            finish_reason = self._convert_finish_reason(chunk["messageStop"]["stopReason"])

        if message is None:
            return None

        return ChatStreamResponse(
            id=message_id,
            model=model,
            choices=[
                Choice(
                    index=0,
                    delta=message,
                    finish_reason=finish_reason,
                )
            ],
        )


####################################
# Router Endpoints
####################################


@router.get("/config")
async def get_config(request: Request, user=Depends(get_admin_user)):
    """Get Bedrock configuration."""
    return {
        "ENABLE_BEDROCK_API": request.app.state.config.ENABLE_BEDROCK_API,
        "BEDROCK_REGION": request.app.state.config.BEDROCK_REGION,
    }


class BedrockConfigForm(BaseModel):
    ENABLE_BEDROCK_API: Optional[bool] = None
    BEDROCK_REGION: Optional[str] = None


@router.post("/config/update")
async def update_config(
    request: Request,
    form_data: BedrockConfigForm,
    user=Depends(get_admin_user),
):
    """Update Bedrock configuration."""
    if form_data.ENABLE_BEDROCK_API is not None:
        request.app.state.config.ENABLE_BEDROCK_API = form_data.ENABLE_BEDROCK_API
    if form_data.BEDROCK_REGION is not None:
        request.app.state.config.BEDROCK_REGION = form_data.BEDROCK_REGION

    return {
        "ENABLE_BEDROCK_API": request.app.state.config.ENABLE_BEDROCK_API,
        "BEDROCK_REGION": request.app.state.config.BEDROCK_REGION,
    }


async def get_all_models(request: Request, user: UserModel = None) -> dict:
    """Get all available Bedrock models."""
    if not request.app.state.config.ENABLE_BEDROCK_API:
        return {"data": []}

    try:
        region = request.app.state.config.BEDROCK_REGION
        model = BedrockChatModel(region)
        models = model.list_models()

        # Format for OpenWebUI
        return {
            "data": [
                {
                    **m,
                    "name": m["id"],
                    "owned_by": "bedrock",
                    "bedrock": m,
                }
                for m in models
            ]
        }
    except Exception as e:
        log.error(f"Failed to list Bedrock models: {e}")
        return {"data": []}


@router.get("/models")
async def get_models(request: Request, user=Depends(get_verified_user)):
    """List available Bedrock models."""
    return await get_all_models(request, user)


@router.post("/chat/completions")
async def generate_chat_completion(
    request: Request,
    form_data: dict,
    user=Depends(get_verified_user),
    bypass_filter: Optional[bool] = False,
):
    """Generate chat completion using Bedrock."""
    if BYPASS_MODEL_ACCESS_CONTROL:
        bypass_filter = True

    if not request.app.state.config.ENABLE_BEDROCK_API:
        raise HTTPException(status_code=400, detail="Bedrock API is not enabled")

    payload = {**form_data}
    metadata = payload.pop("metadata", None)

    model_id = payload.get("model")
    model_info = Models.get_model_by_id(model_id)

    # Check access control
    if model_info:
        if model_info.base_model_id:
            payload["model"] = model_info.base_model_id
            model_id = model_info.base_model_id

        if not bypass_filter and user.role == "user":
            if not (
                user.id == model_info.user_id
                or has_access(user.id, type="read", access_control=model_info.access_control)
            ):
                raise HTTPException(status_code=403, detail="Model not found")
    elif not bypass_filter and user.role != "admin":
        raise HTTPException(status_code=403, detail="Model not found")

    region = request.app.state.config.BEDROCK_REGION
    bedrock = BedrockChatModel(region)

    stream = payload.get("stream", False)

    if stream:
        return StreamingResponse(
            bedrock.chat_stream(payload),
            media_type="text/event-stream",
        )
    else:
        response = await bedrock.chat(payload)
        return response.model_dump()
