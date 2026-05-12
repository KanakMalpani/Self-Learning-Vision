# Contributing

Contributions should keep Self-Learning Vision local-first, provider-neutral, and consent-forward.

## Principles

- Prefer local/free functionality by default.
- Keep paid or hosted providers optional.
- Do not add public identity databases.
- Do not commit real uploads, embeddings, logs, or private data.
- Add tests for matching, clustering, provider behavior, or privacy-sensitive changes.
- Keep UI language clear about confidence and uncertainty.

## Development

```bash
make install
make test-api
make test-web
```

Frontend tests require `npm install` in `apps/web`.

## Provider Contributions

New providers should include:

- A short provider card in `docs/provider-guide.md`.
- Required environment variables.
- Whether images leave the local machine.
- Expected embedding dimensions.
- A fallback behavior when the provider is unavailable.

## Verification

Before opening a pull request:

```bash
make verify
```

For frontend changes, also run:

```bash
make build-web
```

## Pull Request Expectations

- Keep changes modular and easy to review.
- Explain how the change affects memory quality, privacy, provider behavior, or user control.
- Include tests for learning policy, lifecycle, replay, provider, or UI behavior when those areas change.
- Update docs when user-facing behavior changes.
- Use public-safe screenshots only.
