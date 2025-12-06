#!/bin/bash
set -euo pipefail

# Push to wolvia-main and wait for GitHub Actions docker build to complete
# Outputs the version tag when done

# Explicitly use the fork repo (gh defaults to upstream in forked repos)
REPO="kevcmk/open-webui"

BRANCH=$(git branch --show-current)
SKIP_PUSH=false

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --skip-push)
      SKIP_PUSH=true
      shift
      ;;
    *)
      echo "Unknown argument: $1"
      echo "Usage: $0 [--skip-push]"
      exit 1
      ;;
  esac
done

if [[ "$BRANCH" != "wolvia-main" ]]; then
  echo "⚠️  Warning: Branch '$BRANCH' is not wolvia-main"
  echo "Only wolvia-main triggers the docker build workflow"
  read -p "Continue anyway? [y/N] " -n 1 -r
  echo
  if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    exit 1
  fi
fi

if [ "$SKIP_PUSH" = false ]; then
  echo "📤 Pushing $BRANCH to origin..."
  git push origin "$BRANCH"
else
  echo "⏭️  Skipping push (--skip-push)"
fi

COMMIT_SHA=$(git rev-parse HEAD)
echo "✅ Commit: $COMMIT_SHA"
echo ""
echo "⏳ Waiting for workflow to start..."

# Poll for workflow run to appear (GitHub can take a few seconds)
MAX_WAIT=60
WAITED=0
RUN_ID=""

while [ $WAITED -lt $MAX_WAIT ]; do
  RUN_ID=$(gh run list \
    --repo="$REPO" \
    --workflow=docker-build.yml \
    --branch="$BRANCH" \
    --limit=10 \
    --json databaseId,headSha \
    --jq ".[] | select(.headSha == \"$COMMIT_SHA\") | .databaseId" \
    2>/dev/null || echo "")

  if [ -n "$RUN_ID" ]; then
    break
  fi

  sleep 2
  WAITED=$((WAITED + 2))
done

if [ -z "$RUN_ID" ]; then
  echo "❌ No workflow run found for commit $COMMIT_SHA after ${MAX_WAIT}s"
  echo "Check: https://github.com/$REPO/actions"
  exit 1
fi

echo "🔍 Found workflow run: $RUN_ID"
echo "🔗 https://github.com/$REPO/actions/runs/$RUN_ID"
echo ""
echo "👀 Watching workflow (this may take 10-15 minutes)..."
echo ""

# Watch the workflow and exit with its status
gh run watch "$RUN_ID" --repo="$REPO" --exit-status
EXIT_CODE=$?

echo ""
if [ $EXIT_CODE -eq 0 ]; then
  echo "✅ Workflow completed successfully!"
  echo ""

  # Extract the version from the workflow run
  # The version is output in the "Set version" step
  echo "📦 Fetching version tag..."

  # Get version from the "Print version" step output
  VERSION=$(gh run view "$RUN_ID" --repo="$REPO" --log 2>/dev/null | grep "VERSION:" | tail -1 | sed 's/.*VERSION: //' || echo "")

  echo ""
  echo "════════════════════════════════════════════════════════════════"
  echo "🏷️  VERSION: $VERSION"
  echo "════════════════════════════════════════════════════════════════"
  echo ""
  echo "To deploy, update terraform:"
  echo "  wolvia/terraform/environments/dev/main.tf"
  echo "  wolvia/terraform/environments/prod/main.tf"
  echo ""
  echo "Set: openwebui_version = \"$VERSION\""
  echo ""
else
  echo "❌ Workflow failed!"
  echo ""
  echo "📋 Fetching failed logs..."
  gh run view "$RUN_ID" --repo="$REPO" --log-failed
  exit 1
fi
