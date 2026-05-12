# Demo Fixtures

The public repo should never include private uploads, embeddings, or real personal datasets.

Recommended demo fixture sources:

- Generated face-like illustrations.
- Synthetic geometric fixtures for detection and UI flows.
- User-owned test images kept outside Git.
- Consent-safe images specifically created for demos.

## Demo Flow

1. Upload image A with one face.
2. Confirm it is unknown.
3. Enroll the selected face as `Demo Person`.
4. Upload image B of the same person.
5. Confirm the app returns `matched`.
6. Upload two unknown images of another person.
7. Confirm the app marks the repeated unknown as familiar and suggests enrollment.

## Generate Local Demo Images

The repo includes a small generator that writes synthetic placeholder images outside Git:

```bash
cd apps/api
python scripts/create_demo_fixtures.py
```

Generated files go to `apps/api/data/demo-fixtures`.

## Fixture Rules

- Do not commit private photos.
- Do not commit generated embeddings.
- Do not commit upload directories.
- Do not include names of real people unless they explicitly consented.
- Prefer synthetic or generated placeholders for automated tests.
