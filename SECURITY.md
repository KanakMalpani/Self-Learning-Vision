# Security Policy

Self-Learning Vision is local-first, but vision memory still deserves careful handling.

## What To Report

Please report:

- Hardcoded secrets or credentials.
- Paths that expose uploads, embeddings, references, unknown samples, or databases.
- Paths that expose generic memory entities or user-defined domain metadata outside the current user scope.
- Paths that expose active-learning questions or user correction responses outside the current user scope.
- Paths that expose correction history or undo snapshots outside the current user scope.
- Privacy vault exports that include raw images, biometric embeddings, unknown-cluster centroids, or upload paths unexpectedly.
- Hosted provider calls that bypass local-only privacy settings.
- Provider selections that allow remote image transfer without explicit user and environment opt-in.
- Provider integrations that send images remotely without explicit configuration.
- Authentication or authorization bypasses.
- Data deletion failures.

## Safe Configuration

- Keep `.env` private.
- Rotate `JWT_SECRET` before any shared deployment.
- Leave paid providers disabled unless intentionally configured.
- Do not commit uploads, embeddings, reference registries, logs, or database files.
- Do not commit local `memory-entities` storage.
- Do not commit local `active-learning` storage.
- Do not commit local `corrections` storage.
- Do not commit local `privacy-settings` storage or exported vault files.
- Do not commit local `provider-selections` storage.
- Review provider documentation before sending images to a hosted API.
- Use `GET /api/v1/data/export` and `DELETE /api/v1/data/purge` to inspect or remove local user memory.

## Desktop Security Boundary

- The desktop sidecar binds only to `127.0.0.1` and does not expose a LAN listener by default.
- Desktop releases keep hosted providers disabled, use SQLite, `local_json`, and inline learning jobs by default.
- The desktop webview can call the bundled app commands but does not receive shell execution or process-spawn permission.
- The desktop content security policy permits backend connections only to the loopback API and Tauri IPC transport, while blocking embedded objects and external framing.
- The desktop-only shutdown route requires a per-launch native token so frozen sidecars exit with the app.
- Desktop user data lives under the Tauri app-data directory for `com.selflearningvision.desktop`, outside the installed application bundle.

## Supported Release Boundary

The public release is intended for personal/local memory, demos, and research. It is not intended for surveillance, public identity lookup, or high-stakes decisions.

## Repository Security Automation

- CodeQL scans the Python API, JavaScript/TypeScript web app, and Rust desktop shell on pull requests, pushes to `main`, and a weekly schedule.
- Dependabot checks Python, npm, Cargo, and GitHub Actions dependencies monthly so updates can be reviewed through normal pull requests.
- Desktop release artifacts are built on their native operating systems and pass frozen-sidecar and public-safety gates before publication.
- Maintainers should enable GitHub private vulnerability reporting for the public repository before publishing installers.
