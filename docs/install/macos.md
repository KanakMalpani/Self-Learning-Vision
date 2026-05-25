# Install On macOS

## Choose A Download

- Apple Silicon: `Self-Learning-Vision-*-macos-arm64.dmg`
- Intel Mac: `Self-Learning-Vision-*-macos-x64.dmg`

To check your architecture in Terminal:

```bash
uname -m
```

Use the Apple Silicon download for `arm64` and the Intel download for `x86_64`.

## Verify The Download

```bash
shasum -a 256 Self-Learning-Vision-*-macos-*.dmg
```

Compare the result with `SHA256SUMS.txt` on the GitHub Release page.

## Install And Open

1. Open the `.dmg`.
2. Move Self-Learning Vision into Applications.
3. Open the application.
4. Because this alpha is unsigned, macOS may block the first launch. Right-click
   the app and choose **Open**, or approve it in System Settings.

Do not disable macOS security protections globally to run the alpha.

## Local Data

Data is stored under:

```text
~/Library/Application Support/com.selflearningvision.desktop
```

Removing the app does not automatically remove this local data directory.
