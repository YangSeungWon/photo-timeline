# Photo Timeline Development Makefile

.PHONY: help dev dev-backend dev-frontend dev-worker build test clean install

help: ## Show this help message
	@echo "Photo Timeline Development Commands:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# Development
dev: ## Start full development environment (backend + frontend + worker)
	@echo "🚀 Starting full development environment..."
	docker compose up -d postgres redis
	@echo "⏳ Waiting for services to be ready..."
	sleep 3
	@echo "🔧 Starting backend, worker, and frontend..."
	@make -j3 dev-backend dev-worker dev-frontend

dev-backend: ## Start backend development server
	@echo "🐍 Starting FastAPI backend..."
	cd backend && AUTO_CREATE_TABLES=true uvicorn main:app --reload --host 0.0.0.0 --port 8000

dev-frontend: ## Start frontend development server
	@echo "⚛️  Starting Next.js frontend..."
	cd frontend && npm run dev

dev-worker: ## Start background worker
	@echo "⚙️  Starting RQ worker..."
	cd backend && python worker.py

# Infrastructure
services: ## Start infrastructure services (PostgreSQL + Redis)
	@echo "🐘 Starting PostgreSQL and Redis..."
	docker compose up -d postgres redis

services-stop: ## Stop infrastructure services
	@echo "🛑 Stopping services..."
	docker compose down

# Installation
install: ## Install all dependencies
	@echo "📦 Installing backend dependencies..."
	cd backend && pip install -r requirements.txt
	@echo "📦 Installing frontend dependencies..."
	cd frontend && npm install

# Database
db-migrate: ## Run database migrations
	@echo "🗄️  Running database migrations..."
	cd backend && alembic upgrade head

db-reset: ## Reset database (WARNING: destroys all data)
	@echo "⚠️  Resetting database..."
	docker compose down postgres
	docker volume rm photo-timeline_postgres_data || true
	docker compose up -d postgres
	sleep 5
	@make db-migrate

# Testing
test: ## Run all tests
	@echo "🧪 Running backend tests..."
	cd backend && python -m pytest
	@echo "🧪 Running frontend tests..."
	cd frontend && npm test

test-backend: ## Run backend tests only
	@echo "🧪 Running backend tests..."
	cd backend && python -m pytest

# Build
build: ## Build production images
	@echo "🏗️  Building production images..."
	docker compose build

# Cleanup
clean: ## Clean up development environment
	@echo "🧹 Cleaning up..."
	docker compose down
	docker system prune -f
	cd frontend && rm -rf .next node_modules/.cache

# Logs
logs: ## Show logs from all services
	docker compose logs -f

logs-backend: ## Show backend logs
	docker compose logs -f backend

logs-worker: ## Show worker logs
	docker compose logs -f worker

logs-db: ## Show database logs
	docker compose logs -f postgres

# Quick start for new developers
setup: ## Complete setup for new developers
	@echo "🎯 Setting up Photo Timeline for development..."
	@make install
	@make services
	@echo "⏳ Waiting for services..."
	sleep 5
	@make db-migrate
	@echo "✅ Setup complete! Run 'make dev' to start development."

# Production
prod: ## Start production environment
	@echo "🚀 Starting production environment..."
	docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Status
status: ## Show status of all services
	@echo "📊 Service Status:"
	@docker compose ps 