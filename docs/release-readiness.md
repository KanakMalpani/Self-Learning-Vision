# Release Readiness

Use this checklist before making the repository public.

## Artifact Safety

- Do not commit uploads, enrolled face references, unknown samples, unknown clusters, local databases, generated reports, logs, or local embeddings.
- Keep only synthetic fixtures that are intentionally created for tests.
- Rotate local secrets before sharing screenshots, logs, or environment files.
- Confirm `.env` is not committed; publish `.env.example` only.

## Default Configuration

- `AUTH_ENABLED=false` is acceptable for a local demo. Enable auth and rotate `JWT_SECRET` for broader deployments.
- `ENABLE_FACE_MATCHING=true` tries the strongest available local embedding provider.
- The default app works without paid APIs or hosted identity services.
- Public API docs use Memory Run language.
- Provider docs explain local/free and paid/hosted paths.
- Evaluation docs and `/evaluation` define matching, clustering, provider scorecards, quality, and privacy checks.
- Frontend CI runs tests, typecheck, and production build.
- CodeQL scans the Python API, web application, and Rust desktop shell.
- Dependabot groups security updates for Python, npm, Cargo, and GitHub Actions dependencies without opening routine alpha version-bump noise.
- Data export and purge endpoints exist for local memory control.
- SQLite developer mode is documented for zero-config local API work.

## Verification Commands

Backend tests:

```bash
cd apps/api
pytest -q
```

Frontend checks:

```bash
cd apps/web
npx tsc --noEmit
npm test
```

Repository hygiene:

```bash
git status --short --ignored
make scan-public
```

Desktop release tooling:

```bash
python -m unittest discover -s scripts/tests -p "test_*.py"
python scripts/release_artifacts.py verify-tag --tag v0.3.0-alpha.1
```

After building a platform's frozen API sidecar, verify its desktop-safe runtime
contract on that same operating system:

```bash
python scripts/smoke_desktop_sidecar.py --target windows-x64
```

Use `macos-x64`, `macos-arm64`, or `linux-x64` on their native build runners.

## Clean Startup

```bash
cp .env.example .env
docker compose up --build
```

Expected local URLs:

- Web: http://localhost:3000
- API: http://localhost:8000

## Launch Materials

- Follow [First Five Minutes](first-five-minutes.md) on a clean checkout.
- Capture only public-safe screenshots from a clean demo environment.
- Use [Demo Walkthrough](demo-walkthrough.md) for a short launch video or README demo.
- Follow [GitHub Launch Checklist](github-launch-checklist.md) before the first public push.
- Follow [Desktop Release Checklist](desktop-release-checklist.md) before publishing desktop installers.
- Enable GitHub private vulnerability reporting before distributing public desktop downloads.

## Tracked Linux Alpha Advisory

- The Linux Tauri dependency tree currently inherits `glib 0.18.5` through
  Tauri's GTK3 dependency (`gtk 0.18.2`). GitHub reports an advisory fixed in
  `glib 0.20.0`, but Cargo cannot select that version while GTK requires
  `glib ^0.18`.
- Keep this alert open and reassess it before publishing Linux downloads or
  when the Tauri/GTK dependency chain offers a compatible patched release.
