# Memory Quality Toolkit

This toolkit turns the core idea into usable project infrastructure.

## Template Creator

Users can create structured memories from domain templates instead of writing JSON.
The web app exposes this at `/memories`.

Examples:

- product: brand, SKU, category, condition;
- document: document type, source, visible text summary;
- inventory: asset ID, quantity, storage location, reorder state;
- place: location type, landmarks, access notes.

## Memory Search

Users can search local memory across labels, aliases, tags, notes, domain type,
and attributes.

Endpoint:

```http
GET /api/v1/memory-entities/search?q=camera&domain_type=product
```

Search is local metadata search. It does not inspect raw images or embeddings.

## Memory Detail Page

Each memory has a detail view at `/memories/{id}`. It combines:

- attributes;
- observations count;
- lifecycle events count;
- active-learning questions;
- corrections;
- confidence ledger.
- evidence bundles;
- memory health;
- related conflicts;
- learning replay suggestions.
- learning timeline;
- editing and correction controls.

Endpoint:

```http
GET /api/v1/memory-entities/{entity_id}/detail
PATCH /api/v1/memory-entities/{entity_id}
POST /api/v1/memory-entities/{entity_id}/learning/replay
```

## Provider Conformance

Every provider should prove basic behavior before users trust it:

- capabilities are declared;
- privacy behavior is documented;
- hosted image transfer is explicit;
- cost model is documented;
- setup instructions exist;
- executable plugins include an entrypoint.

Endpoint:

```http
GET /api/v1/provider-conformance
```

## Offline Benchmark Pack

The benchmark pack is metadata-only. It defines consent-safe test cases without
shipping raw photos, embeddings, personal datasets, logs, or databases.

Endpoint:

```http
GET /api/v1/evaluation/benchmark-pack
```

Benchmark history stores local metric snapshots so users can compare before and
after changing a provider, threshold, or workflow.

Endpoints:

```http
GET /api/v1/evaluation/benchmark-runs
POST /api/v1/evaluation/benchmark-runs
```

Example case:

```json
{
  "case_id": "product-sku-memory",
  "domain_type": "product",
  "task": "template_memory_creation",
  "description": "A product memory should track brand, SKU, category, and condition."
}
```

## Confidence Ledger

Each memory can explain why it is trusted or uncertain.

Endpoint:

```http
GET /api/v1/memory-entities/{entity_id}/confidence-ledger
```

Example entries:

- created from template: `+60%`
- user confirmed: `+15%`
- stale memory decay: `-5%`
- marked as wrong: `-10%`

## Domain-Specific Active Learning

The app asks different questions depending on the memory domain.

Examples:

- inventory: “What quantity, location, or reorder state should be remembered?”
- document: “What visible text should be remembered?”
- product: “What brand, model, SKU, or condition should be remembered?”
- place: “What landmarks identify this place?”

Endpoint:

```http
POST /api/v1/memory-entities/{entity_id}/active-learning/domain-review
```
