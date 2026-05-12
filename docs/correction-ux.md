# Correction UX

Self-learning systems need fast, explicit correction. Phase 3 adds correction APIs
for generic memory entities and an undo log with local before/after snapshots.

## Correction Actions

Supported actions:

- rename a memory entity;
- archive or forget a memory entity;
- mark a memory as "not this";
- merge duplicate entities;
- split observations into a new entity;
- undo a correction.

These actions operate on the generic `MemoryEntity` layer, so they apply to people,
objects, places, scenes, events, and custom user-defined domains.

## API

```http
POST /api/v1/memory-entities/{entity_id}/corrections/rename
POST /api/v1/memory-entities/{entity_id}/corrections/forget
POST /api/v1/memory-entities/{entity_id}/corrections/not-this
POST /api/v1/memory-entities/{entity_id}/corrections/merge
POST /api/v1/memory-entities/{entity_id}/corrections/split
GET  /api/v1/corrections
POST /api/v1/corrections/{correction_id}/undo
```

## Undo Model

Each correction stores:

- operation type;
- target entity id;
- summary;
- metadata;
- local entity snapshot before the correction;
- local entity snapshot after the correction;
- undo status.

Undo restores the previous entity snapshot and marks the correction as undone.

## Product Requirements

A polished UI should expose correction controls near each memory:

- rename;
- not this;
- merge duplicates;
- split memory;
- archive;
- forget;
- undo last correction.

Destructive actions should require clear confirmation. Undo should be visible after
every correction that changes local memory.

## Safety Boundary

Correction history is user data. It can reveal labels, mistakes, and user decisions,
so it is stored locally and included in export/purge controls. Raw images and
embeddings are not required in correction log payloads.

Corrections that change trust, such as "not this", also create memory lifecycle
events so confidence changes remain auditable.
