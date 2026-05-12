# Privacy Vault

Phase 5 adds a privacy-first vault layer for export, import, redaction, and local-only
provider controls.

## Defaults

The default release is local-only:

- hosted providers are blocked unless explicitly enabled;
- biometric embeddings are not included in public exports;
- unknown-cluster centroid embeddings are not included in exports;
- upload file paths are hidden unless the user opts in;
- domain visibility can hide entire memory domains from export.

## API

```http
GET  /api/v1/privacy/settings
PUT  /api/v1/privacy/settings
GET  /api/v1/data/export
POST /api/v1/data/vault/export
POST /api/v1/data/vault/import
DELETE /api/v1/data/purge
```

## Plain Vault Export

Plain vault export wraps the same redacted payload returned by `GET /api/v1/data/export`:

```json
{
  "format": "self-learning-vision.vault.v1",
  "encrypted": false,
  "payload": {}
}
```

## Encrypted Vault Export

Encrypted vault export uses `cryptography` and a passphrase-derived Fernet key:

```json
{
  "format": "self-learning-vision.vault.v1",
  "encrypted": true,
  "kdf": "PBKDF2HMAC-SHA256",
  "iterations": 390000,
  "salt": "...",
  "ciphertext": "..."
}
```

The encrypted envelope does not expose memory entities, corrections, active-learning
questions, upload metadata, or labels outside the ciphertext.

## Import

Vault import currently restores or merges generic `MemoryEntity` records from a plain
or encrypted vault payload. It does not import raw uploads, embeddings, or unknown
face samples.

## Provider Guardrails

Environment defaults:

```env
PRIVACY_LOCAL_ONLY_MODE=true
PRIVACY_ALLOW_HOSTED_PROVIDERS=false
```

If a hosted/paid embedding provider is requested while local-only policy is active,
the backend blocks that provider and falls back to no hosted matching.

Provider marketplace selection uses the same guardrails. Hosted or paid cards are
reported as `blocked_by_privacy_policy` until hosted providers are explicitly allowed.

## Storage

Privacy settings live under:

```text
STORAGE_DIR/privacy-settings/{user_id}/settings.json
```

This folder is ignored by Git.
