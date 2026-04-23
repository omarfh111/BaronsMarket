# Frontend - Flutter Mobile App

## Features

- Home screen with store branding
- Camera capture and backend inference call
- Top predictions with confirm/reject flow
- Cart with quantity merge and running total
- Checkout QR generation

## Flutter dependencies

Defined in `pubspec.yaml`:

- provider
- http + http_parser
- image_picker
- qr_flutter
- flutter_spinkit
- audioplayers
- flutter_launcher_icons (dev dependency)

## System requirements

- Flutter SDK (`3.41.x` tested)
- Android Studio
- Android SDK + platform-tools + build-tools + command-line tools
- Android licenses accepted

## Setup

```powershell
cd frontend
flutter pub get
```

Generate launcher icon from `assets/logo_app.png`:

```powershell
flutter pub run flutter_launcher_icons:main
```

## Run options

Android emulator:

```powershell
flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8000
```

Physical phone (same Wi-Fi as backend PC):

```powershell
flutter run --dart-define=API_BASE_URL=http://<PC_LOCAL_IP>:8000
```

## Build APK

```powershell
flutter build apk --release --dart-define=API_BASE_URL=http://<PC_LOCAL_IP>:8000
```

APK location:

- `build/app/outputs/flutter-apk/app-release.apk`

## Assets

- `assets/monoprix_logo.png` -> shown in app UI
- `assets/logo_app.png` -> app launcher icon source
- `assets/sounds/add_to_cart.mp3` -> optional sound

## Notes

- Android cleartext HTTP is enabled for local backend testing.
- If sound file is missing, app continues without crash.
