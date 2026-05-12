# Evaluation Dashboard

The repo includes an in-app Evaluation page at `/evaluation`. It turns the
self-learning loop into measurable local telemetry without exporting sensitive
artifacts.

## Dashboard Sections

- **Recognition:** matched, tentative, unknown, and average confidence.
- **Learning Loop:** confirmations, rejections, labels, dismissals, pending questions, and completion rate.
- **Corrections:** correction rate, false-match signals, missed-match signals, and correction mix.
- **Provider Scorecard:** selected providers, cost model, privacy behavior, and provider-aware benchmark guidance.
- **Redacted Dataset:** active-learning examples, correction examples, and memory entity state.

## API Shape

Implemented endpoints:

```http
GET /api/v1/evaluation/summary
GET /api/v1/evaluation/metrics
GET /api/v1/evaluation/dataset
GET /api/v1/evaluation/provider-scorecard
```

Metrics response:

```json
{
  "memory_runs": 12,
  "recognition_decisions": {
    "matched": 7,
    "tentative": 3,
    "unknown": 2
  },
  "uncertainty_rate": 0.416667,
  "corrections": 3,
  "correction_rate": 0.25,
  "estimated_precision": 0.8,
  "estimated_recall": 0.75
}
```

## Why It Matters

Self-learning systems need visibility into mistakes. The dashboard should help users see whether the model is learning carefully or becoming overconfident.

## Public Sharing Rule

Share metrics and provider scorecards freely. Do not share raw uploads,
embeddings, private notes, provider secrets, or production user datasets.
