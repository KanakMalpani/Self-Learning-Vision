# Demo Walkthrough

Use this script for a public demo, README video, or release walkthrough. Keep all images consented, synthetic, or created only for the demo.

## Demo Goal

Show that Self-Learning Vision is not just face recognition. It is a local memory system that learns cautiously, explains trust, asks useful questions, and gives users control.

## 10 Minute Flow

### 1. Local-First Promise

Show `.env.example` or the settings page:

- Local/free path is the default.
- Hosted providers are optional.
- Paid providers are replaceable.
- Raw uploads, embeddings, and local databases are not intended for Git.

### 2. First Memory

Upload a safe demo image, run a memory check, select a face, and enroll it.

What to say:

> The system creates a trusted person memory only after user review.

### 3. Recognition And Uncertainty

Upload another safe image. Show a confident match, tentative match, or unknown candidate.

What to say:

> Confidence is visible. Uncertain results become questions instead of silent truth.

### 4. Review Inbox

Open `/learning-review`.

Show:

- Highest-priority questions.
- Contradictions.
- Candidate memories ready for review.
- Low-health memories.
- Replay suggestions.
- Learning policy preset controls.

What to say:

> The app ranks what matters most, so the user is not buried under every possible question.

### 5. Memory Detail

Open a memory detail page.

Show:

- Evidence bundles.
- Health score.
- Timeline.
- Confidence ledger.
- Related conflicts.
- Correction and replay actions.

What to say:

> A memory should be explainable. The user can see why it exists and how it changed.

### 6. Correction And Replay

Rename a memory, reject a wrong match, or mark a conflict as needing review. Then show replay suggestions.

What to say:

> One correction can clean up related questions and signals without storing raw images.

### 7. Data Controls

Show export, vault export, import, and purge.

What to say:

> The user owns the local memory and can remove it.

## Screenshot Checklist

Use these screenshots in the GitHub README or release page after capturing them from a clean demo environment:

- Home upload and memory run screen.
- First enrollment flow.
- Review Inbox with sample questions and conflicts.
- Memory detail with evidence, health, and timeline.
- Learning policy controls.
- Evaluation dashboard.
- Data export and purge controls.
- Provider marketplace or provider selection page.

Do not commit screenshots that show real private people, real local paths, credentials, production data, or private uploads.

## Release Video Shape

Recommended structure:

- 15 seconds: what the app is.
- 45 seconds: first memory.
- 60 seconds: recognition, uncertainty, and review.
- 60 seconds: evidence, health, and correction.
- 30 seconds: provider choice and data controls.
- 15 seconds: where contributors can start.

