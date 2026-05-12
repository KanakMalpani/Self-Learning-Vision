# First Five Minutes

This guide is the shortest successful path through Self-Learning Vision. It uses the free local configuration and avoids hosted providers.

## 1. Start The App

```bash
cp .env.example .env
docker compose up --build
```

Open:

- Web: http://localhost:3000
- API: http://localhost:8000

The default `.env.example` keeps hosted providers disabled.

## 2. Use Safe Demo Data

Use only images you own, images you have permission to process, or synthetic/demo images. Do not use photos of people who did not agree to be part of the test.

For a public demo, prefer staged images, synthetic fixtures, or your own consenting test set.

## 3. Create The First Memory

1. Upload an image.
2. Run a memory check.
3. Select a detected face.
4. Enroll it with a clear label, short note, and optional tags.
5. Open the memory detail page and confirm the evidence, confidence, and timeline are understandable.

The first memory is intentionally review-gated. The app should not silently create a trusted person identity.

## 4. See Learning In Action

Upload a second image that contains the same person or a repeated unknown. The system should show one of these outcomes:

- A confident local match for an existing memory.
- A tentative match that asks for review.
- An unknown candidate that becomes more useful after repeated sightings.

Open `/learning-review` to inspect the Review Inbox. This is where high-value questions, contradictions, low-health memories, and replay suggestions are grouped.

## 5. Check Trust And Control

Before calling the run successful, inspect:

- Memory detail: health, evidence bundles, timeline, and related conflicts.
- Learning policy: conservative, balanced, or experimental behavior.
- Data controls: export, encrypted vault export, and purge.
- Evaluation: passive signal counts, review counts, contradiction rate, and memory health distribution.

## Success Criteria

A first-time user should understand these five things without reading the code:

- What the system remembered.
- Why it trusts or does not trust that memory.
- What still needs review.
- How to correct or undo learning.
- How to export or remove local memory.

