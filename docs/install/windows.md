# Install On Windows

## Choose A Download

- Setup installer: `Self-Learning-Vision-*-windows-x64-setup.exe`
- Portable build: `Self-Learning-Vision-*-windows-x64-portable.zip`

The setup installer is the simplest option. The portable build is for machines
where you cannot or do not want to install an application.

## Verify The Download

In PowerShell, run:

```powershell
Get-FileHash .\Self-Learning-Vision-*-windows-x64-setup.exe -Algorithm SHA256
```

Compare the hash with `SHA256SUMS.txt` on the same GitHub Release page. For the
portable build, run the same command against the `.zip` file.

## Setup Installer

1. Open the setup `.exe`.
2. If SmartScreen displays an unknown publisher warning, review the filename and
   checksum, then select the option to continue.
3. Complete installation and open Self-Learning Vision.

The unsigned alpha includes the Microsoft WebView2 bootstrapper so the installer
can provide the UI runtime when it is missing.

## Portable Build

1. Extract the entire `.zip` folder.
2. Keep `Self-Learning Vision.exe` and its sidecar executable together.
3. Open `Self-Learning Vision.exe`.

The portable build requires Microsoft Edge WebView2 Runtime to already be
installed.

## Local Data

Data is stored under:

```text
%APPDATA%/com.selflearningvision.desktop
```

Removing the app does not automatically remove this data directory. Use the
application data controls before deleting local files manually.
