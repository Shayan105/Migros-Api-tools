# Migros Api tools

![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![Docker](https://img.shields.io/badge/docker-ready-2496ED?logo=docker&logoColor=white)

This repo scrapes product data from Migros category pages, stores time-based snapshots in MongoDB, and exposes a FastAPI service to query products by category with optional date and discount filters.

## Try it yourself
Use the publicly available url : https://api.mi-gross.ch/products/viandes_poissons?page=1&limit=20

## Why this project

- Scrapes multiple Migros categories automatically
- Stores historical snapshots (`scraped_at`) for time-based analysis
- Provides category-level JSON exports for quick offline access
- Includes a query API with:
  - category listing
  - pagination
  - date and date-range filtering
  - reduced-price filtering
- Supports local execution and Docker-based scraping

## Project structure

- `scraper.py` – main scraper for all configured categories and MongoDB persistence
- `api_server.py` – FastAPI app for querying scraped data from MongoDB
- `docker-compose.yml` / `Dockerfile` – containerized scraper runtime
- `requirements.txt` – Python dependencies
- `*.json` – example/exported category snapshots

## How to get started

### Prerequisites

- Python 3.11+
- Google Chrome (for Selenium local runs)
- MongoDB running and reachable at:
  - `mongodb://127.0.0.1:27017/` (default local)
  - or `MONGO_URI` environment variable for custom endpoints

### 1) Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2) Run the scraper

```bash
python scraper.py
```

This will:
- scrape all categories defined in `scraper.py`
- write/update category JSON files in the repository root
- insert product snapshots into MongoDB database `migros_db`

### 3) Run the API server

```bash
python api_server.py
```

By default, the API runs on port `8000`.

### 4) Query the API

List categories:

```bash
curl "http://localhost:8000/categories"
```

Get latest distinct products for a category:

```bash
curl "http://localhost:8000/products/fruits_legumes?page=1&limit=20"
```

Filter by specific date:

```bash
curl "http://localhost:8000/products/fruits_legumes?date=2026-05-20"
```

Filter by date range and reduced products:

```bash
curl "http://localhost:8000/products/fruits_legumes?start_date=2026-05-01&end_date=2026-05-20&is_reduced=true"
```

## Docker usage (scraper)

Build and run with Docker Compose:

```bash
docker compose up --build
```

The compose setup passes `MONGO_URI=mongodb://host.docker.internal:27017/` so the container can write to a MongoDB instance running on the host.

## Where to get help

- Open an issue: `https://github.com/Shayan105/MigrosScrapper/issues`
- Inspect API docs (when server is running):
  - Swagger UI: `http://localhost:8000/docs`
  - ReDoc: `http://localhost:8000/redoc`

## Who maintains and contributes

- Maintainer: repository owner (`Shayan105`)
- Contributions are welcome via pull requests.

Suggested contribution flow:
1. Fork the repository
2. Create a feature branch
3. Make focused changes
4. Open a pull request with a clear description

If a dedicated contribution guide is added later, reference it from this README (for example, `CONTRIBUTING.md`).
