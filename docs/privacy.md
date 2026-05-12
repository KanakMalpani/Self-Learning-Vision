# Privacy

- Local-first: uploaded images, face embeddings, identity references, unknown samples, and unknown clusters are stored under `STORAGE_DIR` and in the local app database you control.
- The default release does not require cloud identity services or paid APIs.
- Local-only mode is enabled by default and blocks hosted/paid providers unless explicitly configured.
- Privacy vault export redacts biometric embeddings, unknown-cluster centroids, and upload paths by default.
- Encrypted vault export uses `cryptography` with a passphrase-derived key.
- Unknown faces are stored only after quality checks and are never named automatically.
- Promotion from an unknown cluster to a named identity requires explicit user action.
- Export or import redacted local memory through the privacy vault APIs.
- Delete local data through `DELETE /api/v1/data/purge`, by removing Docker volumes with `docker compose down -v`, and by clearing `STORAGE_DIR`.
- Rotate secrets such as `JWT_SECRET` and database passwords before any broader deployment.
- Logs may contain timestamps, ids, and event messages; review them before sharing.
