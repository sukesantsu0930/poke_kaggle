ARG BASE_IMAGE=pytorch/pytorch:2.5.1-cuda12.4-cudnn9-runtime
FROM ${BASE_IMAGE}

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

WORKDIR /workspace

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        git \
        unzip \
        zip \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements.txt
COPY requirements-gpu.txt requirements-gpu.txt
RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements.txt \
    && if [ -s requirements-gpu.txt ]; then python -m pip install -r requirements-gpu.txt; fi

CMD ["bash"]
