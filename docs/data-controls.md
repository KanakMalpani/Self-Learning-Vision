# Data Controls

Self-Learning Vision stores user memory locally. Public releases should make those boundaries visible and easy to manage.

## API Controls

- `GET /api/v1/data/export` exports the current user's memory metadata, correction history, active-learning questions, passive learning signals, generic memory entities, Memory Runs, upload metadata, identity references, and unknown clusters.
- `GET /api/v1/learning/policy` and `PUT /api/v1/learning/policy` expose local learning policy presets.
- `POST /api/v1/data/vault/export` exports a plain or encrypted privacy vault.
- `POST /api/v1/data/vault/import` imports memory entities from a plain or encrypted privacy vault.
- `DELETE /api/v1/data/purge` deletes the current user's uploads, Memory Runs, correction history, active-learning questions, passive learning signals, generic memory entities, identity references, and unknown face registry data.

The export endpoint intentionally excludes raw embeddings from identity references and unknown-cluster centroids by default. Upload file paths are also excluded unless explicitly enabled in privacy settings. Treat embeddings as biometric data.

## Storage Paths

- Uploads: `STORAGE_DIR`
- Identity references: `STORAGE_DIR/face-references/{user_id}`
- Generic memory entities: `STORAGE_DIR/memory-entities/{user_id}`
- Active-learning questions: `STORAGE_DIR/active-learning/{user_id}`
- Passive learning signals: `STORAGE_DIR/learning-signals/{user_id}`
- Learning policy: `STORAGE_DIR/learning-policy/{user_id}`
- Correction logs: `STORAGE_DIR/corrections/{user_id}`
- Privacy settings: `STORAGE_DIR/privacy-settings/{user_id}`
- Provider selections: `STORAGE_DIR/provider-selections/{user_id}`
- Unknown samples and clusters: `STORAGE_DIR/unknown-faces/{user_id}`

## Product Requirements

A polished UI should expose:

- Export my memory.
- Export encrypted vault.
- Import vault.
- Configure domain export visibility.
- Review and change provider selections.
- Delete a Memory Run.
- Delete an upload.
- Delete an identity reference.
- Delete an unknown cluster.
- Review, answer, or dismiss active-learning questions.
- Review or dismiss passive learning signals.
- Choose a learning policy preset and preview it with the simulator.
- Apply learning replay from memory detail or the Review Inbox.
- Rename, merge, split, forget, and undo memory corrections.
- Purge all local memory.

Every destructive action should require explicit confirmation.
