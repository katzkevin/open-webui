# Desktop App for Open WebUI (Wolvia Fork)

## Background

The official `open-webui-desktop` repo uses the **Open WebUI Sustainable Use License 1.0** which prohibits:
- Commercial use without written authorization
- Redistribution for payment
- Branding modifications
- Sublicensing

This makes it unsuitable for our fork. We need to build our own simple Electron wrapper.

---

## Approach: Simple Electron Wrapper

Since we already have Open WebUI running as a server (or will deploy it), we just need a thin Electron shell that:
1. Opens a BrowserWindow pointing to our server URL
2. Provides native desktop experience (system tray, notifications, etc.)

### What We're NOT Doing
- NOT bundling Python runtime
- NOT managing server processes
- NOT installing packages at runtime
- This keeps us at ~200-500 lines vs their ~2000 lines

---

## Implementation Plan

### Phase 1: Minimal Viable Wrapper

**Files to create:**
```
desktop/
├── package.json
├── electron-builder.yml
├── src/
│   ├── main/
│   │   └── index.ts          # Main process
│   ├── preload/
│   │   └── index.ts          # Preload script (if needed)
│   └── renderer/
│       └── index.html        # Loading/error screen
├── resources/
│   ├── icon.png
│   ├── icon.icns             # macOS
│   └── icon.ico              # Windows
└── tsconfig.json
```

**Core functionality:**
1. Create BrowserWindow with appropriate settings
2. Load configurable server URL (default: `http://localhost:8080`)
3. Handle window lifecycle (minimize to tray on close)
4. Basic error handling (server unreachable screen)

### Phase 2: Quality of Life Features

1. **System tray icon** - Quick access, show/hide window
2. **Configurable server URL** - Via settings file or env var
3. **Native notifications** - Pass through from web app
4. **Deep linking** - Handle `openwebui://` protocol
5. **Auto-launch on startup** - Optional setting

### Phase 3: Build & Distribution

1. **electron-builder** configuration for:
   - macOS: DMG + notarization
   - Windows: NSIS installer
   - Linux: AppImage, deb, rpm
2. **Auto-updates** via electron-updater (optional)
3. **Code signing** setup

---

## Detailed Implementation

### Main Process (`src/main/index.ts`)

```typescript
import { app, BrowserWindow, Tray, Menu, nativeImage, shell } from 'electron';
import path from 'path';

const SERVER_URL = process.env.OPEN_WEBUI_URL || 'http://localhost:8080';

let mainWindow: BrowserWindow | null = null;
let tray: Tray | null = null;
let isQuitting = false;

function createWindow(): void {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 800,
    minHeight: 600,
    icon: path.join(__dirname, '../../resources/icon.png'),
    titleBarStyle: process.platform === 'darwin' ? 'hiddenInset' : 'default',
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
    },
  });

  mainWindow.loadURL(SERVER_URL);

  // Open external links in default browser
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (!url.startsWith(SERVER_URL)) {
      shell.openExternal(url);
      return { action: 'deny' };
    }
    return { action: 'allow' };
  });

  // Minimize to tray instead of closing
  mainWindow.on('close', (event) => {
    if (!isQuitting) {
      event.preventDefault();
      mainWindow?.hide();
    }
  });
}

function createTray(): void {
  const icon = nativeImage.createFromPath(
    path.join(__dirname, '../../resources/tray.png')
  );
  tray = new Tray(icon.resize({ width: 16, height: 16 }));

  const contextMenu = Menu.buildFromTemplate([
    { label: 'Show', click: () => mainWindow?.show() },
    { type: 'separator' },
    { label: 'Quit', click: () => { isQuitting = true; app.quit(); } },
  ]);

  tray.setContextMenu(contextMenu);
  tray.on('click', () => mainWindow?.show());
}

// Single instance lock
const gotTheLock = app.requestSingleInstanceLock();
if (!gotTheLock) {
  app.quit();
} else {
  app.on('second-instance', () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.show();
      mainWindow.focus();
    }
  });

  app.whenReady().then(() => {
    createWindow();
    createTray();
  });

  app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') app.quit();
  });

  app.on('before-quit', () => {
    isQuitting = true;
  });
}
```

### Package.json

```json
{
  "name": "wolvia-desktop",
  "version": "1.0.0",
  "description": "Wolvia Desktop Client",
  "main": "dist/main/index.js",
  "scripts": {
    "dev": "electron .",
    "build": "tsc",
    "dist": "npm run build && electron-builder",
    "dist:mac": "npm run build && electron-builder --mac",
    "dist:win": "npm run build && electron-builder --win",
    "dist:linux": "npm run build && electron-builder --linux"
  },
  "dependencies": {
    "electron-updater": "^6.1.0"
  },
  "devDependencies": {
    "electron": "^28.0.0",
    "electron-builder": "^24.9.0",
    "typescript": "^5.3.0"
  }
}
```

### electron-builder.yml

```yaml
appId: com.wolvia.desktop
productName: Wolvia
copyright: Copyright © 2024 Wolvia

directories:
  output: release

mac:
  category: public.app-category.productivity
  icon: resources/icon.icns
  target:
    - dmg
    - zip

win:
  icon: resources/icon.ico
  target:
    - nsis

linux:
  icon: resources/icon.png
  target:
    - AppImage
    - deb
  category: Network
```

---

## Configuration Options

Support multiple ways to configure the server URL:

1. **Environment variable:** `OPEN_WEBUI_URL`
2. **Config file:** `~/.wolvia/config.json`
3. **Command line:** `--server-url=http://...`

Priority: CLI > Env > Config file > Default

---

## Error Handling

When server is unreachable, show a local HTML page with:
- "Unable to connect to server" message
- Retry button
- Option to change server URL

```typescript
mainWindow.webContents.on('did-fail-load', (event, errorCode, errorDescription) => {
  mainWindow?.loadFile(path.join(__dirname, '../renderer/error.html'));
});
```

---

## Timeline Estimate

| Phase | Effort |
|-------|--------|
| Phase 1: Minimal wrapper | Small |
| Phase 2: QoL features | Small-Medium |
| Phase 3: Build/Distribution | Medium |

---

## Open Questions

1. **Server URL strategy:**
   - Hardcode production URL?
   - Allow user configuration?
   - Support both local and remote servers?

2. **Branding:**
   - App name: "Wolvia" or keep "Open WebUI"?
   - Custom icons needed?

3. **Distribution:**
   - Internal only or public release?
   - App store distribution (Mac App Store, Microsoft Store)?
   - Auto-update mechanism?

4. **Authentication:**
   - How does auth work with the wrapper?
   - Need to persist cookies/session?

---

## Next Steps

1. Create `desktop/` directory in this repo
2. Initialize with minimal package.json and main.ts
3. Get basic window loading server URL working
4. Add system tray support
5. Set up electron-builder for distribution
6. Test on all target platforms
