all: up

up:
	docker compose up -d --build

down:
	docker compose down

exec:
	docker exec -it $(name) /bin/bash

logs:
	docker compose logs $(name) -f

restart:
	docker compose restart

stop:
	docker compose stop

clean:
	docker compose down --rmi all --volumes --remove-orphans

prune:
	docker system prune -a --volumes -y

.PHONY: all up down logs restart stop clean