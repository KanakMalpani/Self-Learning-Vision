# Evaluation Guide

Self-learning vision systems need evaluation that is stricter than a normal demo because false positives can create bad memory.

## Test Layers

- **Detection:** Face boxes are present, bounded, and stable enough for selection.
- **Quality:** Blurry, tiny, occluded, or extreme-pose faces are rejected or flagged.
- **Embedding:** Providers return normalized numeric vectors or fail cleanly.
- **Matching:** Accepted, tentative, and unknown states follow configured thresholds.
- **Learning:** Unknown samples cluster only when similarity is high enough.
- **Promotion:** Unknown clusters become named identities only after user action.
- **Deletion:** Uploads and memory runs can be removed without orphaned records.

## Recommended Metrics

- Accepted-match precision.
- Tentative-match review rate.
- Unknown false-cluster rate.
- Unknown missed-cluster rate.
- Low-quality rejection rate.
- Provider fallback rate.
- Average recognition latency.
- Local storage growth per memory run.

## Implemented Evaluation Loop

The app exposes a local, redacted evaluation loop:

```http
GET /api/v1/evaluation/summary
GET /api/v1/evaluation/metrics
GET /api/v1/evaluation/dataset
GET /api/v1/evaluation/provider-scorecard
GET /api/v1/evaluation/benchmark-pack
GET /api/v1/evaluation/benchmark-runs
POST /api/v1/evaluation/benchmark-runs
```

The metrics endpoint reports recognition decisions, uncertainty rate, correction
rate, active-learning completion rate, false-match signals, missed-match signals,
passive signal count, auto-reinforcement count, review inbox backlog,
contradiction rate, memory health distribution, replay count, and estimated
precision/recall. Precision and recall are estimates because the
app does not assume a global ground-truth dataset; it uses user confirmations,
labels, rejections, memory corrections, and lifecycle contradictions.

The dataset endpoint is designed for safe local benchmarking. It includes
active-learning answers, correction records, and memory entity state, but excludes
raw images, upload paths, biometric embeddings, and provider secrets.

The provider scorecard endpoint lets teams compare the free local path with paid
or hosted providers without changing the public contract. Run the same
consent-safe fixture set before and after switching providers, then compare:

- estimated precision;
- estimated recall;
- uncertainty rate;
- correction rate;
- active-learning completion rate;
- whether images leave the device.

The benchmark pack endpoint defines consent-safe, metadata-only cases for repeatable
offline comparisons. It does not ship raw images, biometric embeddings, or real
personal datasets.

Benchmark run history stores redacted metric snapshots. Use it to compare a local
baseline against later provider or threshold changes.

## Fixture Policy

Use consent-safe fixtures only:

- Synthetic images.
- Generated placeholders.
- User-owned test images.
- Redacted metadata.
- No private embeddings, production uploads, or real personal datasets in Git.

## Release Checklist

Before publishing a release:

- Run backend tests.
- Run frontend tests after installing web dependencies.
- Run artifact and secret scans.
- Verify Docker starts cleanly.
- Confirm `.env.example` contains placeholders only.
- Confirm no generated uploads, embeddings, logs, or databases are committed.
- Confirm docs describe both free/local and paid/provider paths.
