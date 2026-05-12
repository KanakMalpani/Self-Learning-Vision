# Self-Learning Vision Standard

This document defines the standard this project is aiming for: a reference implementation for vision systems that learn from user-confirmed memory instead of hidden scraping, public identity databases, or automatic naming.

## North Star

A self-learning vision system should:

- Detect visual entities with clear confidence and quality signals.
- Ask the user before turning an unknown entity into named memory.
- Improve from repeated encounters without silently inventing identity.
- Work locally by default.
- Allow paid or hosted providers only through explicit configuration.
- Make deletion, export, and provider boundaries obvious.
- Be testable with repeatable fixtures and documented thresholds.
- Make the learning loop measurable with privacy-safe metrics.

## Core Loop

1. Upload or capture an image.
2. Detect faces and score image quality.
3. Select the face or entity to analyze.
4. Compare against user-enrolled local memory.
5. Return one of three states: `matched`, `tentative`, or `unknown`.
6. Store useful unknowns locally.
7. Cluster repeated unknowns.
8. Suggest enrollment only after repeated sightings.
9. Promote unknown clusters only after user confirmation.
10. Track memory provenance, confidence, and caveats.

## Required Product Properties

- **Local-first:** The default path runs without cloud identity services.
- **Provider-neutral:** The backend accepts local, paid, hosted, or internal providers through the same contract.
- **Consent-forward:** Unknowns are never named automatically.
- **Auditable:** Every result explains quality, confidence, and matching reason.
- **Portable:** Data lives in explicit storage paths and can be deleted or exported.
- **Composable:** Detection, embedding, matching, clustering, and UI are separable.

## Reference Vocabulary

- **Memory Run:** One user-triggered recognition attempt against an uploaded image.
- **Memory Report:** The generated explanation for a Memory Run.
- **Identity Reference:** A user-confirmed enrolled person.
- **Unknown Sample:** A high-quality unknown face stored locally.
- **Unknown Cluster:** Repeated unknown samples likely representing the same person.
- **Promotion:** User-confirmed conversion of an unknown cluster into an identity reference.

## Quality Gates

The system should reject or warn on:

- Low detector confidence.
- Low-resolution faces.
- Blurry crops.
- Extreme pose.
- Strong occlusion.
- Similarity below the configured acceptance threshold.
- Tentative matches that should not update seen counts.

## Provider Requirements

Every provider should document:

- Whether images leave the machine.
- Whether embeddings are stored.
- Required environment variables.
- Expected embedding dimensions.
- Known limitations.
- Cost model, if any.
- Recommended thresholds.

## Evaluation Requirements

A release-quality vision memory system should include:

- Unit tests for quality gates, matching, unknown clustering, and promotion.
- Synthetic or consent-safe fixtures.
- False-positive tests near threshold boundaries.
- Regression tests for repeated unknown clustering.
- Provider conformance tests.
- A redacted evaluation dataset built from user feedback and corrections.
- Provider scorecards that compare local, paid, hosted, and internal paths.
- Estimated precision, estimated recall, uncertainty rate, and correction rate.
- Privacy scans for images, embeddings, databases, logs, and API keys.

## Non-Goals

This project should not become:

- A public identity search engine.
- A surveillance system.
- A public-figure recognition database.
- A credit, employment, housing, law-enforcement, or access-control decision system.
- A hidden data collection pipeline.
