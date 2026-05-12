# Active Learning

Self-Learning Vision should learn by asking the smallest useful question at the
right time. The active-learning queue is now paired with a passive learning
signal layer, memory health scoring, and a Review Inbox.

## What Triggers A Question

The backend currently creates questions for:

- tentative face matches, when the system has a plausible candidate but should not
  trust it automatically;
- familiar unknown clusters, when the same unknown person has appeared enough times
  to be worth naming;
- domain-specific memory review, when important template fields are missing;
- contradictions, low-health memories, and replay suggestions created by passive
  learning signals.

These are intentionally conservative. The system should avoid turning every low
confidence event into work for the user.

## Queue Storage

Questions are stored locally under:

```text
STORAGE_DIR/active-learning/{user_id}/questions.json
```

Each question includes:

- `question_type`
- `prompt`
- `domain_type`
- `priority`
- `priority_reason`
- `source_signal_ids`
- `learning_value`
- `risk_level`
- `cooldown_until`
- `confidence`
- `memory_run_id`
- `upload_id`
- candidate or unknown-cluster context
- response status

The registry uses dedupe keys so repeated processing of the same upload or cluster
does not create duplicate pending questions.

## API

- `GET /api/v1/active-learning/questions`
- `GET /api/v1/active-learning/questions?status=pending`
- `POST /api/v1/active-learning/questions/{question_id}/response`
- `GET /api/v1/learning/review-inbox`
- `GET /api/v1/learning/signals`
- `POST /api/v1/learning/signals/{signal_id}/dismiss`
- `POST /api/v1/memory-entities/{entity_id}/learning/replay`

Response actions:

- `confirm`
- `reject`
- `dismiss`
- `label`
- `skip`

## Applied Learning

For a tentative match:

- `confirm` marks the local face reference as seen and reinforces the related
  `person` memory entity.
- `reject` records a contradiction against the related memory when one exists.
- `dismiss` and `skip` record the response without trusting new identity memory.

For a familiar unknown cluster:

- `label` promotes the unknown cluster into local face references and syncs the
  label into the generic `person` memory domain.
- `dismiss`, `reject`, and `skip` leave the cluster unpromoted.

## Passive Learning

Passive learning stores redacted `LearningSignal` records under:

```text
STORAGE_DIR/learning-signals/{user_id}/signals.json
```

Signals can come from memory runs, unknown clusters, corrections,
active-learning answers, lifecycle events, and domain review. They store
metadata only: no raw images, embeddings, upload paths, or provider secrets.

Balanced-auto reinforcement can raise confidence for an existing memory after
repeated high-confidence signals. It does not silently create trusted person
identities.

## Review Inbox

The `/learning-review` UI groups:

- highest-priority questions;
- contradictions;
- candidate memories;
- low-health memories;
- replay suggestions;
- recent passive signals.

Question priority is scored from uncertainty, repeated evidence, lifecycle
state, contradiction risk, domain, age, and expected learning value.

## Privacy

Active-learning questions and passive signals store metadata and user responses.
They do not need raw images or embeddings in the queue payload. Exports include
question and signal history so users can inspect what the system asked, what it
noticed, and how they answered.

## Product Direction

The next polish layer should add richer inline editing for domain attributes and
merge/split controls directly inside the Review Inbox.
