# WOLVIA FORK - Open WebUI with Wolvia Branding

![Build Status](https://github.com/kevcmk/open-webui/actions/workflows/docker-build.yml/badge.svg)

This is a fork of [Open WebUI](https://github.com/open-webui/open-webui) with Wolvia-specific branding and feature modifications, compliant with the BSD-3-Clause License Clause 5(i) exemption for deployments with <50 users.

**Current Upstream Version**: `0.6.41`

---

## Automated Docker Build System

This fork uses **GitHub Actions** to automatically build and version Docker images.

### Versioning Strategy

**Format**: `{upstream_version}-wolvia.{build_number}`

- `upstream_version`: The Open WebUI version this fork is based on (e.g., `0.6.41`)
- `wolvia`: Marks this as a Wolvia-branded fork
- `build_number`: GitHub Actions run number

**Examples**:
- `0.6.41-wolvia.14070` - Build #14070 based on Open WebUI v0.6.41
- `0.6.41-wolvia.14071` - Subsequent build with fixes/updates

### How It Works

1. **Push to branch** → Triggers GitHub Actions workflow
2. **Automatic versioning** → Calculates `{upstream_version}-wolvia.{run_number}`
3. **Docker build** → Builds image with all Wolvia modifications
4. **Push to ECR** → Uploads to both dev and prod AWS ECR repositories
5. **Multi-tag** → Tags image with version, git SHA, and `latest`

### Branch → Environment Mapping

| Branch | ECR Repositories | Environment |
|--------|-----------------|-------------|
| `wolvia-main` | `wolvia-dev-openwebui`, `wolvia-prod-openwebui` | Both |

### Workflow File

See `.github/workflows/docker-build.yml` for the complete automation.

### Updating Upstream Version

When merging a new Open WebUI release:

1. Fetch upstream: `git fetch upstream`
2. Merge upstream tag: `git merge v0.6.42`
3. Update `UPSTREAM_VERSION` in `.github/workflows/docker-build.yml`
4. Push to trigger new build series

### Manual Deployment

After GitHub Actions builds and pushes the image:

1. **Update terraform**: Set `openwebui_version = "0.6.41-wolvia.X"` in `wolvia/terraform/environments/{dev|prod}/main.tf`
2. **Deploy**: Run `./scripts/push-and-wait.sh` in the main Wolvia repo
3. **Verify**: Check ECS task definition uses new image

---

## LICENSE COMPLIANCE WARNING

**CRITICAL**: This fork has removed Open WebUI branding elements under BSD-3-Clause License, Clause 5(i) exemption.

### CURRENT STATUS: COMPLIANT
- **User count**: 3 users
- **License exemption**: <50 users in any rolling 30-day period (Clause 5(i))

### COMPLIANCE REQUIREMENT

**THIS FORK MUST NOT BE USED WHEN USER COUNT EXCEEDS 15**

#### Action Required at 15 Users:
1. **IMMEDIATELY** restore all Open WebUI branding, OR
2. Obtain enterprise license from Timothy Jaeryang Baek (copyright holder), OR
3. Cease deployment entirely

The 15-user threshold provides a safety buffer below the 50-user license limit.

---

## Fork Modifications Summary

This fork contains **82 modified files** relative to upstream. Each modification has a clear purpose.

---

## 1. Branding (BSD-3 Clause 5(i) Exemption)

**Why**: Replace Open WebUI branding with Wolvia branding. Legal under BSD-3 Clause 5(i) for <50 users.

### Favicon & Images
All replaced with Wolvia logo:
- `static/static/favicon.png`, `favicon.ico`, `favicon-16x16.png`, `favicon-32x32.png`, `favicon-96x96.png`
- `static/static/favicon-dark.png`, `apple-touch-icon.png`, `logo.png`, `splash.png`, `splash-dark.png`
- `static/static/favicon.svg` - Removed (using PNG instead)
- `backend/open_webui/static/*` - Duplicates for backend serving

### Code Changes
| File | Change |
|------|--------|
| `backend/open_webui/env.py` | Removed automatic "(Open WebUI)" suffix from WEBUI_NAME |
| `src/routes/+layout.svelte` | Removed "• Open WebUI" from notification titles |
| `src/lib/components/channel/Channel.svelte` | Removed "• Open WebUI" from page titles |
| `src/lib/components/chat/ShareChatModal.svelte` | Disabled "Share to Open WebUI Community" |

---

## 2. Observability & Error Tracking

**Why**: Production monitoring with Sentry and OpenTelemetry for debugging and performance.

| File | Description |
|------|-------------|
| `backend/open_webui/utils/telemetry/chat_tracing.py` | OpenTelemetry spans for chat completion flow |
| `backend/open_webui/utils/telemetry/constants.py` | Span attribute constants |
| `backend/open_webui/main.py` | Sentry SDK integration (backend) |
| `src/hooks.client.ts` | Sentry SDK integration (frontend) |
| `src/app.html` | Sentry script loading |
| `backend/open_webui/utils/middleware.py` | `trace_chat_span` wrappers, `log.error` for chat memory errors |
| `backend/open_webui/routers/test_logging.py` | Test endpoints for Datadog/Sentry validation |

---

## 3. UI Customizations

**Why**: Hide features we don't use, add provider-specific model icons, fix dark mode.

| File | Change |
|------|--------|
| `static/static/custom.css` | Hides Temporary Chat, Controls button, Workspace sidebar |
| `src/lib/assets/wolvia-custom.css` | Additional Wolvia-specific styles |
| `src/lib/components/chat/ModelSelector/ModelItem.svelte` | Provider icons (Bedrock/OpenAI) based on model ID; dark mode invert |
| `static/static/bedrock.svg`, `openai.svg` | Provider icon assets |

### Dark Mode Model Icons

Added `dark:invert` to all model profile images so they display correctly in dark mode:
- `chat/Placeholder.svelte` - Main page model icon
- `chat/ChatPlaceholder.svelte` - Chat placeholder model icon
- `chat/Messages/ResponseMessage.svelte` - Chat response avatar
- `chat/MessageInput.svelte` - @ selected model indicator
- `chat/MessageInput/Commands/Models.svelte` - @ command dropdown
- `chat/Overview/Node.svelte` - Chat overview nodes
- `layout/Sidebar/PinnedModelItem.svelte` - Sidebar pinned models
- `channel/MessageInput/MentionList.svelte` - Channel mention list
- `channel/Messages/Message.svelte` - Channel message model icons

---

## 4. New API Endpoints

**Why**: Bulk model configuration for sync_settings.ts automation.

| File | Description |
|------|-------------|
| `backend/open_webui/routers/models.py` | `POST /api/v1/models/bulk-configure` endpoint |
| `backend/open_webui/models/models.py` | `bulk_configure()` method and Pydantic models |
| `README.bulk_configure.md` | API documentation |

---

## 5. Desktop App (Electron)

**Why**: Native desktop application for Wolvia.

| File | Description |
|------|-------------|
| `desktop/*` | Electron app (index.ts, error.html, package.json, etc.) |
| `.github/workflows/desktop-release.yml` | Desktop build/release workflow |

---

## 6. CI/CD & Build Infrastructure

**Why**: Automated Docker builds to ECR, versioning.

| File | Description |
|------|-------------|
| `.github/workflows/docker-build.yml` | Docker build → ECR workflow |
| `push-and-wait-for-build.sh` | Push and wait for CI completion |
| `backend/justfile` | Backend development tasks |

---

## 7. Documentation

**Why**: Fork-specific documentation for development and operations.

| File | Description |
|------|-------------|
| `CLAUDE.md` | Claude Code development instructions |
| `README.wolvia.md` | This file - complete fork documentation |
| `README.bulk_configure.md` | Bulk configure API docs |
| `SETUP.md` | Local development setup |
| `claude-todos/*.md` | Task specifications |

---

## 8. Dependencies

**Why**: Additional packages for telemetry and Sentry.

| File | Change |
|------|--------|
| `backend/requirements.txt` | Added opentelemetry, sentry-sdk |
| `package.json` | Added @sentry/sveltekit |
| `package-lock.json` | Lock file updates |

---

## 9. Minor Fixes & Improvements

| File | Change |
|------|--------|
| `backend/open_webui/utils/middleware.py` | `log.error` instead of `log.debug` for chat memory errors |
| `backend/open_webui/utils/chat.py` | Minor improvements |
| `backend/open_webui/routers/ollama.py` | Minor fixes |
| `backend/open_webui/routers/openai.py` | Minor fixes |

---

## NOT Modified (Legal Compliance)

These files are **intentionally unchanged** to maintain license compliance:

- `src/lib/components/chat/Settings/About.svelte` - License text and attribution **KEPT INTACT**
- `LICENSE` - Full BSD-3-Clause license **KEPT INTACT**
- Copyright notices for Timothy Jaeryang Baek **KEPT INTACT**

---

## New Features Documentation

### Bulk Configure API

A new endpoint to declaratively configure per-model settings (tools, system message, is_active) in a single atomic operation.

```
POST /api/v1/models/bulk-configure
```

See `README.bulk_configure.md` for full documentation.

### Provider-Specific Model Icons

Models are automatically assigned icons based on their provider:
- **AWS Bedrock models** (`anthropic.*`, `amazon.*`, `meta.*`, etc.): Shows Bedrock icon
- **OpenAI models** (`gpt-*`, `o1-*`, `o3-*`, etc.): Shows OpenAI icon
- **Other models**: Shows default favicon

### Per-Source Log Levels

Configure logging granularity per component:
```bash
AUDIO_LOG_LEVEL=DEBUG
MODELS_LOG_LEVEL=INFO
OPENAI_LOG_LEVEL=WARNING
# etc.
```

### Test Logging Endpoint

For validating Datadog and Sentry integration:
```
POST /api/v1/test-logging  # Requires admin auth
GET /api/v1/test-sentry?testId=xxx  # No auth required
```

---

## License Information

**License**: BSD 3-Clause License with Branding Restrictions
**Upstream**: https://github.com/open-webui/open-webui
**Copyright**: © 2023-2025 Timothy Jaeryang Baek (Open WebUI)

### Relevant License Clause

> **Clause 5(i)**: The branding restriction shall not apply in deployments or distributions where the total number of end users (defined as individual natural persons with direct access to the application) does not exceed fifty (50) within any rolling thirty (30) day period.

---

## User Count Monitoring

**Current Implementation**: Manual tracking (3 users as of fork creation)

**Required Implementation** (when approaching 15 users):
- Automated user count monitoring
- Alert system at 15-user threshold
- Automated branding restoration OR deployment halt

---

## Compliance Checklist

- [ ] User count ≤ 15
- [ ] Rolling 30-day period tracked
- [ ] License file intact (`LICENSE`)
- [ ] About page attribution intact (`src/lib/components/chat/Settings/About.svelte`)
- [ ] Upstream repository credited

---

## Contact

For enterprise licensing inquiries:
**Open WebUI**: https://openwebui.com
**Copyright Holder**: Timothy Jaeryang Baek

---

**Last Updated**: 2026-01-05
**Fork Maintainer**: Wolvia Development Team
