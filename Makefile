.PHONY: up down run test db

up:
	docker compose up -d

down:
	docker compose down

run: up
	./start.sh

db:
	python -m voice_postgres.console

test:
	python -m pytest -q
