# Open WebUI Upgrade Plan: v0.6.43 → v0.7.2

**Date**: 2026-01-15
**Status**: In Progress

---

## Overview

Upgrading the Wolvia fork from Open WebUI v0.6.43 to v0.7.2.

| Item | Before | After |
|------|--------|-------|
| Open WebUI Version | 0.6.43 | 0.7.2 |
| Wolvia Version Format | `0.6.41-wolvia.{build}` | `0.7.2-wolvia.{build}` |

---

## Phase 1: Merge Upstream (This Repo)

### Step 1: Fetch and Merge
```bash
git fetch upstream
git merge v0.7.2
```

### Step 2: Resolve Conflicts
Expected conflict areas based on Wolvia modifications:
- [ ] `backend/open_webui/main.py` - Sentry integration
- [ ] `backend/open_webui/routers/models.py` - bulk-configure endpoint
- [ ] `backend/open_webui/utils/middleware.py` - trace_chat_span
- [ ] `package.json` / `package-lock.json` - Sentry deps
- [ ] Various UI components with dark mode fixes

### Step 3: Update Version References
- [ ] `.github/workflows/docker-build.yml` - Set `UPSTREAM_VERSION: "0.7.2"`
- [ ] `README.wolvia.md` - Update "Current Upstream Version" to 0.7.2

### Step 4: Local Testing
- [ ] `npm install` and `npm run build` - Frontend builds
- [ ] `pip install -r backend/requirements.txt` - Backend deps
- [ ] Verify bulk-configure API still works
- [ ] Verify Sentry integration compiles

### Step 5: Push to wolvia-main
```bash
git push origin wolvia-main
```

---

## Phase 2: Wolvia Repo Updates

### Step 1: Regenerate openwebui_python_client
After the new version is running:
```bash
# Start local OpenWebUI with new version
# Then regenerate client from OpenAPI spec
openapi-generator generate \
  -i http://localhost:8080/openapi.json \
  -g python \
  -o openwebui_python_client \
  --package-name openwebui_client
```

### Step 2: Update Terraform
In `wolvia/terraform/modules/infrastructure/ecs.tf`:
```hcl
locals {
  openwebui_version = "0.7.2-wolvia.{NEW_BUILD_NUMBER}"
}
```

### Step 3: New Environment Variables (Optional)
Consider adding to ECS task definition:
```hcl
# Audit logs to CloudWatch (instead of file)
{
  name  = "ENABLE_AUDIT_STDOUT"
  value = "true"
},
{
  name  = "ENABLE_AUDIT_LOGS_FILE"
  value = "false"
},
```

### Step 4: Review Integration Tests
Check if any API changes affect:
- `integration_test_user_settings.ts`
- `integration_test_openwebui_models.ts`
- `integration_test_model_management.ts`

---

## Key v0.7.0+ Features

### Native Function Calling
Models can now perform multi-step tasks combining:
- Web research
- Knowledge base queries
- Note-taking
- Image generation

Requires models with native function calling support and "Native" mode in Chat Controls.

### Built-in Tools
Users can ask models to:
- Search notes, past chats, channel messages
- Query knowledge bases without attaching files
- Web search with clickable citations

### Performance Improvements
- Reengineered database connection handling
- Dynamic loading of document processing libraries
- Optimized queries (N+1 elimination)

### New Admin Settings
- Search bar in Admin Settings sidebar
- Per-model capability toggles (disable specific built-in tools)
- Granular group sharing permissions

---

## Breaking Changes to Watch

1. **API Permission Enforcement**: Image Generation, Web Search, Audio APIs now enforce backend permissions. Direct API calls without proper permissions will get 403s.

2. **Evaluations URL Changed**: `/admin/evaluations/feedbacks` → `/admin/evaluations/feedback`

3. **Markdown Splitter Config**: If using standalone "Markdown (Header)" splitter, must switch to character/token mode with `ENABLE_MARKDOWN_HEADER_TEXT_SPLITTER` toggle.

---

## Rollback Plan

If issues occur:
1. Revert terraform to previous `openwebui_version`
2. Push to wolvia repo to redeploy
3. Investigate issues on dev environment

---

## Completion Checklist

- [ ] Upstream merged successfully
- [ ] All conflicts resolved
- [ ] Workflow version updated
- [ ] README.wolvia.md updated
- [ ] GitHub Actions build passes
- [ ] openwebui_python_client regenerated
- [ ] Terraform updated with new version
- [ ] Dev environment tested
- [ ] Prod deployment completed
