# GitHub Launch Checklist

Use this before making the repository public.

## Repository Settings

- Set the repo description to: `Local-first self-learning vision memory app with active review, passive signals, and explainable memory health.`
- Add topics: `computer-vision`, `face-recognition`, `active-learning`, `local-first`, `privacy`, `fastapi`, `nextjs`, `open-source`.
- Confirm the default branch is protected after the first public push.
- Require CI for pull requests once the workflow is green.
- Enable Dependabot or another dependency update flow when you are ready to maintain public updates.

## README Readiness

- Keep the first screen focused on what the app does.
- Keep install commands near the top.
- Link to First Five Minutes, Demo Walkthrough, Security, and Contributing.
- Use screenshots only from a clean demo environment.
- Do not promise production surveillance or public identity lookup.

## Public Safety

- Confirm no uploads, local databases, embeddings, generated reports, logs, or local provider state are committed.
- Confirm `.env` is not committed.
- Confirm `.env.example` contains placeholders only.
- Confirm public docs do not include private machine paths.
- Confirm demo media is consented, synthetic, or intentionally public-safe.

## Verification

```bash
make verify
make build-web
```

Run the repository hygiene scan:

```bash
make scan-public
```

Also inspect `git status --short --ignored` before the first public push.

## First Release

Suggested release title:

```text
Self-Learning Vision v0.1.0 - Local-first memory, review, and learning controls
```

Suggested release notes:

```text
Initial public release of Self-Learning Vision.

- Local-first face memory workflow.
- Review-gated person enrollment.
- Passive learning signals and ranked active-learning questions.
- Review Inbox for questions, contradictions, candidates, low-health memories, and replay suggestions.
- Evidence bundles, memory health, lifecycle policy, and correction replay.
- Provider-neutral architecture with local/free default path and optional hosted provider hooks.
- Data export, encrypted vault export/import, purge controls, and public-safety documentation.
```

