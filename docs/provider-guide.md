# Provider Guide

Self-Learning Vision is designed to work in two modes:

## Free / Local Mode

The default path is local-first and free to run after setup:

- Face detection runs locally.
- Identity references are stored locally.
- Unknown samples and clusters are stored locally.
- Matching uses local embeddings, with an open provider path when available and a deterministic development fallback.
- No paid API key is required for the default demo.

This is the recommended mode for privacy, experimentation, and open-source development.

## Paid / Bring-Your-Own Provider Mode

Teams can add paid or hosted providers without changing the API surface:

- Add an embedding provider in `apps/api/app/services/recognition.py` by implementing `FaceEmbeddingProvider`.
- Read provider credentials from environment variables, never from committed files.
- Keep paid provider SDKs in an optional requirements file or integration-specific documentation.
- Preserve the same recognition states: `matched`, `tentative`, and `unknown`.
- Keep user confirmation required before naming unknown people.

Suggested environment variables for custom integrations:

```env
VISION_PROVIDER=local
EMBEDDING_PROVIDER=auto
PAID_PROVIDER_ENABLED=false
PAID_PROVIDER_API_KEY=
```

## Built-In Provider Choices

- `EMBEDDING_PROVIDER=auto`: try the best available local/open provider, then fall back to the deterministic local provider.
- `EMBEDDING_PROVIDER=local`: force the free local development provider.
- `EMBEDDING_PROVIDER=insightface`: prefer InsightFace/ArcFace when installed, then fall back locally.
- `EMBEDDING_PROVIDER=none`: disable embedding matching.
- `EMBEDDING_PROVIDER=paid`: reserved for explicitly configured hosted or paid providers. The default app falls back locally unless `PAID_PROVIDER_ENABLED=true`.

## Provider SDK Folder

Provider scaffolding lives in `apps/api/app/providers`:

- `base.py` exposes the provider contract.
- `local.py` exposes the built-in local provider.
- `insightface_provider.py` exposes the InsightFace provider.
- `template_paid_provider.py` is a starter class for paid or hosted providers.
- Marketplace metadata and provider selection live in `apps/api/app/services/provider_marketplace.py`.

See [provider-marketplace.md](provider-marketplace.md).

## Provider Contract

A provider should return a stable numeric embedding for a selected face box:

```python
class FaceEmbeddingProvider:
    name: str

    def extract_embedding(self, image_path: str, face_box: dict) -> list[float] | None:
        ...
```

The rest of the system handles quality gates, local identity matching, unknown clustering, and promotion.

Additional marketplace-ready contracts are available for detection, classification,
captioning, OCR, and multimodal reasoning in `apps/api/app/providers/base.py`.

## Provider Card Template

Each provider should document:

```md
### Provider Name

- Mode: local/free, hosted/paid, or internal.
- Images leave device: yes/no.
- Embeddings stored locally: yes/no.
- Environment variables:
- Expected dimensions:
- Latency profile:
- Cost model:
- Failure fallback:
- Recommended thresholds:
```

## Safety Expectations

- Do not send images to third-party providers unless the user has configured that provider intentionally.
- Keep `PRIVACY_LOCAL_ONLY_MODE=true` and `PRIVACY_ALLOW_HOSTED_PROVIDERS=false` unless hosted providers are intentionally enabled.
- Show when a provider is local vs hosted.
- Keep local storage boundaries clear.
- Do not auto-name unknown identities.
