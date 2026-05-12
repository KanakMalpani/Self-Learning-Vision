# Learning Review

The Review Inbox is the main workspace for active and passive learning. It turns
memory uncertainty into small, auditable decisions.

## What It Shows

- Highest-value active-learning questions.
- Contradiction signals from corrections, rejected matches, or duplicate labels.
- Candidate memories that are ready for review.
- Low-health memories that may need confirmation or cleanup.
- Replay suggestions that apply one correction across related signals.
- Recent passive learning signals.
- Learning policy preset and policy simulation.

## Passive Signals

Passive signals are redacted metadata records. They can describe:

- tentative matches;
- familiar unknown clusters;
- manual or automatic reinforcement;
- corrections;
- contradictions;
- candidate review;
- learning replay.

Signals never store raw images, upload paths, biometric embeddings, or provider
secrets. Hosted providers can produce signals, but the stored contract remains
provider-neutral.

## Balanced Auto

The system may automatically reinforce an existing memory when repeated
high-confidence evidence supports it. New trusted person identities still require
user action. Archived, forgotten, and uncertain memories are not auto-reinforced.

## Policy Presets

Users can choose:

- `conservative`: no auto reinforcement and a smaller review budget;
- `balanced`: auto-reinforce existing memories after repeated strong evidence;
- `experimental`: lower reinforcement thresholds and a larger review budget.

The simulator previews how many memories would be auto-reinforced, moved to
review, or blocked before the policy changes learning behavior.

## Memory Health

Each memory receives a health state:

- `stable`: evidence is consistent and confidence is healthy;
- `watch`: memory is useful but needs more evidence or freshness;
- `needs_review`: contradictions, low confidence, or pending questions need user attention.

Health considers confidence, observations, lifecycle events, corrections,
contradictions, passive signals, and freshness.

## Learning Replay

Replay applies a correction or conflict signal across related learning state. It
can resolve passive signals, create a targeted review question, and add a
lifecycle contradiction when needed. Replay is local and auditable.

## Memory Detail

The memory detail page supports direct learning maintenance:

- edit attributes and notes;
- rename;
- mark not-this;
- archive;
- answer linked review questions;
- inspect the learning timeline.

## API

```http
GET  /api/v1/learning/signals
GET  /api/v1/learning/policy
PUT  /api/v1/learning/policy
GET  /api/v1/learning/policy/simulation
GET  /api/v1/learning/review-inbox
POST /api/v1/learning/signals/{signal_id}/dismiss
PATCH /api/v1/memory-entities/{entity_id}
POST /api/v1/memory-entities/{entity_id}/learning/replay
```
