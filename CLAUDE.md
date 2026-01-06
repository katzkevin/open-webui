# Open WebUI - Wolvia Fork

This is Wolvia's fork of Open WebUI, maintained at `github.com/kevcmk/open-webui`.
The upstream repo is `github.com/open-webui/open-webui`.

**See [README.wolvia.md](README.wolvia.md) for the complete list of fork modifications and why they exist.**

**When making changes to this fork, document them in README.wolvia.md.**

## Building & Deploying

**IMPORTANT: Docker images are ONLY built via GitHub Actions on push to `wolvia-main`.**

- **DO NOT** build Docker images locally
- **DO NOT** attempt to deploy images built outside of GitHub Actions
- **DO NOT** run terraform commands directly - all infrastructure changes go through the wolvia repo's CI/CD pipeline
- All builds happen automatically when code is pushed to `wolvia-main`

### Deployment Process

1. Push changes to `wolvia-main` branch
2. GitHub Actions automatically builds and pushes the image to ECR
3. Get the new version tag from the GitHub Actions workflow output (e.g., `0.6.41-wolvia.{run_number}`)
   - Check logs: `gh run view <run_id> --repo katzkevin/open-webui --log | grep "VERSION:"`
4. Go to `../wolvia` repo and update `openwebui_version` in `terraform/modules/infrastructure/ecs.tf`
5. Push to the wolvia repo's `dev` or `main` branch to trigger the Release and Deploy Pipeline

### Version Format

- `{upstream_version}-wolvia.{github_run_number}` - e.g., `0.6.41-wolvia.14070`
- The run number comes from the GitHub Actions workflow
- Currently based on upstream v0.6.41

### Syncing with Upstream

To pull in upstream changes:
```bash
git fetch upstream
git merge upstream/main
# Resolve any conflicts, keeping Wolvia customizations
git push origin wolvia-main
```
