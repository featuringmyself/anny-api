# Anny API

FastAPI backend for Anny (AI visibility / audit workflows). It exposes ChatGPT automation and audit routes (capture, analyze, synthesize, report, and related helpers).

- Interactive docs: `/docs`
- Alternative docs: `/redoc`
- Health check: `/health`

Requires **Python 3.12+**.

## Local development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
fastapi run app/main.py --port 8000
```

Then open http://127.0.0.1:8000/docs

## Docker

The project includes a `Dockerfile` so you can build and run the API as a Linux container image (same approach as [FastAPI in Containers - Docker](https://fastapi.tiangolo.com/deployment/docker/)).

### Dockerfile

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt /app/requirements.txt

RUN pip install --no-cache-dir --upgrade -r /app/requirements.txt

COPY . /app

CMD ["fastapi", "run", "app/main.py", "--port", "80"]
```

What each step does:

1. **Base image** — official `python:3.12-slim` (matches `.python-version`).
2. **`WORKDIR /app`** — install and run the app under `/app`.
3. **Copy `requirements.txt` first** — so Docker can cache the dependency layer when only app code changes.
4. **`pip install --no-cache-dir --upgrade`** — install locked deps without leaving pip’s download cache in the image; upgrade any versions already present in the base image when a newer match exists.
5. **`COPY . /app`** — copy the application source last (changes most often).
6. **`CMD`** — start with `fastapi run` on port **80** inside the container (exec form, so shutdown/lifespan work correctly).

If you run behind a TLS termination proxy (Nginx, Traefik, etc.), use:

```dockerfile
CMD ["fastapi", "run", "app/main.py", "--port", "80", "--proxy-headers"]
```

### Build the image

From the project root (where the `Dockerfile` is):

```bash
docker build -t anny-api .
```

### Run the container

Map host port `8000` to container port `80`:

```bash
docker run -d --name anny-api -p 8000:80 anny-api
```

### Check it

- Health: http://127.0.0.1:8000/health
- Interactive API docs: http://127.0.0.1:8000/docs
- Alternative docs: http://127.0.0.1:8000/redoc
