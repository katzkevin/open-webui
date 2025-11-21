# WOLVIA FORK - Open WebUI with Wolvia Branding

![Build Status](https://github.com/kevcmk/open-webui/actions/workflows/docker-build.yml/badge.svg)

This is a fork of [Open WebUI](https://github.com/open-webui/open-webui) with Wolvia-specific branding modifications, compliant with the BSD-3-Clause License Clause 5(i) exemption for deployments with <50 users.

---

## 🚀 Automated Docker Build System

This fork uses **GitHub Actions** to automatically build and version Docker images.

### Versioning Strategy

**Format**: `{upstream_version}-wolvia.{build_number}`

- `upstream_version`: The Open WebUI version this fork is based on (e.g., `0.6.36`)
- `wolvia`: Marks this as a Wolvia-branded fork
- `build_number`: Auto-incremented based on commit count

**Examples**:
- `0.6.36-wolvia.1` - First Wolvia build based on Open WebUI v0.6.36
- `0.6.36-wolvia.2` - Second build with fixes/updates
- `0.6.36-wolvia.15` - 15th iteration

### How It Works

1. **Push to branch** → Triggers GitHub Actions workflow
2. **Automatic versioning** → Calculates `{upstream_version}-wolvia.{commits}`
3. **Docker build** → Builds image with all Wolvia branding
4. **Push to ECR** → Uploads to appropriate AWS ECR repository
5. **Multi-tag** → Tags image with version, git SHA, and `latest`

### Branch → Environment Mapping

| Branch | ECR Repository | Environment |
|--------|---------------|-------------|
| `wolvia-main` | `wolvia-prod-openwebui` | Production |
| `wolvia-dev` | `wolvia-dev-openwebui` | Development |

### Workflow File

See `.github/workflows/docker-build.yml` for the complete automation.

### Updating Upstream Version

When merging a new Open WebUI release:

1. Merge upstream tag (e.g., `v0.6.37`)
2. Update `UPSTREAM_VERSION` in `.github/workflows/docker-build.yml`
3. Push to trigger new build series: `0.6.37-wolvia.1`, etc.

### Manual Deployment

After GitHub Actions builds and pushes the image:

1. **Update terraform**: Set `openwebui_version = "0.6.36-wolvia.X"` in `terraform/environments/{dev|prod}/main.tf`
2. **Deploy**: Run `./scripts/push-and-wait.sh` in the main Wolvia repo
3. **Verify**: Check ECS task definition uses new image

---

## ⚠️ LICENSE COMPLIANCE WARNING

**CRITICAL**: This fork has removed Open WebUI branding elements under BSD-3-Clause License, Clause 5(i) exemption.

## CURRENT STATUS: COMPLIANT
- **User count**: 3 users
- **License exemption**: <50 users in any rolling 30-day period (Clause 5(i))

## 🚨 COMPLIANCE REQUIREMENT 🚨

**THIS FORK MUST NOT BE USED WHEN USER COUNT EXCEEDS 15**

### Action Required at 15 Users:
1. **IMMEDIATELY** restore all Open WebUI branding, OR
2. Obtain enterprise license from Timothy Jaeryang Baek (copyright holder), OR
3. Cease deployment entirely

The 15-user threshold provides a safety buffer below the 50-user license limit.

## Modified Files

This fork contains the following branding modifications:

### Favicon & Images (Replaced with Wolvia branding)
- `static/static/favicon.png`
- `static/static/favicon.svg`
- `static/static/favicon.ico`
- `static/static/favicon-16x16.png`
- `static/static/favicon-32x32.png`
- `static/static/favicon-96x96.png`
- `static/static/favicon-dark.png`
- `static/static/apple-touch-icon.png`
- `static/static/logo.png`
- `static/static/splash.png`
- `static/static/splash-dark.png`
- `backend/open_webui/static/` (all favicon files duplicated)

### Code Changes (Removed "Open WebUI" branding)
- `backend/open_webui/env.py` (line 113-115): Removed automatic "(Open WebUI)" suffix appending
- `src/routes/+layout.svelte` (line 306): Removed "• Open WebUI" from chat notification title
- `src/routes/+layout.svelte` (line 455): Removed "• Open WebUI" from channel message notification title
- `src/lib/components/channel/Channel.svelte` (line 205): Removed "• Open WebUI" from channel page title
- `src/lib/components/chat/ShareChatModal.svelte` (lines 30-58, 129-142): Disabled "Share to Open WebUI Community" feature
- `src/lib/i18n/locales/en-US/translation.json` (lines 1283, 1449): Removed community sharing translation strings

### NOT Modified (Legal Compliance)
- License text in `src/lib/components/chat/Settings/About.svelte` - **KEPT INTACT**
- Copyright notices for Timothy Jaeryang Baek - **KEPT INTACT**
- Full BSD-3-Clause license in `LICENSE` file - **KEPT INTACT**

## License Information

**License**: BSD 3-Clause License with Branding Restrictions
**Upstream**: https://github.com/open-webui/open-webui
**Copyright**: © 2023-2025 Timothy Jaeryang Baek (Open WebUI)

### Relevant License Clause

> **Clause 5(i)**: The branding restriction shall not apply in deployments or distributions where the total number of end users (defined as individual natural persons with direct access to the application) does not exceed fifty (50) within any rolling thirty (30) day period.

## User Count Monitoring

**Current Implementation**: Manual tracking (3 users as of fork creation)

**Required Implementation** (when approaching 15 users):
- Automated user count monitoring
- Alert system at 15-user threshold
- Automated branding restoration OR deployment halt

## Compliance Checklist

- [ ] User count ≤ 15
- [ ] Rolling 30-day period tracked
- [ ] License file intact (`LICENSE`)
- [ ] About page attribution intact (`src/lib/components/chat/Settings/About.svelte`)
- [ ] Upstream repository credited

## Contact

For enterprise licensing inquiries:
**Open WebUI**: https://openwebui.com
**Copyright Holder**: Timothy Jaeryang Baek

---

**Last Updated**: 2025-11-20
**Fork Maintainer**: Wolvia Development Team
