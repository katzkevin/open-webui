import {
  app,
  BrowserWindow,
  Tray,
  Menu,
  nativeImage,
  shell,
} from 'electron';
import path from 'path';

// Configuration
const DEFAULT_SERVER_URL = 'https://chat.wolvia.ai';
const SERVER_URL = process.env.OPEN_WEBUI_URL || DEFAULT_SERVER_URL;

let mainWindow: BrowserWindow | null = null;
let tray: Tray | null = null;
let isQuitting = false;

function getResourcePath(filename: string): string {
  // In development, resources are in desktop/resources
  // In production, they're in the app's resources folder
  if (app.isPackaged) {
    return path.join(process.resourcesPath, filename);
  }
  return path.join(__dirname, '../../resources', filename);
}

function getRendererPath(filename: string): string {
  // In development, renderer files are in src/renderer
  // In production, they're copied to dist/renderer
  if (app.isPackaged) {
    return path.join(__dirname, '../renderer', filename);
  }
  return path.join(__dirname, '../../src/renderer', filename);
}

function createWindow(): void {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 800,
    minHeight: 600,
    icon: getResourcePath('icon.png'),
    titleBarStyle: 'default',
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
    },
    show: false, // Don't show until ready
  });

  // Show window when ready to avoid flash
  mainWindow.once('ready-to-show', () => {
    mainWindow?.show();
  });

  // Load the server URL
  mainWindow.loadURL(SERVER_URL);

  // Handle load failures - show error page
  mainWindow.webContents.on('did-fail-load', (_event, errorCode, errorDescription, validatedURL) => {
    console.error(`Failed to load ${validatedURL}: ${errorDescription} (${errorCode})`);
    mainWindow?.loadFile(getRendererPath('error.html'));
  });

  // URLs that should stay in the app (OAuth providers, etc.)
  const allowedDomains = [
    SERVER_URL,
    'https://accounts.google.com',
    'https://www.google.com',
    'https://login.microsoftonline.com',
    'https://github.com/login',
    'https://appleid.apple.com',
  ];

  const isAllowedUrl = (url: string): boolean => {
    return allowedDomains.some(domain => url.startsWith(domain));
  };

  // Handle new window requests (e.g., target="_blank" links)
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    // Allow OAuth and same-origin URLs to open in new window
    if (isAllowedUrl(url)) {
      return { action: 'allow' };
    }
    // Open truly external links in browser
    shell.openExternal(url);
    return { action: 'deny' };
  });

  // Handle navigation in main window
  mainWindow.webContents.on('will-navigate', (event, url) => {
    // Allow OAuth flows and same-origin navigation
    if (isAllowedUrl(url) || url.startsWith('file://')) {
      return; // Allow navigation
    }
    // Block and open in external browser
    event.preventDefault();
    shell.openExternal(url);
  });

  // Minimize to tray instead of closing (optional behavior)
  mainWindow.on('close', (event) => {
    if (!isQuitting && process.platform === 'darwin') {
      event.preventDefault();
      mainWindow?.hide();
    }
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

function createTray(): void {
  const iconPath = getResourcePath('icon.png');
  const icon = nativeImage.createFromPath(iconPath);

  // Resize for tray (16x16 on most platforms, 22x22 on some Linux)
  const trayIcon = icon.resize({ width: 16, height: 16 });
  tray = new Tray(trayIcon);

  const contextMenu = Menu.buildFromTemplate([
    {
      label: 'Show Wolvia',
      click: () => {
        if (mainWindow) {
          mainWindow.show();
          mainWindow.focus();
        }
      },
    },
    { type: 'separator' },
    {
      label: 'Reload',
      click: () => {
        mainWindow?.loadURL(SERVER_URL);
      },
    },
    { type: 'separator' },
    {
      label: 'Quit',
      click: () => {
        isQuitting = true;
        app.quit();
      },
    },
  ]);

  tray.setContextMenu(contextMenu);
  tray.setToolTip('Wolvia');

  // Click on tray icon shows window
  tray.on('click', () => {
    if (mainWindow) {
      if (mainWindow.isVisible()) {
        mainWindow.focus();
      } else {
        mainWindow.show();
      }
    }
  });
}

// Single instance lock - prevent multiple windows
const gotTheLock = app.requestSingleInstanceLock();

if (!gotTheLock) {
  app.quit();
} else {
  app.on('second-instance', () => {
    // Someone tried to run a second instance, focus our window
    if (mainWindow) {
      if (mainWindow.isMinimized()) {
        mainWindow.restore();
      }
      mainWindow.show();
      mainWindow.focus();
    }
  });

  app.whenReady().then(() => {
    createWindow();
    createTray();

    // macOS: Re-create window when dock icon is clicked
    app.on('activate', () => {
      if (BrowserWindow.getAllWindows().length === 0) {
        createWindow();
      } else {
        mainWindow?.show();
      }
    });
  });

  // Quit when all windows are closed (except on macOS)
  app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') {
      app.quit();
    }
  });

  app.on('before-quit', () => {
    isQuitting = true;
  });
}
