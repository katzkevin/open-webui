# Open WebUI Upgrade Plan: v0.6.43 → v0.7.2

**Date**: 2026-01-15
**Status**: COMPLETED (Phase 1) - Ready to push

---

## Overview

Upgrading the Wolvia fork from Open WebUI v0.6.43 to v0.7.2.

| Item | Before | After |
|------|--------|-------|
| Open WebUI Version | 0.6.43 | 0.7.2 |
| Wolvia Version Format | `0.6.41-wolvia.{build}` | `0.7.2-wolvia.{build}` |

---

## Phase 1: Merge Upstream (This Repo) - COMPLETED

### Step 1: Fetch and Merge - DONE
```bash
git fetch upstream
git merge v0.7.2
```

### Step 2: Resolve Conflicts - DONE
Actual conflicts resolved:

| File | Resolution |
|------|------------|
| `backend/open_webui/utils/chat.py` | Kept Wolvia tracing spans + added upstream's `bypass_system_prompt` parameter |
| `backend/open_webui/utils/middleware.py` | Kept Wolvia tracing spans + added native FC checks + file_context capability check |
| `src/lib/components/chat/ModelSelector/ModelItem.svelte` | Kept dark mode fix (`dark:brightness-0 dark:invert`) + added `loading="lazy"` |
| `package-lock.json` | Accepted upstream version |
| `backend/open_webui/test/util/abstract_integration_test.py` | Deleted (upstream removed) |
| `backend/open_webui/test/util/mock_user.py` | Deleted (upstream removed) |

### Step 3: Update Version References - DONE
- [x] `.github/workflows/docker-build.yml` - Set `UPSTREAM_VERSION: "0.7.2"`
- [x] `.github/workflows/desktop-release.yml` - Set `UPSTREAM_VERSION: "0.7.2"`
- [x] `README.wolvia.md` - Updated all version references
- [x] `CLAUDE.md` - Updated all version references

### Step 4: Local Testing - DONE
- [x] Python syntax check passed
- [ ] Full build test skipped (local Node v23 > project's max v22)
- CI will handle full build validation

### Step 5: Push to wolvia-main
```bash
git push origin wolvia-main
```

---

## Phase 2: Wolvia Repo Updates (After CI Build)

### Step 1: Wait for GitHub Actions Build
After pushing, monitor the build:
```bash
gh run list --repo katzkevin/open-webui --limit 5
gh run view <run_id> --repo katzkevin/open-webui --log | grep "VERSION:"
```

The new version will be: `0.7.2-wolvia.{run_number}`

### Step 2: Update Terraform
In `wolvia/terraform/modules/infrastructure/ecs.tf`:
```hcl
locals {
  # OpenWebUI version - Wolvia fork with branding modifications
  # Format: {upstream_version}-wolvia.{build} (e.g., 0.7.2-wolvia.XXXXX)
  # Based on Open WebUI v0.7.2 with BSD-3 Clause 5(i) compliant branding changes
  openwebui_version = "0.7.2-wolvia.{NEW_BUILD_NUMBER}"
}
```

### Step 3: Regenerate openwebui_python_client (If needed)
After the new version is deployed to dev:
```bash
# From wolvia repo
cd openwebui_python_client
openapi-generator generate \
  -i https://chat-dev.wolvia.com/openapi.json \
  -g python \
  -o . \
  --package-name openwebui_client
```

Check if API changes affect the client.

### Step 4: New Environment Variables (Optional)
Consider adding to ECS task definition in `ecs.tf`:
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

### Step 5: Review Integration Tests
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
1. Revert terraform to previous `openwebui_version` (`0.6.41-wolvia.14692`)
2. Push to wolvia repo to redeploy
3. Investigate issues on dev environment

---

## Completion Checklist

### Phase 1 (This Repo)
- [x] Upstream merged successfully
- [x] All conflicts resolved
- [x] Workflow version updated
- [x] README.wolvia.md updated
- [ ] Push to wolvia-main
- [ ] GitHub Actions build passes

### Phase 2 (Wolvia Repo)
- [ ] Get new version tag from CI
- [ ] Update terraform with new version
- [ ] Deploy to dev
- [ ] Regenerate openwebui_python_client (if needed)
- [ ] Run integration tests
- [ ] Deploy to prod
