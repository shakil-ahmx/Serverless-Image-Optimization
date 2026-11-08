#!/bin/bash
set -e

echo "🚀 Building Lambda Layer with Pillow using Docker..."

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$( cd "$SCRIPT_DIR/.." && pwd )"
TERRAFORM_DIR="$PROJECT_DIR/terraform"

# Stop Git Bash (Windows) from rewriting /paths inside docker arguments
export MSYS_NO_PATHCONV=1

if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed."
    exit 1
fi

if ! docker info &> /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker first."
    exit 1
fi

echo "📦 Building layer in Linux container (Python 3.12, linux/amd64)..."

docker run --rm \
  --platform linux/amd64 \
  -v "$TERRAFORM_DIR":/output \
  python:3.12-slim \
  bash -c "
    pip install --quiet Pillow==10.4.0 -t /tmp/python/lib/python3.12/site-packages/ && \
    cd /tmp && \
    python -m zipfile -c pillow_layer.zip python/ && \
    cp pillow_layer.zip /output/
  "

echo "✅ Layer built: $TERRAFORM_DIR/pillow_layer.zip"
