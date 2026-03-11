# Model Bulk Configure API

## Overview

A new endpoint to declaratively configure per-model settings in a single atomic operation. Complements the existing bulk config import (which handles connections, task settings, MCP server definitions, etc.).

## Endpoint

```
POST /api/v1/models/bulk-configure
```

**Authentication**: Admin API key required

## Request Schema

```typescript
interface BulkConfigureRequest {
  // Array of model configurations
  models: ModelConfig[];

  // Options for the operation
  options?: {
    // Delete model DB entries not in the models array (default: false)
    delete_unlisted?: boolean;

    // Create DB entries for models that don't exist yet (default: true)
    // Models must be available from a configured source (BAG, OpenAI, etc.)
    create_if_missing?: boolean;
  };
}

interface ModelConfig {
  // Model ID (e.g., "global.anthropic.claude-sonnet-4-5-20250929-v1:0")
  id: string;

  // Tools available for this model (shown in UI, can be toggled)
  // e.g., ["server:mcp:wolvia-memory", "server:mcp:safe-web-search"]
  toolIds?: string[];

  // Tools enabled by default in new chats
  // Must be subset of toolIds
  defaultFeatureIds?: string[];

  // System message for this model (null to clear)
  system_message?: string | null;

  // Whether model is active/visible to users (default: true)
  is_active?: boolean;
}
```

## Response Schema

```typescript
interface BulkConfigureResponse {
  success: boolean;

  // Summary of what was done
  summary: {
    created: number;      // New model entries created
    updated: number;      // Existing entries updated
    deleted: number;      // Entries deleted (if delete_unlisted=true)
    skipped: number;      // Models skipped (not found, create_if_missing=false)
  };

  // Details per model
  details: {
    id: string;
    action: "created" | "updated" | "deleted" | "skipped";
    error?: string;  // If skipped due to error
  }[];
}
```

## Example Request

```bash
curl -X POST https://chat.dev.wolvia.ai/api/v1/models/bulk-configure \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "models": [
      {
        "id": "global.anthropic.claude-sonnet-4-5-20250929-v1:0",
        "toolIds": [
          "server:mcp:wolvia-memory",
          "server:mcp:safe-web-search",
          "server:mcp:linear",
          "server:mcp:google-drive"
        ],
        "defaultFeatureIds": [
          "server:mcp:wolvia-memory",
          "server:mcp:safe-web-search"
        ],
        "system_message": null,
        "is_active": true
      },
      {
        "id": "global.anthropic.claude-opus-4-5-20251101-v1:0",
        "toolIds": [
          "server:mcp:wolvia-memory",
          "server:mcp:safe-web-search",
          "server:mcp:linear",
          "server:mcp:google-drive"
        ],
        "defaultFeatureIds": [
          "server:mcp:wolvia-memory",
          "server:mcp:safe-web-search"
        ],
        "system_message": null,
        "is_active": true
      }
    ],
    "options": {
      "delete_unlisted": true,
      "create_if_missing": true
    }
  }'
```

## Example Response

```json
{
  "success": true,
  "summary": {
    "created": 1,
    "updated": 1,
    "deleted": 34,
    "skipped": 0
  },
  "details": [
    {
      "id": "global.anthropic.claude-sonnet-4-5-20250929-v1:0",
      "action": "updated"
    },
    {
      "id": "global.anthropic.claude-opus-4-5-20251101-v1:0",
      "action": "created"
    }
  ]
}
```

## Behavior

### Model Creation (`create_if_missing=true`)

When a model ID in the request doesn't have a DB entry:
1. Verify the model exists in a configured source (fetch from `/api/models`)
2. Create a new `model` table entry with the provided config
3. If model doesn't exist in any source, skip with error

### Model Update

When a model ID already has a DB entry:
1. Update `meta.toolIds` and `meta.defaultFeatureIds`
2. Update `meta.suggestion_prompts` for system message (or clear if null)
3. Update `is_active` flag

### Model Deletion (`delete_unlisted=true`)

When enabled, any model DB entry NOT in the request's `models` array will be deleted. This cleans up stale entries from old providers or rollbacks.

**Warning**: This is destructive. Any per-model customizations not in the request will be lost.

## Implementation Location

```
backend/open_webui/routers/models.py
```

Add to existing `Models` router alongside other model management endpoints.

## Database Schema Reference

The `model` table stores per-model configuration:

```sql
CREATE TABLE model (
    id VARCHAR PRIMARY KEY,           -- e.g., "global.anthropic.claude-sonnet-4-5-20250929-v1:0"
    user_id VARCHAR,                  -- Owner (null for system models)
    base_model_id VARCHAR,            -- Parent model if this is a variant
    name VARCHAR,                     -- Display name
    meta JSON,                        -- Contains toolIds, defaultFeatureIds, etc.
    params JSON,                      -- Model parameters
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

Key fields in `meta`:
- `toolIds`: string[] - Tools available for this model
- `defaultFeatureIds`: string[] - Tools enabled by default
- `suggestion_prompts`: string - System message (legacy field name)

## Sync Settings Integration

After implementation, `sync_settings.ts` can be simplified:

```typescript
// Before: Multiple loops and API calls
for (const model of models) {
  await updateModelTools(model.id, tools);
  await updateModelSystemMessage(model.id, message);
}

// After: Single call
await fetch(`${url}/api/v1/models/bulk-configure`, {
  method: 'POST',
  headers: { 'Authorization': `Bearer ${apiKey}` },
  body: JSON.stringify({
    models: models.map(m => ({
      id: m.id,
      toolIds: AVAILABLE_TOOLS,
      defaultFeatureIds: DEFAULT_FEATURES,
      system_message: getSystemMessage(m.id),
      is_active: shouldKeepModelActive(m.id)
    })),
    options: { delete_unlisted: true, create_if_missing: true }
  })
});
```

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Invalid model ID format | Skip with error in details |
| Model not in any source | Skip with error (if create_if_missing=true) |
| toolIds contains invalid tool | Accept (tools validated at runtime) |
| defaultFeatureIds not subset of toolIds | Accept (UI handles gracefully) |
| Database error | Return 500 with error message |
| Not admin | Return 403 Forbidden |

## Future Enhancements

1. **Pattern matching**: Allow `"id": "global.anthropic.*"` to apply config to all matching models
2. **Dry run mode**: `"dry_run": true` to preview changes without applying
3. **Backup/restore**: Automatically backup current state before applying
