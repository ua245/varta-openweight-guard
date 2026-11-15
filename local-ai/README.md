# GPT-OSS 20B local server (host-compatible)

## Two launch paths

| Path | When to use |
|---|---|
| **CUDA / x86_64** (`gpt-oss-server`) | Ubuntu + NVIDIA (this hackathon GPU box). **Default here.** |
| ARM Vulkan + nerdctl (snapshot on `main`) | Apple M-series Lima guest only — not portable |

## Provenance (unchanged from repo)

- Source: [ggml-org/gpt-oss-20b-GGUF](https://huggingface.co/ggml-org/gpt-oss-20b-GGUF)
- Revision: `41e8a94d15d62070b36cf4553a0250717ecf46b8`
- File: `gpt-oss-20b-MXFP4.gguf` (12 109 566 624 bytes)
- SHA-256: `27cd6c432c7672cb812a92f611cf3ba7bbc35928262bb1e1253ff4ee6ae35901`

After download, write:

```json
{"files":[{"path":"gpt-oss-20b-MXFP4.gguf","size":12109566624}]}
```

to `$GPT_OSS_MODEL_DIR/.verified.json` only when size + SHA match.

## Environment

| Variable | Default | Meaning |
|---|---|---|
| `GPT_OSS_MODEL_DIR` | `$HOME/ai/models/gpt-oss-20b` | Weights + `.verified.json` |
| `LLAMA_ROOT` | `$HOME/ai/llama.cpp` | Tree containing `llama-server` |
| `GPT_OSS_GPU_LAYERS` | `24` | Layers on GPU (8 GB cards: keep modest) |
| `GPT_OSS_CTX` | `16384` | Context (repo-aligned) |
| `GPT_OSS_HOST` / `GPT_OSS_PORT` | `127.0.0.1` / `8080` | OpenAI-compatible bind |

API: `http://127.0.0.1:8080/v1`, alias **`gpt-oss-20b`**.

```bash
./local-ai/gpt-oss-server
# or: systemctl --user enable --now gpt-oss-server   # after installing the unit

cd local-ai
AI_BASE_URL=http://127.0.0.1:8080/v1 AI_VERIFY_REPORT=validation.local.json python3 -m verify
```

`validation.local.json` is gitignored (machine-local timings).

Why this exists: [docs/COMPATIBILITY.md](../docs/COMPATIBILITY.md).
