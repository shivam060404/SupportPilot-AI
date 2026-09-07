.PHONY: install api frontend test migrate up down

install:
	python -m pip install -r requirements.txt

api:
	uvicorn backend.app.api.main:app --reload --port 8000

frontend:
	cd frontend && npm run dev

test:
	pytest

migrate:
	alembic upgrade head

up:
	docker compose up --build

down:
	docker compose down
