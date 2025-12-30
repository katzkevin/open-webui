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

## Modified Files

This fork contains the following modifications relative to upstream:

### CI/CD & Infrastructure (New Files)

| File | Description |
|------|-------------|
| `.github/workflows/docker-build.yml` | GitHub Actions workflow for automated Docker builds to ECR |
| `push-and-wait-for-build.sh` | Script to push changes and wait for GitHub Actions build to complete |
| `CLAUDE.md` | Development instructions for Claude Code |
| `README.wolvia.md` | This file - Wolvia fork documentation |
| `README.bulk_configure.md` | Documentation for the bulk-configure API endpoint |

### Favicon & Images (Replaced with Wolvia Branding)

| File | Change |
|------|--------|
| `static/static/favicon.png` | Replaced with Wolvia logo |
| `static/static/favicon.ico` | Replaced with Wolvia logo |
| `static/static/favicon-16x16.png` | Replaced with Wolvia logo |
| `static/static/favicon-32x32.png` | Replaced with Wolvia logo |
| `static/static/favicon-96x96.png` | Replaced with Wolvia logo |
| `static/static/favicon-dark.png` | Replaced with Wolvia logo |
| `static/static/apple-touch-icon.png` | Replaced with Wolvia logo |
| `static/static/logo.png` | Replaced with Wolvia logo |
| `static/static/splash.png` | Replaced with Wolvia logo |
| `static/static/splash-dark.png` | Replaced with Wolvia logo |
| `static/static/favicon.svg` | Removed (using PNG instead) |
| `backend/open_webui/static/*` | All favicon files duplicated for backend serving |

### Provider Icons (New Files)

| File | Description |
|------|-------------|
| `static/static/bedrock.svg` | AWS Bedrock provider icon |
| `static/static/openai.svg` | OpenAI provider icon |
| `backend/open_webui/static/bedrock.svg` | Backend copy of Bedrock icon |
| `backend/open_webui/static/openai.svg` | Backend copy of OpenAI icon |

### UI Customizations

| File | Change |
|------|--------|
| `static/static/custom.css` | Hides Temporary Chat button, Controls button, and Workspace sidebar item |
| `src/lib/components/chat/ModelSelector/ModelItem.svelte` | Shows provider-specific icons (Bedrock, OpenAI) based on model ID |

### Branding Removal (Code Changes)

| File | Change |
|------|--------|
| `backend/open_webui/env.py` | Removed automatic "(Open WebUI)" suffix appending to custom WEBUI_NAME |
| `src/routes/+layout.svelte` | Removed "• Open WebUI" from chat notification titles |
| `src/routes/+layout.svelte` | Removed "• Open WebUI" from channel message notification titles |
| `src/lib/components/channel/Channel.svelte` | Removed "• Open WebUI" from channel page titles |
| `src/lib/components/chat/ShareChatModal.svelte` | Disabled "Share to Open WebUI Community" feature |

### New API Endpoints

| File | Description |
|------|-------------|
| `backend/open_webui/routers/models.py` | Added `POST /api/v1/models/bulk-configure` endpoint for bulk model configuration |
| `backend/open_webui/models/models.py` | Added `bulk_configure()` method and related Pydantic models (`BulkConfigureRequest`, `BulkConfigureResponse`, etc.) |
| `backend/open_webui/routers/test_logging.py` | Test endpoint for Datadog and Sentry integration validation |

### Telemetry & Observability

| File | Description |
|------|-------------|
| `backend/open_webui/utils/telemetry/chat_tracing.py` | OpenTelemetry chat completion tracing utilities |
| `backend/open_webui/utils/telemetry/constants.py` | Chat span attribute constants for OpenTelemetry |
| `backend/open_webui/main.py` | Added Sentry SDK integration with FastAPI/Starlette |

### Logging Improvements

| File | Change |
|------|--------|
| `backend/open_webui/env.py` | Added per-source log level configuration (e.g., `AUDIO_LOG_LEVEL`, `MODELS_LOG_LEVEL`, etc.) |
| Various backend files | Updated to use source-specific log levels via `SRC_LOG_LEVELS` |

### Test Infrastructure

| File | Change |
|------|--------|
| `backend/open_webui/test/apps/webui/routers/test_models.py` | Updated tests for models router, added bulk-configure endpoint tests |
| `backend/open_webui/test/util/abstract_integration_test.py` | Test infrastructure updates |
| `backend/open_webui/test/util/mock_user.py` | Mock user utilities for testing |

### NOT Modified (Legal Compliance)

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

**Last Updated**: 2025-12-29
**Fork Maintainer**: Wolvia Development Team
