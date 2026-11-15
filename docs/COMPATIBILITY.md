# Why deploying `guard-core` was hard (and what we fixed)

This branch’s README and `main`’s `local-ai/` snapshot describe a **specific** lab machine.
Copying those instructions onto a normal x86_64 NVIDIA box fails for several structural reasons.

## What was breaking

### 1. Model runtime assumed Apple ARM + virtual Vulkan
`local-ai/gpt-oss-server` (on `main`) launches:

- `nerdctl` + a **pinned ARM64** Fedora Vulkan image
- `--device Vulkan0` (Virtio-GPU Venus), not NVIDIA CUDA
- model mount at `/models/gpt-oss-20b` inside a Lima guest

On this host (Ubuntu x86_64, RTX 5060) that container cannot run, `/dev/dri` Vulkan is not the NVIDIA path, and `nerdctl`/containerd guest layout is absent. **Symptom:** no `gpt-oss-20b` on `:8080`, or the launcher exits immediately.

**Fix:** `local-ai/gpt-oss-server` CUDA launcher + `local-ai/gpt-oss-server.user.service` using stock `llama-server` from [ggml-org/llama.cpp](https://github.com/ggml-org/llama.cpp) CUDA builds, same weights/alias/ports as the repo.

### 2. 12 GB MXFP4 weights vs 8 GB VRAM
GPT-OSS 20B MXFP4 is ~12.1 GB. An 8 GB card cannot hold all layers. Naïve `--n-gpu-layers 99` OOMs or never becomes ready.

**Fix:** hybrid offload (`GPT_OSS_GPU_LAYERS` default 24); MoE experts stay mostly in system RAM (~16–18 GB RSS). Needs **≥24 GB RAM**, not just a GPU.

### 3. Port `:8080` already taken
Repo API is hard-coded to `http://127.0.0.1:8080/v1`. On this machine `sensible-sandbox-api` (n8n sandbox) already bound `127.0.0.1:8080`, returning `401 missing X-Api-Key` — easy to mistake for a broken llama server.

**Fix:** free `:8080` before start (documented in spin-up), or set `GPT_OSS_PORT` / `AGENT_BASE_URL` together.

### 4. Wrong / competing local LLM already in VRAM
A FreeToken Qwen3-8B worker held ~7 GB VRAM. Starting GPT-OSS beside it fails or thrash-swaps.

**Fix:** stop the other GPU server first (`systemctl --user stop freetoken` / clear VRAM).

### 5. `guard-core` agent defaults still pointed at Gemma/Ollama
`agent.check` / `agent.run` defaulted to `gemma4:e2b` and Windows-WSL Ollama URLs from the hackathon laptop notes. On the Ubuntu GPU box nothing listened there.

**Fix:** `example.env` + spin-up script default to `AGENT_BASE_URL=http://127.0.0.1:8080/v1` and `AGENT_MODEL=gpt-oss-20b`.

### 6. `Tools(..., vision=...)` TypeError risk
`agent/run.py` / `scenario.py` pass `vision=` into `Tools`, but `Tools.__init__` did not accept it — fine until `--vision-model` is used.

**Fix:** accept and store `vision` on `Tools`.

### 7. Mail + OCR demo was not in `guard-core`
Bank mailbox / summarize / OCR lived only as ad-hoc host setup. Health checks also failed closed when the LLM was still downloading.

**Fix:** `bank-mail/` (Mailpit + desk UI) and tolerant `/api/health` (mail can be up while the model warms).

### 8. No ASCII coding desk without OpenCode
`main`’s local-ai docs assume OpenCode 2.3 on ARM. That binary/config path is optional noise for guard demos.

**Fix:** `cview/` — stdlib ASCII REPL against the same OpenAI-compatible server.

## Quick bring-up (this host class)

```bash
# 1) secrets
cp example.env .env   # fill ADAPTION_API_KEY / TAVILY_API_KEY; chmod 600 .env

# 2) weights (exact repo revision + SHA)
#    → $HOME/ai/models/gpt-oss-20b/gpt-oss-20b-MXFP4.gguf + .verified.json

# 3) llama-server CUDA build under $HOME/ai/llama.cpp

# 4) free :8080, start model + mail + preflight
bash scripts/spin-up-guard-core.sh
python -m agent.check
python -m agent.run --model gpt-oss-20b --issue poisoned_issue_v3.md
```

See `local-ai/README.md` for weight provenance and verify checks.
