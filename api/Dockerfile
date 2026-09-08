FROM python:3.11-slim

WORKDIR /app

# 系统依赖:ffprobe + ImageMagick(ARW 缩略图备用)+ curl
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    imagemagick \
    libvips-tools \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 代码
COPY . /app

EXPOSE 8000

# 默认启动 api(可被 worker 覆盖 command)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]