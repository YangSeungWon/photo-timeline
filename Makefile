.PHONY: dev build test clean install

# Development commands
dev:
	docker-compose up --build

dev-backend:
	cd backend && uvicorn main:app --reload --host 0.0.0.0 --port 8000

dev-frontend:
	cd frontend && npm run dev

# Build commands
build:
	docker-compose build

# Test commands
test:
	pytest tests/ -v

test-watch:
	pytest tests/ -v --watch

# Installation commands
install:
	pip install -e ./libs/photo_core
	pip install -r backend/requirements.txt
	cd frontend && npm install

# Cleanup commands
clean:
	docker-compose down -v
	docker system prune -f

# Database commands
db-up:
	docker-compose up postgres -d

db-down:
	docker-compose stop postgres

# Utility commands
logs:
	docker-compose logs -f

logs-backend:
	docker-compose logs -f backend

logs-frontend:
	docker-compose logs -f frontend 