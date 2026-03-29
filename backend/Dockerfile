FROM python:3.10-slim AS rust_builder

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH="/root/.cargo/bin:${PATH}"

WORKDIR /build

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates build-essential pkg-config \
    && rm -rf /var/lib/apt/lists/*

RUN curl https://sh.rustup.rs -sSf | sh -s -- -y --profile minimal --default-toolchain stable

COPY backend/rust_ext /build/rust_ext
RUN pip install --no-cache-dir maturin \
    && maturin build --release -i python --manifest-path /build/rust_ext/Cargo.toml

FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system deps (minimal)
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Install Rust extension wheel built in previous stage
COPY --from=rust_builder /build/rust_ext/target/wheels /tmp/rust_wheels
RUN pip install --no-cache-dir /tmp/rust_wheels/rl428_minimax_rust-*.whl \
    && rm -rf /tmp/rust_wheels

# Copy application code
COPY backend/app /app/app

EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
