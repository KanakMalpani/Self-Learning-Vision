# Memory Domains

Self-Learning Vision is moving from a face-only memory app toward a domain-expandable
visual memory system. Face identity is the first built-in domain, but the same memory
model can represent objects, places, scenes, events, or user-defined concepts.

## Core Model

Every remembered concept is a `MemoryEntity`:

```text
MemoryEntity
- entity_id
- domain_type
- label
- attributes
- user_schema
- aliases
- tags
- notes
- confidence
- lifecycle_state
- observations
- lifecycle_events
- source_reference_ids
```

Built-in domain types:

- `person`
- `object`
- `place`
- `scene`
- `event`
- `document`
- `product`
- `inventory`

Custom domain types are also supported. A user can define `tool_device`,
`product_sku`, `plant_species`, `safety_hazard`, or any other local memory domain.

## Domain Templates

The backend includes a template catalog for common visual memory domains. Templates
define a domain type, recommended fields, default tags, starting confidence, and
prompts that providers or UIs can use when asking for user feedback.

Implemented templates:

- `person`: user-confirmed identity or local relationship memory.
- `object`: recurring physical objects, tools, devices, and visual items.
- `place`: rooms, venues, routes, and recognizable environments.
- `scene`: visual context, state, or setup.
- `event`: time-bound happenings captured by visual evidence.
- `document`: receipts, forms, labels, pages, signs, and OCR targets.
- `product`: SKUs, packages, parts, and branded items.
- `inventory`: assets, stock, tools, and supplies.

Create an entity from a template:

```http
POST /api/v1/memory-domain-templates/product/entities
```

```json
{
  "label": "Camera Lens",
  "attributes": {
    "brand": "DemoOptics",
    "model_or_sku": "DX-50"
  },
  "tags": ["photography"],
  "confidence": 0.91,
  "lifecycle_state": "confirmed"
}
```

## User-Changeable Schemas

Each entity can carry a `user_schema` dictionary. This lets users describe what fields
matter for their domain without changing backend code.

Example:

```json
{
  "domain_type": "tool_device",
  "label": "Thermal Camera",
  "attributes": {
    "serial_number": "demo-123",
    "room": "Lab"
  },
  "user_schema": {
    "fields": {
      "serial_number": "string",
      "room": "string"
    }
  },
  "tags": ["hardware", "vision"],
  "confidence": 0.82,
  "lifecycle_state": "confirmed"
}
```

## Face Identity Bridge

Current face enrollment remains supported. When a person is enrolled through the face
reference flow, the backend also creates or updates a generic `person` entity.

That means existing face recognition becomes one domain-specific provider feeding the
generic memory layer:

```text
Face reference -> person MemoryEntity -> observations -> lifecycle/evaluation later
```

This keeps the ready-to-use face workflow intact while making room for object,
place, scene, event, and custom-domain providers.

## API

- `GET /api/v1/memory-domains`
- `GET /api/v1/memory-domain-templates`
- `GET /api/v1/memory-domain-templates/{template_id}`
- `POST /api/v1/memory-domain-templates/{template_id}/entities`
- `GET /api/v1/memory-entities`
- `GET /api/v1/memory-entities?domain_type=person`
- `POST /api/v1/memory-entities`
- `GET /api/v1/memory-entities/{entity_id}`

## Privacy

`MemoryEntity` records store metadata, confidence, observations, and user-defined
attributes. They do not need to expose raw images or biometric embeddings. The default
data export includes generic memory entities but keeps biometric vectors out of the
export payload.

## Next Phases

This model is the foundation for:

- active learning questions,
- correction UX,
- memory lifecycle states, confidence history, and contradiction handling,
- provider marketplace domains,
- evaluation metrics,
- contextual recall across people, places, objects, scenes, and events.
