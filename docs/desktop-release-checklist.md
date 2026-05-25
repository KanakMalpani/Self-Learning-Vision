# Desktop Release Checklist

Use this checklist for an unsigned desktop alpha release. It prevents a configured
platform from being presented as verified before its native artifact has actually
been built and opened.

## Release Outputs

| Platform | Artifact | Build Evidence Required |
| --- | --- | --- |
| Windows x64 | setup `.exe` and portable `.zip` | Windows frozen-sidecar gate and manual launch |
| macOS Intel | `.dmg` | Intel frozen-sidecar gate and manual launch |
| macOS Apple Silicon | `.dmg` | Apple Silicon frozen-sidecar gate and manual launch |
| Linux x64 | `.AppImage` and `.deb` | Linux frozen-sidecar gate and manual launch |

The GitHub release workflow refuses to publish unless all six named downloads are
present, the Windows portable ZIP contains only its allowlisted files, and the
release tag agrees with the Tauri, npm, and Cargo desktop versions.

Each native build also launches the frozen API sidecar before packaging and
verifies loopback-only readiness, local storage/provider modes, protected
shutdown, and complete process termination.

## Before Tagging

1. Confirm that the intended version is identical in:
   - `apps/desktop/package.json`
   - `apps/desktop/src-tauri/Cargo.toml`
   - `apps/desktop/src-tauri/tauri.conf.json`
2. Run the repository checks:

```bash
make verify
python scripts/release_artifacts.py verify-tag --tag v0.3.0-alpha.1
```

3. Open or update a pull request touching desktop release files and wait for
   the `Desktop Alpha Release` packaging and frozen-sidecar smoke matrix to pass
   on Windows, macOS Intel, macOS Apple Silicon, and Linux.
4. Confirm `CodeQL` passes for Python, JavaScript/TypeScript, and Rust changes.
5. Inspect the worktree for local data or generated output:

```bash
git status --short --ignored
```

6. Confirm that documentation still describes the release as unsigned and
   local-first.
7. In repository security settings, enable private vulnerability reporting
   before sharing desktop installers publicly.

## Build And Publication

1. Push an alpha tag matching the desktop version, for example:

```bash
git tag v0.3.0-alpha.1
git push origin v0.3.0-alpha.1
```

2. Wait for every matrix job in `Desktop Alpha Release` to pass.
3. Confirm the prerelease includes:

```text
Self-Learning-Vision-v0.3.0-alpha.1-windows-x64-setup.exe
Self-Learning-Vision-v0.3.0-alpha.1-windows-x64-portable.zip
Self-Learning-Vision-v0.3.0-alpha.1-macos-x64.dmg
Self-Learning-Vision-v0.3.0-alpha.1-macos-arm64.dmg
Self-Learning-Vision-v0.3.0-alpha.1-linux-x64.AppImage
Self-Learning-Vision-v0.3.0-alpha.1-linux-x64.deb
SHA256SUMS.txt
```

## Manual Smoke Test

For each OS artifact:

1. Verify the downloaded checksum against `SHA256SUMS.txt`.
2. Install or extract the app using the OS guide.
3. Launch the app and wait for the local engine to become ready.
4. Use only a synthetic or consented image for an upload test.
5. Open Review Inbox and a memory detail view.
6. Quit the app and confirm no background local API remains running.
7. Relaunch and confirm expected local data persistence.

Do not call macOS or Linux verified until this manual smoke test is recorded for
their native downloads. The automated sidecar gate proves packaged local-engine
behavior; it does not replace opening the final installer UI on that operating
system.

## Safety Gate

- No `.env`, databases, local images, uploads, logs, model caches, or raw
  embeddings are attached to the release.
- The portable ZIP contains only the desktop executable, packaged API sidecar,
  and portable readme.
- Windows and macOS unsigned warnings are documented.
- The desktop backend binds to `127.0.0.1` only.
- No diagnostic data is uploaded automatically.
- Dependabot and CodeQL configuration is present for continuing public-release
  maintenance; their GitHub checks are reviewed before tagging.
