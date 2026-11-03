# Image Python officielle legere
FROM python:3.11-slim

# Repertoire de travail
WORKDIR /app

# Installer uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copier les fichiers de configuration
COPY pyproject.toml uv.lock* ./

# Installation des dependances avec uv
RUN uv sync --frozen --no-dev

# Copie du code source et configuration
COPY main.py settings.toml ./

# Exposition du port 8080 (standard Cloud Run)
EXPOSE 8080

# Commande de demarrage avec uv
CMD ["uv", "run", "--no-dev", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]