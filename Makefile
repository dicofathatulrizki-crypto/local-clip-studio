# Local Clip Studio — Makefile
# Development automation for backend and frontend.

.PHONY: help setup dev backend frontend test lint typecheck clean docker-build docker-up

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

setup: ## Run the one-click setup script
	bash scripts/setup.sh

dev: ## Start both backend and frontend dev servers
	bash scripts/dev.sh

backend: ## Start only the backend server
	@echo "Starting backend on http://127.0.0.1:8765"
	python -m backend.main --reload

frontend: ## Start only the frontend dev server
	@echo "Starting frontend on http://localhost:5173"
	bun run dev

test: ## Run all tests
	python -m pytest tests/ -v --tb=short

test-cov: ## Run tests with coverage report
	python -m pytest tests/ -v --tb=short --cov=backend --cov-report=term-missing

test-unit: ## Run unit tests only
	python -m pytest tests/unit/ -v --tb=short

test-integration: ## Run integration tests only
	python -m pytest tests/integration/ -v --tb=short

lint: ## Run the linter
	python -m ruff check backend/ tests/
	python -m ruff format --check backend/ tests/

format: ## Format code with ruff
	python -m ruff format backend/ tests/
	python -m ruff check --fix backend/ tests/

typecheck: ## Run type checking with mypy
	python -m mypy backend/ --ignore-missing-imports

clean: ## Clean build artifacts and caches
	rm -rf build/ dist/ *.egg-info .pytest_cache .mypy_cache .ruff_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf .coverage htmlcov/
	@echo "Cleaned build artifacts"

docker-build: ## Build Docker image
	docker compose -f docker/docker-compose.yml build

docker-up: ## Start with Docker Compose
	docker compose -f docker/docker-compose.yml up -d

docker-down: ## Stop Docker Compose
	docker compose -f docker/docker-compose.yml down

download-models: ## Download default AI models
	bash scripts/download_models.sh

db-migrate: ## Run database migrations
	cd backend && alembic upgrade head

db-rollback: ## Rollback last migration
	cd backend && alembic downgrade -1

db-revision: ## Create a new migration revision
	cd backend && alembic revision --autogenerate -m "$(name)"
