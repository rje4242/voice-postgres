.PHONY: up down run test fmt

up:
	docker compose up -d

down:
	docker compose down

run: up
	./start.sh

test:
	python -m pytest -q
