# Native Bedrock Router Implementation

## Problem Statement

The Bedrock pipe implementation (`openwebui_tools/pipes/bedrock_claude.py`) **cannot support tool calling** because:

1. **OpenWebUI pipes only yield strings** - there's no protocol for structured tool calls
2. The `__TOOL_CALLS__` marker in the pipe is output as **literal text** to the chat UI
3. OpenWebUI does not parse this marker - users see raw JSON like:
   ```
   TOOL_CALLS:{"tool_calls": [{"id": "...", "function": {"name": "safe-web-search_quick_web_search", ...}}]}
   ```

The `bedrock-access-gateway` works because it's a **full OpenAI-compatible API server** with proper SSE responses, not a pipe.

### Why E2E Tests Gave False Positives

The tests in `e2e/tests/test_bedrock_pipe_tool_calling.py` passed but were invalid:
- Tests used `stream=False` but web interface uses streaming (different code paths)
- Tests checked for keywords ("weather", "temperature") not actual tool execution
- Model answered from training data without tools ever being called

**Lesson**: E2E tests MUST use `stream=True` to match production behavior.

## Solution: Native Bedrock Router

Create a native Bedrock router in OpenWebUI (like `openai.py`, `ollama.py`) that:
- Has direct access to OpenWebUI's tool execution machinery
- Returns proper `ChatStreamResponse` objects with `tool_calls`
- Uses the proven Bedrock Converse API implementation from bedrock-access-gateway

## Implementation Approach

### Reuse bedrock-access-gateway Code

The gateway at `/Users/katz/workspace/wolvia/submodules/bedrock-access-gateway/` already has working Bedrock Converse API + tool calling. **Import or vendor this code** rather than writing from scratch.

Options (in order of preference):
1. **Import as package** - Add gateway as dependency, import the Bedrock model classes
2. **Vendor the code** - Copy core files into OpenWebUI router directory
3. **Keep proxy approach** - Current setup with gateway already works for tool calling

### Key Gateway Files to Reuse

| File | Purpose |
|------|---------|
| `src/api/models/bedrock.py` | Core Bedrock implementation with `BedrockModel` class |
| `src/api/models/base.py` | Base model classes (`BaseChatModel`, `BaseEmbeddingsModel`) |
| `src/api/schema.py` | OpenAI-compatible schemas (`ChatRequest`, `ChatResponse`, `ToolCall`, etc.) |

### Key Classes and Methods in `bedrock.py`

```python
class BedrockModel(BaseChatModel):
    def validate(self, chat_request: ChatRequest)       # Line 210
    async def _invoke_bedrock(self, chat_request, stream=False)  # Line 324
    async def chat(self, chat_request) -> ChatResponse  # Line 362
    async def chat_stream(self, chat_request) -> AsyncIterable[bytes]  # Line 406
    def _parse_messages(self, chat_request) -> list[dict]  # Line 504
    def _parse_request(self, chat_request) -> dict      # Line 723
    def _create_response_stream(...)                    # Line 954
```

Tool calling is handled at:
- Lines 547-579: Parsing tool calls from messages
- Lines 878-892: Creating `ToolCall` objects in responses
- Lines 979-1017: Streaming tool call responses

---

## Implementation Steps

### 1. Create Router File

**Location**: `/Users/katz/workspace/open-webui/backend/open_webui/routers/bedrock.py`

The router should:
- Define an `APIRouter` with endpoints for `/models` and `/chat/completions`
- Use `BedrockModel` class (imported or vendored) for actual API calls
- Handle streaming responses compatible with OpenWebUI's expectations

### 2. Register Router in main.py

**File**: `/Users/katz/workspace/open-webui/backend/open_webui/main.py`

Add to imports (around line 73):
```python
from open_webui.routers import (
    ...
    bedrock,  # Add this
)
```

Add router include (around line 1400):
```python
app.include_router(bedrock.router, prefix="/bedrock", tags=["bedrock"])
```

### 3. Add to Model Enumeration

**File**: `/Users/katz/workspace/open-webui/backend/open_webui/utils/models.py`

Add a `fetch_bedrock_models()` function similar to `fetch_openai_models()` and `fetch_ollama_models()`.

Update `get_all_base_models()` to include Bedrock models in the gather:
```python
async def get_all_base_models(request: Request, user: UserModel = None):
    openai_task = ...
    ollama_task = ...
    bedrock_task = (
        fetch_bedrock_models(request, user)
        if request.app.state.config.ENABLE_BEDROCK_API
        else asyncio.sleep(0, result=[])
    )
    function_task = get_function_models(request)

    openai_models, ollama_models, bedrock_models, function_models = await asyncio.gather(
        openai_task, ollama_task, bedrock_task, function_task
    )

    return function_models + openai_models + ollama_models + bedrock_models
```

### 4. Add AWS Configuration

**File**: `/Users/katz/workspace/open-webui/backend/open_webui/config.py` or `env.py`

Add environment variables:
```python
ENABLE_BEDROCK_API = os.environ.get("ENABLE_BEDROCK_API", "false").lower() == "true"
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY", "")
# Or use IAM role-based auth (preferred in ECS/Lambda)
```

