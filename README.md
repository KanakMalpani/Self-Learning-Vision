# Self-Learning Vision

[![CI](https://github.com/KanakMalpani/Self-Learning-Vision/actions/workflows/ci.yml/badge.svg)](https://github.com/KanakMalpani/Self-Learning-Vision/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Self-Learning Vision is a local-first vision memory app. It detects faces in uploaded images, lets you enroll people into your own local memory, recognizes them later, and learns from repeated unknown faces by suggesting enrollment when someone becomes familiar. The core memory model is expandable beyond faces into objects, places, scenes, events, and user-defined visual domains.

The default release is intentionally local and personal. It does not require a public identity database, paid API, or cloud recognition service.

## First Five Minutes

```bash
cp .env.example .env
docker compose up --build
```

Open http://localhost:3000, upload an image you are allowed to use, run a memory check, enroll a person, then open the Review Inbox to see how active and passive learning decisions are surfaced for review.

For the guided path, see [First Five Minutes](docs/first-five-minutes.md). For a demo script, see [Demo Walkthrough](docs/demo-walkthrough.md).

## What It Does

- Upload an image and detect visible faces.
- Select a face and compare it against locally enrolled identities.
- Enroll someone with a name or alias, notes, and tags.
- Recall memory context, seen count, and last seen time on future uploads.
- Store useful unknown faces locally.
- Cluster repeated unknown faces.
- Suggest adding a familiar unknown only after repeated sightings.
- Promote an unknown cluster into a named identity only after user confirmation.
- Store generic memory entities across built-in or custom domains.
- Start new memories from templates for people, objects, places, scenes, events, documents, products, and inventory.
- Let users define domain-specific attributes and schemas.
- Explain memory confidence with a local confidence ledger.
- Queue domain-specific active-learning questions for structured memories.
- Capture redacted passive learning signals without storing raw images or embeddings.
- Rank active-learning questions by expected value, risk, uncertainty, and memory health.
- Review questions, contradictions, low-health memories, and replay suggestions in one Review Inbox.
- Choose conservative, balanced, or experimental learning policy presets.
- Search local memories across labels, tags, notes, and attributes.
- Queue active-learning questions when the system needs user confirmation.
- Correct memory with rename, not-this, merge, split, forget, and undo flows.
- Track memory lifecycle with reinforcement, decay, contradiction, and stale states.
- Score memory health and group evidence bundles so users can see why a memory is trusted.
- Edit memory fields, rename memories, archive them, or mark them as incorrect from the detail page.
- View a learning timeline for each memory.
- Replay learning after corrections so related signals and questions can be resolved together.
- Export/import a redacted privacy vault, with encrypted vault support.
- Choose providers through a privacy-aware provider marketplace.
- Register local model/provider plugins with JSON manifests.
- Measure learning quality with a redacted evaluation dashboard and provider scorecards.

## Why It Is Different

Self-Learning Vision is built around a consent-forward learning loop:

- The app learns from user-confirmed identity references, not public identity scraping.
- Unknown people stay unknown until the user names them.
- Tentative matches are shown cautiously and do not update memory as trusted sightings.
- Existing memories can be reinforced automatically only after repeated high-confidence evidence.
- New trusted person identities still require user review.
- Providers are replaceable, so users can stay free/local or bring their own hosted model.

## Free And Paid Provider Paths

Self-Learning Vision works out of the box with the free/local path. Paid or hosted AI providers are optional extensions, not requirements.

- Free/local: run the default Docker app and local recognition pipeline.
- Paid/hosted: implement a custom `FaceEmbeddingProvider` and add any SDKs to an optional requirements file.
- Bring-your-own: connect your own model server, edge device, or internal embedding API behind the same provider contract.

See [docs/provider-guide.md](docs/provider-guide.md).

## Public Standard

The project includes a reference standard for building responsible self-learning vision systems:

- [Self-Learning Vision Standard](docs/self-learning-vision-standard.md)
- [Evaluation Guide](docs/evaluation.md)
- [First Five Minutes](docs/first-five-minutes.md)
- [First Run](docs/first-run.md)
- [Demo Walkthrough](docs/demo-walkthrough.md)
- [GitHub Launch Checklist](docs/github-launch-checklist.md)
- [Data Controls](docs/data-controls.md)
- [Memory Domains](docs/memory-domains.md)
- [Memory Quality Toolkit](docs/memory-quality-toolkit.md)
- [Active Learning](docs/active-learning.md)
- [Learning Review](docs/learning-review.md)
- [Correction UX](docs/correction-ux.md)
- [Memory Lifecycle](docs/memory-lifecycle.md)
- [Privacy Vault](docs/privacy-vault.md)
- [Provider Marketplace](docs/provider-marketplace.md)
- [Demo Fixtures](docs/demo-fixtures.md)
- [Evaluation Dashboard](docs/evaluation-dashboard.md)
- [Architecture](docs/architecture.md)
- [Privacy](docs/privacy.md)
- [Usage Policy](docs/usage-policy.md)
- [Security](SECURITY.md)

## Run With Docker

```bash
cp .env.example .env
docker compose up --build
```

Open:

- Web: http://localhost:3000
- API: http://localhost:8000

## Local Development

Backend:

```bash
cd apps/api
pip install -r requirements.txt -c constraints.txt
uvicorn app.main:app --reload --port 8000
```

Frontend:

```bash
cd apps/web
npm install
npm run dev
```

## Provider Model

The backend is designed around replaceable detection and embedding providers. The default configuration tries InsightFace/ArcFace when available and falls back to a local deterministic embedding provider for development and demos.

You can extend `apps/api/app/services/recognition.py` to plug in other local models, hosted APIs, or custom embedding systems while keeping the same enrollment and recognition API.

Public-facing Memory Run endpoints:

- `POST /api/v1/memory-runs`
- `GET /api/v1/memory-runs`
- `GET /api/v1/memory-runs/{id}`
- `POST /api/v1/memory-runs/{id}/reference`
- `GET /api/v1/memory-run-events/stream`
- `GET /api/v1/memory-domains`
- `GET /api/v1/memory-domain-templates`
- `GET /api/v1/memory-domain-templates/{id}`
- `POST /api/v1/memory-domain-templates/{id}/entities`
- `GET /api/v1/memory-entities`
- `GET /api/v1/memory-entities/search`
- `POST /api/v1/memory-entities`
- `PATCH /api/v1/memory-entities/{id}`
- `GET /api/v1/memory-entities/{id}/detail`
- `GET /api/v1/memory-entities/{id}/confidence-ledger`
- `POST /api/v1/memory-entities/{id}/active-learning/domain-review`
- `POST /api/v1/memory-entities/{id}/learning/replay`
- `GET /api/v1/learning/signals`
- `GET /api/v1/learning/policy`
- `PUT /api/v1/learning/policy`
- `GET /api/v1/learning/policy/simulation`
- `GET /api/v1/learning/review-inbox`
- `POST /api/v1/learning/signals/{id}/dismiss`
- `GET /api/v1/active-learning/questions`
- `POST /api/v1/active-learning/questions/{id}/response`
- `GET /api/v1/corrections`
- `POST /api/v1/corrections/{id}/undo`
- `GET /api/v1/memory-lifecycle/summary`
- `POST /api/v1/memory-lifecycle/decay-stale`
- `POST /api/v1/memory-entities/{id}/lifecycle/reinforce`
- `POST /api/v1/memory-entities/{id}/lifecycle/contradiction`
- `GET /api/v1/privacy/settings`
- `PUT /api/v1/privacy/settings`
- `GET /api/v1/data/export`
- `POST /api/v1/data/vault/export`
- `POST /api/v1/data/vault/import`
- `GET /api/v1/providers`
- `GET /api/v1/provider-plugins`
- `GET /api/v1/provider-conformance`
- `GET /api/v1/providers/selection`
- `PUT /api/v1/providers/selection`
- `GET /api/v1/evaluation/summary`
- `GET /api/v1/evaluation/metrics`
- `GET /api/v1/evaluation/dataset`
- `GET /api/v1/evaluation/provider-scorecard`
- `GET /api/v1/evaluation/benchmark-pack`
- `GET /api/v1/evaluation/benchmark-runs`
- `POST /api/v1/evaluation/benchmark-runs`
- `DELETE /api/v1/data/purge`

## Safety Boundary

Self-Learning Vision is for personal, local memory. Do not use it for surveillance, covert identification, or decisions that affect employment, housing, credit, access, legal rights, or safety.

Face images, embeddings, uploaded files, reference registries, unknown samples, and generated artifacts are ignored by Git by default.

## License

MIT License. See [LICENSE](LICENSE).
