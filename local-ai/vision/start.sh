#!/usr/bin/env bash
set -euo pipefail
vision_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# Official ggml-org CUDA image; override with a verified digest when upgrading.
vision_image="${VISION_IMAGE:-ghcr.io/ggml-org/llama.cpp@sha256:cabbb32aaee5abc5d8af3ebec89781a722ad2e83a37f409980008579a31fe767}"
test -f "$vision_dir/models/Qwen3VL-2B-Instruct-Q4_K_M.gguf"
test -f "$vision_dir/models/mmproj-Qwen3VL-2B-Instruct-Q8_0.gguf"
exec docker run -d --name varta-local-vision --gpus all \
  --memory 4g --memory-swap 4g --cpus 4 \
  --security-opt no-new-privileges --cap-drop ALL \
  --read-only --tmpfs /tmp:rw,noexec,nosuid,size=128m \
  --log-opt max-size=10m --log-opt max-file=2 \
  -p 127.0.0.1:8081:8080 \
  -v "$vision_dir/models:/models:ro" \
  "$vision_image" \
  --model /models/Qwen3VL-2B-Instruct-Q4_K_M.gguf \
  --mmproj /models/mmproj-Qwen3VL-2B-Instruct-Q8_0.gguf \
  --alias qwen3-vl-2b-local --host 0.0.0.0 --port 8080 \
  --n-gpu-layers 99 --ctx-size 4096 --parallel 1 \
  --batch-size 128 --ubatch-size 128 --image-max-tokens 1024 \
  --threads 4 --threads-batch 4 --n-predict 512 --no-webui --jinja