### 5. Update Dependencies

**File**: `/Users/katz/workspace/open-webui/backend/requirements.txt`

Add if not already present:
```
boto3>=1.34.0
tiktoken>=0.5.0
```

---

## Reference: How OpenAI Router Works

The `openai.py` router (39KB) shows the pattern to follow:

1. **Router definition**: `router = APIRouter()` with CRUD endpoints
2. **Model listing**: `get_all_models()` returns OpenAI-format model list
3. **Chat completion**: Streaming handled via `StreamingResponse`
4. **Tool calls**: OpenWebUI parses `tool_calls` in response and executes them

Key endpoints in `openai.py`:
- `GET /models` - List available models
- `POST /chat/completions` - Chat completion with streaming support

---

## Files to Modify Summary

| Action | File | Notes |
|--------|------|-------|
| **Create** | `backend/open_webui/routers/bedrock.py` | New router with BedrockModel |
| **Modify** | `backend/open_webui/main.py` | Import and include router |
| **Modify** | `backend/open_webui/utils/models.py` | Add `fetch_bedrock_models()` |
| **Modify** | `backend/open_webui/config.py` | Add AWS config |
| **Modify** | `backend/requirements.txt` | Add boto3, tiktoken |
| **Optional** | `backend/open_webui/routers/bedrock_models/` | Vendor gateway code here |

---

## Implementation Status: COMPLETED

**Date**: 2025-12-23

The native Bedrock router has been implemented. The following files were created/modified:

| File | Action | Notes |
|------|--------|-------|
| `backend/open_webui/routers/bedrock.py` | **Created** | Full router with BedrockChatModel class |
| `backend/open_webui/config.py` | **Modified** | Added ENABLE_BEDROCK_API, BEDROCK_REGION |
| `backend/open_webui/main.py` | **Modified** | Imported and registered bedrock router |
| `backend/open_webui/utils/models.py` | **Modified** | Added fetch_bedrock_models(), updated get_all_base_models() |

### Key Features Implemented:
- Full BedrockChatModel class with Converse API support
- Tool calling support with OpenAI-compatible format
- Streaming responses with SSE
- Cross-region inference profile support
- System prompts and message parsing
- Image content handling (base64)

### Environment Variables:
- `ENABLE_BEDROCK_API=true` - Enable the Bedrock router
- `BEDROCK_REGION=us-east-1` - AWS region (defaults to AWS_REGION env var)

### To Enable:
Set `ENABLE_BEDROCK_API=true` in the environment and ensure AWS credentials are configured (IAM role or env vars).

---

## Current State (What's Working/Not Working)

| Component | Status | Notes |
|-----------|--------|-------|
| **Native Bedrock router** | **IMPLEMENTED** | Full tool support via `/bedrock/chat/completions` |
| Bedrock pipe (`bedrock_claude.py`) | **Disabled** | Tools don't work, models commented out in `sync_settings.ts` |
| Bedrock Access Gateway | **Working** | Full tool support via `us.anthropic.*` and `global.anthropic.*` models |
| E2E tests for pipe | **Skipped** | Invalid tests, marked with skip + warning |
| E2E tests for gateway | **Active** | These work correctly |

---

## Testing Strategy

When implementing the native router:

1. **Unit tests**: Test `BedrockModel` class methods directly
2. **Integration tests**: Test router endpoints with mocked boto3
3. **E2E tests**:
   - MUST use `stream=True` to match production
   - MUST verify actual tool execution, not just keywords
   - Use `sources` in response to confirm tool was called

Example E2E test pattern:
```python
@pytest.mark.asyncio
async def test_bedrock_native_tool_calling(create_chat_completion):
    chat_id, response = await create_chat_completion(
        model_id="bedrock.claude-sonnet-4-5",
        prompt="Search the web for current weather in NYC",
        tool_ids=["server:mcp:safe-web-search"],
        stream=True,  # CRITICAL: Match production
    )

    # Check tool was actually called
    sources = response.get("sources", [])
    tool_sources = [s for s in sources if s.get("tool_result")]
    assert len(tool_sources) >= 1, "Tool should have been executed"
```

---

## Related Files in wolvia Repo

- `/Users/katz/workspace/wolvia/web_app/management/sync_settings.ts` - Models config (pipe models disabled)
- `/Users/katz/workspace/wolvia/e2e/tests/test_bedrock_pipe_tool_calling.py` - Skipped tests with warnings
- `/Users/katz/workspace/wolvia/openwebui_tools/pipes/bedrock_claude.py` - Original pipe (keep for reference)
- `/Users/katz/.claude/plans/soft-stargazing-bonbon.md` - Original plan document

---

## Open Questions

1. **Package import vs vendor**: Can we add bedrock-access-gateway as a pip dependency and import directly?
2. **Model naming**: Should native Bedrock models use `bedrock.*` prefix or something else?
3. **Cross-region inference**: Do we need to support `us.`, `eu.`, `global.` prefixes?
4. **Application inference profiles**: Support for custom inference profiles?

---

## Priority

**High** - Tool calling is broken for all Bedrock pipe models. Users are currently redirected to gateway models, but native support would be cleaner and remove the gateway dependency long-term.
