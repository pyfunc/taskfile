# Desktop App Publishing Example

Publishing desktop applications (Electron) to multiple distribution channels.

## Supported Platforms

| Platform | Format | Signing | Distribution |
|----------|--------|---------|--------------|
| **macOS** | `.dmg` (Universal) | Apple ID + Notarization | GitHub Releases, Auto-updater |
| **Windows** | `.exe` + `.msi` | EV Code Signing | GitHub Releases, Auto-updater |
| **Linux** | `.AppImage`, `.deb`, `.snap` | - | GitHub Releases, Snap Store, Flathub |

## Quick Start

```bash
# Initialize project
taskfile run init

# Development
taskfile run dev              # Start dev server
taskfile run test             # Run tests
taskfile run lint             # Lint code

# Build
taskfile --platform macos run build-macos      # macOS (requires macOS)
taskfile --platform windows run build-windows  # Windows
taskfile --platform linux run build-linux      # Linux
taskfile run build-all                           # All platforms

# Code Signing (requires certs)
taskfile --platform macos run sign-macos
taskfile --platform windows run sign-windows

# Distribution
taskfile run release-github   # GitHub Releases
taskfile run release-snap     # Snap Store
taskfile run release-flathub  # Flatpak/Flathub

# Full pipeline
taskfile --env prod run publish-all
```

## Setup

### 1. Initialize

```bash
taskfile run init
```

This creates `.env.local` with placeholders for:
- `APPLE_ID` + `APPLE_APP_PASSWORD` (for macOS notarization)
- `WINDOWS_CERT` + `WINDOWS_CERT_PASS` (for Windows signing)
- `GITHUB_TOKEN` (for GitHub Releases)

### 2. macOS Notarization

Get from [Apple Developer](https://developer.apple.com):
1. Apple ID
2. App-specific password ([appleid.apple.com](https://appleid.apple.com))
3. Team ID

Set in `.env.prod`:
```bash
APPLE_ID=your@email.com
APPLE_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx
TEAM_ID=ABCDEF1234
```

### 3. Windows Code Signing

Options:
- **EV Certificate**: Hardware token + password
- **OV Certificate**: `.pfx` file + password

Set in `.env.prod`:
```bash
WINDOWS_CERT=/path/to/cert.pfx
WINDOWS_CERT_PASS=your-password
```

### 4. Distribution Channels

Configure in `.env`:
```bash
GH_RELEASES=true      # Publish to GitHub Releases
SNAP_STORE=true       # Publish to Snap Store
FLATHUB=true          # Build Flatpak for Flathub
```

## Publishing Flow

```
┌─────────────┐    ┌─────────────┐    ┌─────────────────┐
│   Build     │───▶│    Sign     │───▶│   Distribute    │
│             │    │             │    │                 │
│ • macOS     │    │ • Apple ID  │    │ • GitHub        │
│ • Windows   │    │ • Windows   │    │ • Snap Store    │
│ • Linux     │    │   cert      │    │ • Flathub       │
└─────────────┘    └─────────────┘    └─────────────────┘
```

## Task Reference

### Build Tasks

| Task | Platform | Description |
|------|----------|-------------|
| `build-macos` | macOS | Build `.dmg` universal binary |
| `build-windows` | Windows | Build `.exe` + `.msi` |
| `build-linux` | Linux | Build `.AppImage` + `.deb` + `.snap` |
| `build-all` | All | Build all platforms (CI) |

### Signing Tasks

| Task | Requirements | Description |
|------|--------------|-------------|
| `sign-macos` | Apple ID + macOS | Sign + notarize with Apple |
| `sign-windows` | Windows cert | Sign with EV/OV certificate |

### Distribution Tasks

| Task | Channel | Description |
|------|---------|-------------|
| `release-github` | GitHub | Create release with all artifacts |
| `release-snap` | Snap Store | Upload to Snapcraft |
| `release-flathub` | Flathub | Build Flatpak + submit PR |

### Full Pipeline

| Task | Description |
|------|-------------|
| `publish-all` | Build + sign + distribute to all channels |

## CI/CD Integration

### GitHub Actions

```yaml
name: Publish Desktop
on:
  push:
    tags: ['v*']

jobs:
  publish-macos:
    runs-on: macos-latest
    steps:
      - uses: actions/checkout@v4
      - run: npm ci
      - run: taskfile --platform macos run build-macos
        env:
          APPLE_ID: ${{ secrets.APPLE_ID }}
          APPLE_APP_PASSWORD: ${{ secrets.APPLE_APP_PASSWORD }}
      - run: taskfile --platform macos run sign-macos

  publish-windows:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4
      - run: npm ci
      - run: taskfile --platform windows run build-windows
      - run: taskfile --platform windows run sign-windows

  publish-linux:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: npm ci
      - run: taskfile --platform linux run build-linux
      - run: taskfile run release-snap
        env:
          SNAPCRAFT_TOKEN: ${{ secrets.SNAPCRAFT_TOKEN }}

  release:
    needs: [publish-macos, publish-windows, publish-linux]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: taskfile run release-github
```

## Auto-updater

Configure `electron-updater`:

```javascript
// main.js
const { autoUpdater } = require('electron-updater');

autoUpdater.checkForUpdatesAndNotify();
```

Set server type in `package.json`:
```json
{
  "build": {
    "publish": {
      "provider": "github",
      "owner": "your-org",
      "repo": "your-app"
    }
  }
}
```

## Best Practices

1. **Separate signing from building**: Build on any machine, sign only on secure machines
2. **Use CI for building**: GitHub Actions with platform-specific runners
3. **Store certs securely**: Use repository secrets or HSM
4. **Test auto-updates**: Publish to GitHub Releases first, test update flow
5. **Version sync**: Keep `package.json` version in sync with git tags

## See Also

- [Electron Builder docs](https://www.electron.build/)
- [Apple Notarization](https://developer.apple.com/documentation/security/notarizing_macos_software_before_distribution)
- [Windows Code Signing](https://docs.microsoft.com/en-us/windows-hardware/drivers/dashboard/get-a-code-signing-certificate)
- [Snap Store publishing](https://snapcraft.io/docs/releasing-to-the-store)
