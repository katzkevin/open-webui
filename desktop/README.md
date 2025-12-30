# Wolvia Desktop App

A lightweight Electron wrapper for [Wolvia](https://chat.wolvia.ai) (Open WebUI fork).

## What This Is

A thin desktop shell (~200 lines) that provides:
- Native macOS/Windows/Linux app experience
- System tray with quick access
- Single-instance enforcement (no duplicate windows)
- OAuth support (Google, Microsoft, GitHub, Apple)

**What it's NOT:**
- Does NOT bundle Python or manage servers
- Does NOT install packages at runtime
- Just points to `https://chat.wolvia.ai`

## Development

```bash
# Install dependencies
npm install

# Run in development
npm start

# Build for distribution
npm run dist:mac      # macOS DMG
npm run dist:win      # Windows NSIS
npm run dist:linux    # Linux AppImage/deb
```

## Configuration

Override the server URL via environment variable:
```bash
OPEN_WEBUI_URL=https://your-server.com npm start
```

Default: `https://chat.wolvia.ai`

## Distribution

### For Testers (Unsigned)

macOS users need to bypass Gatekeeper on first launch:
1. Right-click the app → Open
2. Click "Open" on the security warning

Or run: `xattr -cr /Applications/Wolvia.app`

### GitHub Releases

Releases are built automatically via GitHub Actions when a version tag is pushed:
```bash
# Tag a new release
git tag desktop-v1.0.0
git push origin desktop-v1.0.0
```

This triggers builds for:
- macOS (arm64 + x64) → `.dmg`, `.zip`
- Windows → `.exe`
- Linux → `.AppImage`, `.deb`

Download from: https://github.com/kevcmk/open-webui/releases

### Manual Release

You can also trigger a release manually:
1. Go to Actions → "Desktop App Release"
2. Click "Run workflow"
3. Enter version number

## Architecture

```
desktop/
├── src/
│   ├── main/index.ts      # Electron main process
│   └── renderer/error.html # Connection error page
├── resources/
│   └── icon.png           # App icon (512x512)
├── package.json
├── tsconfig.json
└── electron-builder.yml   # Build configuration
```

## Known Limitations

- **Passkeys**: WebAuthn/passkey auth doesn't work in Electron. Use password-based login.
- **Unsigned builds**: macOS will warn on first launch until we add code signing.

## Code Signing (Future)

To enable auto-updates and remove Gatekeeper warnings:
- macOS: Requires Apple Developer account ($99/yr)
- Windows: Requires code signing certificate

For now, unsigned builds work fine for internal distribution.
