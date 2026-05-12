# First Run

Self-Learning Vision supports two local startup paths.

## Docker Path

Use this when you want the full app with Postgres:

```bash
cp .env.example .env
docker compose up --build
```

Open:

- Web: http://localhost:3000
- API: http://localhost:8000

## SQLite Developer Path

Use this when you want the lowest-friction local backend:

```bash
cd apps/api
DATABASE_URL=sqlite:///./data/self_learning_vision.db uvicorn app.main:app --reload --port 8000
```

Then run the web app:

```bash
cd apps/web
npm install
npm run dev
```

## Provider Choice

Default mode is local/free:

```env
EMBEDDING_PROVIDER=auto
PAID_PROVIDER_ENABLED=false
PRIVACY_LOCAL_ONLY_MODE=true
PRIVACY_ALLOW_HOSTED_PROVIDERS=false
```

Use paid or hosted providers only when intentionally configured:

```env
EMBEDDING_PROVIDER=paid
PAID_PROVIDER_ENABLED=true
PAID_PROVIDER_TOKEN=your_token_here
PRIVACY_LOCAL_ONLY_MODE=false
PRIVACY_ALLOW_HOSTED_PROVIDERS=true
```

Never commit `.env`.
