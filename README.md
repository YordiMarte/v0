# v0

An AI assistant that knows your company. Connect your documents, ask in plain
language, and get answers with the source cited.

**Status:** in development.

## Run locally

    Copy-Item .env.example .env
    docker compose up --build

API health check: http://localhost:8000/api/health/

## Architecture decisions

See [docs/decisions](docs/decisions).