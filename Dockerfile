# =============================================================================
# Stage 1: Builder — install dependencies into a user-local prefix
# =============================================================================
FROM python:3.12-slim AS builder

# Prevents Python from writing .pyc files and buffers stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies into /root/.local so we can copy only the
# installed packages to the final image (keeps the image lean)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir --user -r requirements.txt


# =============================================================================
# Stage 2: Final runtime image — minimal footprint
# =============================================================================
FROM python:3.12-slim AS final

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    # Add user-local bin to PATH so uvicorn / alembic are found
    PATH=/root/.local/bin:$PATH

WORKDIR /app

# Copy installed packages from the builder stage
COPY --from=builder /root/.local /root/.local

# Copy application source code
COPY . .

EXPOSE 8000

# Default entrypoint — apply pending migrations then launch the ASGI server.
# In docker-compose the command is overridden to the same pattern, but this
# provides a safe standalone default for direct `docker run` usage.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
