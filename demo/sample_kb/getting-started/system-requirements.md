# System Requirements

Cumulus runs in the browser. There is no desktop install required for the web app, though we ship optional native wrappers for macOS and Windows.

## Supported browsers

- **Chrome** — version 110 or newer.
- **Firefox** — version 109 or newer.
- **Safari** — version 16 or newer.
- **Edge** — version 110 or newer.

Internet Explorer is not supported and will redirect to a static "please upgrade" page.

## Network requirements

Cumulus needs an outbound HTTPS connection to `*.cumulus.example` on port 443. If your IT team uses an allowlist proxy, ask them to also allow `*.cumulus-cdn.example` for static assets.

WebSocket connections to `wss://realtime.cumulus.example` power live cursors and notifications. If WebSockets are blocked, Cumulus falls back to long-polling, but live presence will be delayed by up to 15 seconds.

## Desktop apps

The macOS and Windows wrappers are Electron-based. They add native notifications, a menu-bar quick-create shortcut, and offline read access to recently viewed projects. Minimum OS: macOS 12 Monterey, Windows 10 21H2.

## Mobile apps

iOS 16+ and Android 11+. The mobile app is read-and-comment only — task creation and editing happen in the web or desktop client.
