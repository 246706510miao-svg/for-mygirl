# 这个镜像用于运行 third API、worker 和 Alembic migration。
FROM python:3.11-slim

# 这一段设置 Python 容器运行时行为，减少缓存文件并让日志直接输出。
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app

WORKDIR /app

# 这一层先安装依赖，代码变动时可以复用 Docker build 缓存。
COPY third/requirements.txt /tmp/third-requirements.txt
RUN pip install --upgrade pip \
    && pip install -r /tmp/third-requirements.txt

# 这一层复制 third 模块源码，API、worker 和 migration 共用同一个镜像。
COPY third ./third
