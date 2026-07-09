ARG BASE_IMAGE=pytorch/pytorch:2.5.1-cuda12.4-cudnn9-runtime
FROM ${BASE_IMAGE}

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /workspace

COPY --from=ghcr.io/astral-sh/uv:0.11.26 /uv /uvx /usr/local/bin/

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        git \
        unzip \
        zip \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock .python-version ./
# --python 3.12 明示: ピン無しだと uv が最新(3.14等)を選び、pygame 等の
# wheel が無い Python でソースビルドに落ちて失敗する（2026-07-09 サーバーで実測）
RUN uv venv --python 3.12 --system-site-packages .venv \
    && uv sync --frozen --no-install-project

ENV PATH="/workspace/.venv/bin:${PATH}"

CMD ["bash"]
