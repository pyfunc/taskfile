# Mobile App Publishing Example

Publishing mobile applications (Flutter) to App Store and Google Play Store.

## Supported Platforms

| Platform | Internal Testing | Production |
|----------|-------------------|------------|
| **iOS** | TestFlight | App Store |
| **Android** | Internal Track, Firebase | Play Store |

## Quick Start

```bash
# Initialize project
taskfile run init

# Development
taskfile run dev              # Start dev mode
taskfile run test             # Run tests
taskfile run analyze          # Static analysis

# Build
taskfile --platform ios run build-ios              # iOS IPA
taskfile --platform android run build-android-aab  # Android AAB

# Staging (Internal Testing)
taskfile --env staging run release-staging

# Production (App Store + Play Store)
taskfile --env prod run release-production
```

## Setup

### 1. Initialize

```bash
taskfile run init
```

Creates `.env.local` with placeholders:
- Apple Developer credentials
- Google Play Service Account
- Firebase token (optional)

### 2. iOS Setup (macOS required)

#### Install dependencies:
```bash
brew install fastlane
```

#### Setup certificates:
```bash
taskfile run setup-ios-cert
```

Or manually:
```bash
cd ios && fastlane match development
cd ios && fastlane match appstore
```

#### Configure `.env.prod`:
```bash
APPLE_ID=your@email.com
APPLE_TEAM_ID=ABCDEF1234
FASTLANE_PASSWORD=your-password
```

### 3. Android Setup

#### Create keystore:
```bash
taskfile run setup-android-keystore
```

