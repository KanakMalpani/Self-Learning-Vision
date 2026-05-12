# Providers

Providers are the extension point for free/local, paid/hosted, or internal embedding systems.

Start with:

- `base.py`: provider contract.
- `local.py`: local development provider alias.
- `insightface_provider.py`: InsightFace/ArcFace provider alias.
- `template_paid_provider.py`: copy this for hosted or paid integrations.
- `manifests/*.json`: file-backed provider plugin cards.
- `base.py` also includes marketplace-ready contracts for detection, classification, captioning, OCR, and multimodal reasoning.

Provider rules:

- Keep local/free as the default.
- Do not send images remotely unless explicitly configured.
- Document image transfer, embedding storage, dimensions, latency, and cost.
- Fail closed and fall back locally when possible.

Provider marketplace metadata lives in `app/services/provider_marketplace.py`.
Executable local plugins can expose an entrypoint like
`app.providers.local:LocalFaceEmbeddingProvider`; roadmap/provider slots can omit
the entrypoint and still appear in the marketplace.
