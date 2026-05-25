# Install On Linux

## Choose A Download

- Portable AppImage: `Self-Learning-Vision-*-linux-x64.AppImage`
- Debian/Ubuntu package: `Self-Learning-Vision-*-linux-x64.deb`

These alpha downloads target x86_64 Linux systems.

## Verify The Download

```bash
sha256sum Self-Learning-Vision-*-linux-x64.AppImage
sha256sum Self-Learning-Vision-*-linux-x64.deb
```

Compare the hash for the file you use with `SHA256SUMS.txt` on the GitHub
Release page.

## AppImage

```bash
chmod +x Self-Learning-Vision-*-linux-x64.AppImage
./Self-Learning-Vision-*-linux-x64.AppImage
```

## Debian Or Ubuntu

```bash
sudo apt install ./Self-Learning-Vision-*-linux-x64.deb
```

## Local Data

Data is stored under:

```text
$XDG_DATA_HOME/com.selflearningvision.desktop
```

If `XDG_DATA_HOME` is unset, the fallback location is:

```text
~/.local/share/com.selflearningvision.desktop
```

Removing an AppImage or uninstalling the package does not automatically remove
your local application data.
