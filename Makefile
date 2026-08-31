.PHONY: up down run test db

up:
	docker compose up -d

down:
	docker compose down

run: up
	./start.sh

db:
	python -m voice_postgres.console

env:
	@echo "From zsh:  source ./env.sh"

test:
	python -m pytest -q

pdf:
	python scripts/make_db_guide.py
