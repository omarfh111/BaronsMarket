# Frontend - Flutter Android App

## Features

- Product scan and AI prediction confirmation
- Cart with quantity merge
- Checkout QR bill
- Checkout queue recommendation display from backend latest queue API

## Tooling Requirements

- Flutter SDK `3.41.x` (tested)
- Android Studio
- Android SDK:
  - Platform Tools
  - Build Tools
  - Command-line Tools
- Accepted Android licenses

## Installation Steps (Windows)

1. Verify Flutter:

```powershell
flutter --version
flutter doctor
```

2. If Flutter command is missing:

```powershell
$env:Path += ";C:\src\flutter\bin"
flutter --version
```

3. Configure Android SDK path if needed:

```powershell
flutter config --android-sdk "C:\Android\Sdk"
flutter doctor --android-licenses
flutter doctor
```

4. Install project deps:

```powershell
cd frontend
flutter pub get
```

## App Icon

Uses `assets/logo_app.png`.

Generate icon:

```powershell
flutter pub run flutter_launcher_icons:main
```

## Run (Debug)

Android emulator:

```powershell
flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8000
```

Physical phone:

```powershell
flutter run --dart-define=API_BASE_URL=http://<PC_LOCAL_IP>:8000
```

## Build APK (Release)

```powershell
flutter build apk --release --dart-define=API_BASE_URL=http://<PC_LOCAL_IP>:8000
```

Output:
- `build/app/outputs/flutter-apk/app-release.apk`

## Assets

- `assets/monoprix_logo.png`: UI branding
- `assets/logo_app.png`: launcher icon
- `assets/sounds/add_to_cart.mp3`: optional feedback sound

## Notes

- Android cleartext HTTP is enabled for local backend access.
- Rebuild APK after backend contract changes reflected in frontend models.
