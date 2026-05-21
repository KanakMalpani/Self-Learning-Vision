# Download Desktop Alpha

Self-Learning Vision desktop alpha is designed for people who want to open one app and use local visual memory without installing Docker, Postgres, Node, or Python.

The desktop alpha is unsigned. Windows and macOS may show unknown-publisher warnings until code signing is added.

## Choose Your Platform

Download artifacts from GitHub Releases:

- Windows: `Self-Learning-Vision-*-windows-x64-setup.exe`
- Windows portable: `Self-Learning-Vision-*-windows-x64-portable.zip`
- macOS Intel: `Self-Learning-Vision-*-macos-x64.dmg`
- macOS Apple Silicon: `Self-Learning-Vision-*-macos-arm64.dmg`
- Linux portable: `Self-Learning-Vision-*-linux-x64.AppImage`
- Linux Debian/Ubuntu: `Self-Learning-Vision-*-linux-x64.deb`

Use `SHA256SUMS.txt` from the release page to verify downloads.

## Windows

Run the setup `.exe`. Windows SmartScreen may say the publisher is unknown because the alpha is unsigned. Choose the portable `.zip` if you cannot run installers on your machine.

## macOS

Open the `.dmg` for your CPU type. If macOS blocks the app, right-click the app and choose **Open**, or approve it from System Settings. This warning is expected for the unsigned alpha.

## Linux

For AppImage:

```bash
chmod +x Self-Learning-Vision-*-linux-x64.AppImage
./Self-Learning-Vision-*-linux-x64.AppImage
```

For Debian/Ubuntu:

```bash
sudo apt install ./Self-Learning-Vision-*-linux-x64.deb
```

## What The Desktop App Includes

- Static Self-Learning Vision web UI.
- Bundled local FastAPI sidecar.
- SQLite database under your user app-data folder.
- Local JSON learning registries.
- Local-only privacy defaults.

The desktop alpha does not bundle Postgres, Redis, Celery, pgvector, InsightFace, or hosted AI providers.

## Local Data Location

The desktop app stores user data outside the installed application:

- Windows: `%APPDATA%/Self-Learning Vision`
- macOS: `~/Library/Application Support/Self-Learning Vision`
- Linux: `$XDG_DATA_HOME/self-learning-vision` or `~/.local/share/self-learning-vision`

Use the Settings page to export or purge local memory. Deleting the app does not necessarily delete this data folder.

## Advanced Docker Path

Docker remains the best path for developers, server-style deployments, Postgres, pgvector, Redis/Celery, and optional InsightFace:

```bash
cp .env.example .env
docker compose up --build
```

## Alpha Limitations

- Unsigned installers.
- No auto-updater.
- No Android/iOS app.
- Desktop app binds the backend only to `127.0.0.1`.
- Desktop alpha uses lightweight local dependencies for packaging stability.
