# Provider Marketplace

Phase 6 adds a provider marketplace layer for local, hosted, paid, and custom vision
backends.

## Capabilities

Providers can advertise these capabilities:

- `face_embedding`
- `face_detection`
- `object_detection`
- `image_classification`
- `captioning`
- `ocr`
- `multimodal_reasoning`

The current app uses `face_embedding` for the ready-to-use face memory workflow.
Other capabilities are marketplace-ready extension points for broader vision domains.

## Provider Cards

Each provider card documents:

- provider id;
- display name;
- mode: local/free, hosted/paid, hosted/internal;
- capabilities;
- readiness status;
- whether images leave the device;
- whether embeddings are stored locally;
- environment variables;
- expected dimensions;
- latency profile;
- cost model;
- setup instructions;
- privacy notes.

## Built-In Cards

- `local-face-embedding`: default local/free face embedding provider.
- `insightface`: optional local InsightFace/ArcFace provider.
- `template-paid-provider`: hosted/paid provider template.
- `custom-http-provider`: template for self-hosted, edge, or internal HTTP providers.

## API

```http
GET /api/v1/providers
GET /api/v1/provider-plugins
GET /api/v1/provider-conformance
GET /api/v1/providers/selection
PUT /api/v1/providers/selection
```

Example selection request:

```json
{
  "capability": "face_embedding",
  "provider_id": "local-face-embedding"
}
```

## Privacy Guardrails

Hosted providers are blocked when local-only policy is active:

```env
PRIVACY_LOCAL_ONLY_MODE=true
PRIVACY_ALLOW_HOSTED_PROVIDERS=false
```

To use a hosted provider, the user must explicitly change both the environment-level
privacy policy and the user privacy settings.

## Provider Contracts

Provider contracts live in `apps/api/app/providers/base.py`:

- `FaceEmbeddingProvider`
- `VisionDetectionProvider`
- `ImageClassificationProvider`
- `ImageCaptionProvider`
- `OCRProvider`
- `MultimodalReasoningProvider`

Provider implementations should fail closed, document data transfer clearly, and keep
free/local mode working without paid accounts.

The conformance endpoint checks provider metadata for capability declarations,
privacy notes, hosted-transfer labeling, cost model, setup instructions, and runtime
entrypoints for executable manifest plugins.

## File-Backed Plugin Registry

Provider cards can be registered with JSON manifests in:

```text
apps/api/app/providers/manifests/*.json
```

Additional local manifest folders can be provided with:

```env
PROVIDER_PLUGIN_DIRS=C:\path\to\my-provider-manifests;D:\another-folder
```

Each manifest can advertise capabilities, privacy behavior, cost model, setup notes,
and an optional Python entrypoint:

```json
{
  "provider_id": "local-dev-face-embedding",
  "display_name": "Local Dev Face Embedding Plugin",
  "mode": "local_free",
  "capabilities": ["face_embedding"],
  "status": "manifest_ready",
  "images_leave_device": false,
  "entrypoint": "app.providers.local:LocalFaceEmbeddingProvider",
  "cost_model": "free"
}
```

When an entrypoint is present for `face_embedding`, the backend can instantiate it
after the user selects that provider. Manifests without entrypoints still appear in
the marketplace as roadmap-ready local model slots for OCR, classification,
captioning, detection, or multimodal reasoning.

Included example manifests:

- `local-dev-face-embedding`: executable local face-embedding plugin.
- `local-openclip-classifier`: local image classification and reasoning slot.
- `local-tesseract-ocr`: local OCR slot for document and inventory templates.