#### Download Play Store key:
1. [Google Play Console](https://play.google.com/console) → Setup → API Access
2. Create Service Account → Download JSON key
3. Save as `android/play-store-key.json`

#### Configure `.env.prod`:
```bash
PLAYSTORE_JSON=android/play-store-key.json
```

### 4. Firebase (optional, for distribution)

```bash
npm install -g firebase-tools
firebase login:ci
```

Set in `.env`:
```bash
FIREBASE_TOKEN=your-token
FIREBASE_APP_ID=1:123456789:android:abcdef
FIREBASE_DIST=true
```

## Publishing Flow

```
┌─────────────┐    ┌─────────────────────┐    ┌───────────────────┐
│ Development │───▶│ Internal Testing    │───▶│ Production        │
│             │    │                     │    │                   │
│ • Local dev │    │ • TestFlight (iOS)  │    │ • App Store       │
│ • Tests     │    │ • Internal Track    │    │ • Play Store      │
│ • Build     │    │ • Firebase Dist     │    │ • Public release  │
└─────────────┘    └─────────────────────┘    └───────────────────┘
```

## Task Reference

### Development Tasks

| Task | Description |
|------|-------------|
| `dev` | Start Flutter dev mode |
| `test` | Run unit/widget tests |
| `analyze` | Static analysis |
| `install` | Install dependencies |

### Build Tasks

| Task | Platform | Output |
|------|----------|--------|
| `build-ios` | iOS | `.ipa` for App Store |
| `build-android-apk` | Android | `.apk` for Firebase |
| `build-android-aab` | Android | `.aab` for Play Store |
| `build-all` | Both | All artifacts |

### Setup Tasks

| Task | Description |
|------|-------------|
| `setup-ios-cert` | Setup iOS certificates (Fastlane match) |
| `setup-android-keystore` | Create Android keystore |

### Staging Tasks (Internal Testing)

| Task | Platform | Channel |
|------|----------|---------|
| `deploy-testflight` | iOS | TestFlight |
| `deploy-play-internal` | Android | Play Store Internal |
| `deploy-firebase` | Android | Firebase App Distribution |
| `release-staging` | Both | All staging channels |

### Production Tasks

| Task | Platform | Store |
|------|----------|-------|
| `release-appstore` | iOS | App Store |
| `release-playstore` | Android | Play Store |
| `release-production` | Both | Both stores |

## Environment Strategy

| Environment | Use Case | Channels |
|-------------|----------|----------|
| `local` | Development | Local device/simulator |
| `staging` | QA, Beta testers | TestFlight, Internal Track, Firebase |
| `prod` | Public release | App Store, Play Store |

## CI/CD Integration

### GitHub Actions

```yaml
name: Mobile CI/CD
on:
  push:
    branches: [main]
  workflow_dispatch:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: subosito/flutter-action@v2
      - run: flutter pub get
      - run: taskfile run test
      - run: taskfile run analyze

  deploy-staging:
    needs: test
    runs-on: macos-latest  # macOS for both iOS and Android
    if: github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v4
      - uses: subosito/flutter-action@v2
      - run: flutter pub get
      - run: taskfile --env staging run release-staging
        env:
          APPLE_ID: ${{ secrets.APPLE_ID }}
          FASTLANE_PASSWORD: ${{ secrets.FASTLANE_PASSWORD }}
          PLAYSTORE_JSON: ${{ secrets.PLAYSTORE_JSON }}

  deploy-production:
    needs: deploy-staging
    runs-on: macos-latest
    if: startsWith(github.ref, 'refs/tags/v')
    steps:
      - uses: actions/checkout@v4
      - uses: subosito/flutter-action@v2
      - run: flutter pub get
      - run: taskfile --env prod run release-production
        env:
          APPLE_ID: ${{ secrets.APPLE_ID }}
          FASTLANE_PASSWORD: ${{ secrets.FASTLANE_PASSWORD }}
          PLAYSTORE_JSON: ${{ secrets.PLAYSTORE_JSON }}
```

## Fastlane Configuration

### iOS Fastfile

```ruby
# ios/fastlane/Fastfile
default_platform(:ios)

platform :ios do
  desc "Push to TestFlight"
  lane :beta do
    build_app(workspace: "Runner.xcworkspace", scheme: "Runner")
    upload_to_testflight
  end

  desc "Release to App Store"
  lane :release do
    build_app(workspace: "Runner.xcworkspace", scheme: "Runner")
    upload_to_app_store
  end
end
```

### Android Fastfile

```ruby
# android/fastlane/Fastfile
default_platform(:android)

platform :android do
  desc "Internal testing"
  lane :internal do
    gradle(task: "bundleRelease")
    upload_to_play_store(track: 'internal')
  end

  desc "Deploy to Play Store"
  lane :deploy do
    gradle(task: "bundleRelease")
    upload_to_play_store
  end
end
```

## Version & Build Numbers

Flutter uses `version: 1.0.0+1` in `pubspec.yaml`:
- `1.0.0` = version
- `+1` = build number

Bump with:
```bash
# Manual bump
taskfile run bump-build

# Or update pubspec.yaml directly
version: 1.1.0+2
```

## Screenshots & Metadata

### Generate Screenshots

```bash
# Capture screenshots on all devices
taskfile run screenshots
```

Uses Fastlane's `snapshot` (iOS) and `screengrab` (Android).

### Upload Metadata

```bash
# Upload descriptions, screenshots without app
taskfile run metadata
```

## Testing Before Release

### iOS

```bash
# Install on device via TestFlight
# 1. Build and upload
TASKFILE_PLATFORM=ios taskfile --env staging run deploy-testflight

# 2. Open TestFlight app on device
# 3. Install and test
```

### Android

```bash
# Install APK directly
flutter build apk --release
adb install build/app/outputs/flutter-apk/app-release.apk

# Or use Firebase Distribution
TASKFILE_PLATFORM=android taskfile --env staging run deploy-firebase
```

## Troubleshooting

### iOS Signing Issues

```bash
# Reset certificates
cd ios && fastlane match nuke development
cd ios && fastlane match nuke appstore
taskfile run setup-ios-cert
```

### Android Keystore Issues

```bash
# Verify keystore
keytool -list -v -keystore android/app/keystore.jks

# Check signing config
cd android && ./gradlew signingReport
```

### Play Store Rejection

Check:
1. Privacy policy URL set
2. Content rating completed
3. App category selected
4. Screenshots uploaded

## See Also

- [Flutter Deployment Docs](https://docs.flutter.dev/deployment/cd)
- [Fastlane iOS](https://docs.fastlane.tools/getting-started/ios/setup/)
- [Fastlane Android](https://docs.fastlane.tools/getting-started/android/setup/)
- [Firebase App Distribution](https://firebase.google.com/docs/app-distribution)
