# Wolvia Fork Setup Guide

## Overview

This fork uses automated CI/CD to build and version Docker images whenever you push changes.

## Initial Setup (One-Time)

### 1. Apply Terraform to Create IAM Resources

In your **main Wolvia repository** (`/Users/katz/workspace/wolvia`):

```bash
cd terraform/environments/dev
terraform apply
```

This creates:
- ECR push permissions attached to existing `cicd-role`
- Reuses the same OIDC setup as main Wolvia workflows

### 2. Verify Role ARN

The workflow uses the existing `cicd-role`:

```bash
arn:aws:iam::117433957365:role/cicd-role
```

This is the same role used by all Wolvia GitHub Actions workflows.

### 3. Set Up Git Branches

Create the Wolvia-specific branches:

```bash
# In open-webui fork repository
git checkout -b wolvia-dev
git push origin wolvia-dev

git checkout -b wolvia-main
git push origin wolvia-main
```

## Daily Workflow

### Making Changes

1. **Work in `wolvia-dev` branch**:
   ```bash
   cd /Users/katz/workspace/open-webui
   git checkout wolvia-dev

   # Make your Wolvia-specific changes
   # (branding updates, config changes, etc.)

   git add .
   git commit -m "fix: update Wolvia logo colors"
   git push origin wolvia-dev
   ```

2. **GitHub Actions runs automatically**:
   - Builds Docker image
   - Versions as `0.6.36-wolvia.{N}`
   - Pushes to `wolvia-dev-openwebui` ECR repository
   - Tags with version, SHA, and `latest`

3. **Check build status**:
   - Go to: https://github.com/kevcmk/open-webui/actions
   - View build logs and version generated

4. **Deploy to dev**:
   ```bash
   cd /Users/katz/workspace/wolvia

   # Update terraform with new version from GitHub Actions
   # Edit terraform/environments/dev/main.tf:
   #   openwebui_version = "0.6.36-wolvia.{N}"

   ./scripts/push-and-wait.sh
   ```

### Promoting to Production

Once tested in dev:

```bash
cd /Users/katz/workspace/open-webui

# Merge dev changes to main
git checkout wolvia-main
git merge wolvia-dev
git push origin wolvia-main
```

This triggers a build that pushes to `wolvia-prod-openwebui` ECR.

Then deploy to prod:

```bash
cd /Users/katz/workspace/wolvia

# Update terraform/environments/prod/main.tf
#   openwebui_version = "0.6.36-wolvia.{N}"

git checkout main
git merge dev
git push origin main
```

## Updating Upstream

When Open WebUI releases a new version (e.g., v0.6.37):

```bash
cd /Users/katz/workspace/open-webui
git checkout wolvia-dev

# Add upstream remote (one-time)
git remote add upstream https://github.com/open-webui/open-webui.git
git fetch upstream

# Merge new version
git merge v0.6.37

# Resolve conflicts (reapply Wolvia branding changes)
# Use comments as guide:
# - Search for "WOLVIA FORK:" comments
# - Reapply those changes to new upstream code

# Update workflow version
# Edit .github/workflows/docker-build.yml:
#   UPSTREAM_VERSION: "0.6.37"

git add .
git commit -m "chore: merge upstream v0.6.37"
git push origin wolvia-dev
```

GitHub Actions will now build `0.6.37-wolvia.1`, starting a new version series.

## Troubleshooting

### Build Fails with "Access Denied" to ECR

**Problem**: GitHub Actions can't push to ECR

**Solution**:
```bash
cd /Users/katz/workspace/wolvia/terraform/environments/dev
terraform apply  # Ensure IAM role is created
```

### Version Number Seems Wrong

**Problem**: Version is `0.6.36-wolvia.9999` (too high)

**Cause**: Commit count includes all history

**Solution**: This is expected. The number always increases. If you want to reset:
1. Create a new branch from a specific commit
2. The commit count will be relative to that new branch

### Build Succeeds but Image Not Found

**Problem**: Terraform can't find the image version

**Check**:
```bash
# List available tags
aws ecr describe-images \
  --repository-name wolvia-dev-openwebui \
  --region us-east-2 \
  --query 'imageDetails[*].imageTags' \
  --output table
```

Make sure you're using the exact version tag from GitHub Actions output.

## Architecture

```
┌─────────────────────────────────────────┐
│ kevcmk/open-webui                       │
│ (Wolvia Fork)                           │
│                                         │
│ Branches:                               │
│ - wolvia-dev  → wolvia-dev-openwebui    │
│ - wolvia-main → wolvia-prod-openwebui   │
└────────────┬────────────────────────────┘
             │
             │ Push triggers workflow
             ▼
┌─────────────────────────────────────────┐
│ GitHub Actions                          │
│ .github/workflows/docker-build.yml      │
│                                         │
│ 1. Calculate version                    │
│ 2. Authenticate to AWS (OIDC)           │
│ 3. Build Docker image                   │
│ 4. Push to ECR                          │
└────────────┬────────────────────────────┘
             │
             │ Pushes image
             ▼
┌─────────────────────────────────────────┐
│ AWS ECR Repositories                    │
│                                         │
│ - wolvia-dev-openwebui                  │
│   Tags: 0.6.36-wolvia.N, SHA, latest    │
│                                         │
│ - wolvia-prod-openwebui                 │
│   Tags: 0.6.36-wolvia.N, SHA, latest    │
└────────────┬────────────────────────────┘
             │
             │ Deployed by Terraform
             ▼
┌─────────────────────────────────────────┐
│ ECS Services                            │
│                                         │
│ - wolvia-dev-cluster/chat-backend       │
│ - wolvia-prod-cluster/chat-backend      │
└─────────────────────────────────────────┘
```

## Security

- **No AWS credentials in GitHub**: Uses OIDC (OpenID Connect) for secure, temporary credentials
- **Reuses existing cicd-role**: Same secure role as main Wolvia workflows
- **Least privilege**: Additional policy only grants ECR push for OpenWebUI repositories
- **Environment isolation**: Separate ECR repositories for dev and prod

## Files in This Fork

### Automation
- `.github/workflows/docker-build.yml` - CI/CD workflow
- `README.wolvia.md` - This file (fork documentation)
- `SETUP.md` - Setup and usage guide

### Branding Changes
See `README.wolvia.md` "Modified Files" section for complete list.

All changes are marked with `WOLVIA FORK:` comments for easy identification during upstream merges.
