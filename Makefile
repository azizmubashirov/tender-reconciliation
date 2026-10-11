PNPM := $(shell command -v pnpm 2>/dev/null || echo "npx --yes pnpm@10.34.6")

.PHONY: help env install lint fmt test up up-av down logs ps clean api-dev web-dev

help: ## Buyruqlar ro'yxati
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "}; {printf "  %-10s %s\n", $$1, $$2}'

env: .env ## .env faylini .env.example dan yaratish
.env:
	cp .env.example .env

install: .env ## Lokal bog'liqliklar + pre-commit hook
	cd backend && uv sync
	cd frontend && $(PNPM) install
	uvx pre-commit install

lint: ## ruff, mypy, eslint, tsc
	cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy
	cd frontend && $(PNPM) lint && $(PNPM) typecheck

fmt: ## Kodni formatlash
	cd backend && uv run ruff check --fix . && uv run ruff format .

test: ## Backend testlari
	cd backend && uv run pytest

up: .env ## Docker muhitini ko'tarish (healthy bo'lguncha kutadi)
	docker compose up -d --build --wait

up-av: .env ## + ClamAV antivirus
	docker compose --profile av up -d --build --wait

down: ## To'xtatish
	docker compose --profile av down

logs: ## Loglar
	docker compose logs -f --tail=100

ps: ## Servislar holati
	docker compose ps

clean: ## To'xtatish va barcha ma'lumotlarni (volume) o'chirish
	docker compose --profile av down -v

api-dev: ## API ni docker'siz ishga tushirish (postgres va redis docker'da bo'lishi kerak)
	cd backend && uv run uvicorn app.main:app --reload

web-dev: ## Vite dev server (hot reload), /api → localhost:8000
	cd frontend && $(PNPM) dev
