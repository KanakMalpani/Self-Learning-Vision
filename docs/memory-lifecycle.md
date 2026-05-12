# Memory Lifecycle

Phase 4 gives every `MemoryEntity` a lifecycle, confidence history, reinforcement,
decay, and contradiction handling.

## Lifecycle States

Supported states:

- `candidate`
- `confirmed`
- `uncertain`
- `stale`
- `archived`
- `forgotten`

These states apply to people, objects, places, scenes, events, and custom user
domains.

## Lifecycle Events

Each memory can record lifecycle events:

- `reinforced`
- `decayed`
- `contradiction`
- `not_this`

Each event stores:

- previous state;
- new state;
- confidence before;
- confidence after;
- reason;
- timestamp.

This creates a local confidence history without needing raw images or embeddings in
the lifecycle payload.

## API

```http
GET  /api/v1/memory-lifecycle/summary
POST /api/v1/memory-lifecycle/decay-stale
POST /api/v1/memory-entities/{entity_id}/lifecycle/reinforce
POST /api/v1/memory-entities/{entity_id}/lifecycle/contradiction
```

## Reinforcement

Reinforcement raises confidence and usually moves a memory toward `confirmed`.

Typical triggers:

- user confirms an active-learning question;
- user manually verifies a memory;
- repeated high-confidence observation occurs.

## Decay

Decay lowers confidence for active memories that have not received reinforcing
observations for a configurable number of days. Confirmed memories can become
`stale`.

Decay does not affect `archived` or `forgotten` memories.

## Contradictions

Contradictions lower confidence and move the memory to `uncertain`.

Typical triggers:

- user marks a match as wrong;
- two labels conflict;
- a correction says an observation belongs somewhere else.

Contradictions are stored in entity attributes and reflected in lifecycle summary
metrics.

## Evaluation Use

The evaluation summary now includes memory lifecycle data:

- state counts;
- domain counts;
- average confidence;
- contradiction count;
- lifecycle event count.

These metrics make the system's learning behavior visible instead of hidden.
