SHELL := /bin/sh

PYTHON ?= python

.PHONY: install install-api install-web fmt-api lint-api test-api test-web typecheck-web build-web build-web-desktop test verify scan-public demo-fixtures dev-api dev-api-sqlite dev-web docker-up docker-down docker-rebuild clean-local

install: install-api install-web

install-api:
	cd apps/api && pip install -r requirements.txt

install-web:
	cd apps/web && npm install

fmt-api:
	cd apps/api && black app tests

lint-api:
	cd apps/api && ruff check app tests

test-api:
	cd apps/api && pytest

test-web:
	cd apps/web && npm test

typecheck-web:
	cd apps/web && npm run typecheck

build-web:
	cd apps/web && npm run build

build-web-desktop:
	cd apps/web && npm run build:desktop

test: test-api test-web

verify: test-api test-web typecheck-web scan-public

demo-fixtures:
	cd apps/api && $(PYTHON) scripts/create_demo_fixtures.py

scan-public:
	rg --files -g "*.jpg" -g "*.jpeg" -g "*.png" -g "*.webp" -g "*.npy" -g "*.csv" -g "*.log" -g "*.env" -g "*.sqlite" -g "*.db" -g "*.pyc" -g "*.tsbuildinfo" || true
	rg -n -i "famo[u]s|web enrichmen[t]|risk scorin[g]|private artifac[t]|secret ke[y]" README.md docs apps docker-compose.yml .env.example || true

dev-api:
	cd apps/api && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

dev-api-sqlite:
	cd apps/api && DATABASE_URL=sqlite:///./data/self_learning_vision.db uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

dev-web:
	cd apps/web && npm run dev

docker-up:
	docker compose up --build

docker-down:
	docker compose down

docker-rebuild:
	docker compose build --no-cache

clean-local:
	rm -rf apps/web/.next apps/web/out apps/web/dist apps/web/tsconfig.tsbuildinfo apps/desktop/src-tauri/target apps/api/build apps/api/dist
	find apps -type d -name "__pycache__" -prune -exec rm -rf {} +
	find apps -type d -name ".pytest_cache" -prune -exec rm -rf {} +
	find apps -type f -name "*.pyc" -delete
