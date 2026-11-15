# GPT-OSS 20B local coding environment

The local Ubuntu environment now serves **GPT-OSS 20B MXFP4** and runs
**OpenCode 2.3.0**. GLM-5.2 weights and its inference service were removed.
This folder records the working development environment and functional checks.
It does not add a new VARTA agent implementation.

## Verified environment

| Item | Configuration |
|---|---|
| Host | Apple M5 Pro, 48 GB unified memory |
| Guest | Ubuntu Server 24.04.5 ARM64 with XFCE; Lima/Krunkit |
| Guest allocation | 8 vCPUs; 24,000 MB RAM (22,888 MiB); 16 GiB sparse root disk |
| Weights | Separate read-only host folder mounted at `/models/gpt-oss-20b`; 12.11 GB |
| GPU | Experimental virtual Vulkan / Virtio-GPU Venus; **not physical GPU passthrough** |
| Runtime | llama.cpp in a pinned ARM64 Vulkan container, entirely inside Ubuntu |
| Model API | `http://127.0.0.1:8080/v1`, alias `gpt-oss-20b` |
| Context | 16,384 tokens; one concurrent request |
| Coding settings | Low reasoning effort; 128-token reasoning budget; 2,048 output tokens in OpenCode |
| Memory limits | Model container: 18 GB, no swap; VM: 24 GB |

The checkpoint plus VM fit comfortably below the 240 GB storage cap. The model
folder lives on the host so it is not duplicated into the 16 GiB guest root disk.
Apple GPU allocations may consume host unified memory outside guest RAM accounting.

## Run coding tasks

On the configured Ubuntu VM:

```bash
cd ~/ai-dev/projects
opencode
# One-shot task:
opencode run --model local/gpt-oss-20b "Inspect this project and propose a small improvement"
```

The installed global configuration is `~/.config/opencode/opencode.json`.
[`opencode.developer.json`](opencode.developer.json) is its source snapshot.
It uses the local OpenAI-compatible provider, short reasoning, up to eight build
steps, and the existing `ubuntu-mail` MCP server. Project edits and focused Python
checks are permitted; general shell commands require confirmation. It needs no
cloud model key; `apiKey: local` is a dummy compatibility value.
OpenCode was installed from its official Linux ARM64 distribution and the running
binary reported 2.3.0. This config follows its v2 schema (`providers`, `agents`,
and `mcp.servers`), which differs from older v1 examples.

Remote users can SSH into the VM with their existing Tailscale authorization and
SSH key, then run the same commands. SSH credentials, host addresses, VPN profiles,
mail account files and the private laptop access bundle are deliberately absent
from this repository. The model API stays on loopback; use an SSH local forward
when a client needs access from a different laptop.

### VARTA integration boundary

The OpenCode configuration above is an **operator development harness**, with
OpenCode's native tools and permissions. It is **not a VARTA-protected agent**.
Its successful tool calls establish runtime compatibility, not injection resistance.

For VARTA product agents, keep the existing architecture:

1. Discover the running model with `cargo run --manifest-path llm-map/Cargo.toml`.
2. Run `python -m proxy` from the repository root.
3. Point the product agent at `http://127.0.0.1:8787/v1`, selecting `gpt-oss-20b`.
4. Route every executed tool through `POST /v1/tools/execute`, as required by
   [`proxy/AGENT_CONTRACT.md`](../proxy/AGENT_CONTRACT.md).

Changing only OpenCode's model URL to the proxy does **not** intercept its native
file, shell or MCP tools. A mandatory tool adapter or disabling those native tools
is needed before claiming OpenCode is guarded. That integration and the poisoned
issue evaluation have not been performed by these local environment smoke tests.

## Model provenance and runtime

- Source: [ggml-org/gpt-oss-20b-GGUF](https://huggingface.co/ggml-org/gpt-oss-20b-GGUF)
- Revision: `41e8a94d15d62070b36cf4553a0250717ecf46b8`
- File: `gpt-oss-20b-MXFP4.gguf`
- Bytes: `12109566624`
- SHA-256: `27cd6c432c7672cb812a92f611cf3ba7bbc35928262bb1e1253ff4ee6ae35901`
- Container: `ghcr.io/unsuman/fedora-vgpu-llama@sha256:bc178266945dc706ef26e2cdb36c1b7e39edf33d79eb44aac46e0398aac1d591`
- Running llama.cpp build: `6ea215d`

The checkpoint was downloaded and hashed in full before the model service started.
No new quantization was performed; this uses the published MXFP4 checkpoint.
[`gpt-oss-server`](gpt-oss-server) and its [systemd unit](gpt-oss-server.service)
record the deployed launch parameters. This is a snapshot of an already provisioned
Lima/Krunkit environment, **not** a universal VM or GPU installer. Other machines
need a compatible virtual Vulkan device, container image, containerd/nerdctl and
model mount. Adjust the username and paths before deploying elsewhere.

The launcher expects a `.verified.json` marker in the model folder with:

```json
{"files":[{"path":"gpt-oss-20b-MXFP4.gguf","size":12109566624}]}
```

Create that marker only after the full file matches the SHA-256 above. The launcher
checks the marker and file size at startup; it does not rehash 12 GB on every restart.
The model mount should stay read-only in the guest. The service is enabled at boot.

```bash
sudo systemctl status gpt-oss-server
sudo journalctl -u gpt-oss-server -f
```

## Short functional checks and measured latency

[`verify.py`](verify.py) checks a streamed answer and a complete function-call/result
round trip using only the Python standard library. It is a model protocol check,
not an agent or tool executor. To run against the local backend:

```bash
cd local-ai
AI_VERIFY_REPORT=validation.local.json python -m verify
```

| Check | Observed result |
|---|---|
| Streaming | Answer `OK`; first visible content after 2.65 s |
| Tool round trip | Model called `add(19, 23)`, consumed result and answered `42`; 2.11 s |
| OpenCode coding | Created `arithmetic.py` with the write tool and ran two Python assertions |
| Independent verification | Generated file inspected and both assertions passed |
| OpenCode MCP | Called `ubuntu-mail.mail_list_folders`; actual INBOX: five messages, three unread |
| Restart | Model service restarted successfully and answered a subsequent streamed request |
| Generation | Approximately 47–73 tokens/s across these short requests |

The coding run first tried the assertions before creating the file, received a
module-not-found error, then wrote the file and reran them successfully. The first
OpenCode prompt contained about 4,500 tokens and took about 16 seconds to ingest;
later tool steps reused the prompt cache. Small API checks do not predict long
context latency, reliability on large code changes, or model quality. See
[`validation.json`](validation.json) for the recorded checks and limits.

## Mail and live resources

The VM retains its lightweight Postfix/Dovecot/Roundcube development mailbox,
including five sprint emails. Webmail is locally forwarded on port 8088. This is
local development mail; internet relay is disabled.

The existing read-only `ubuntu-mail` MCP exposes full message and body reads,
original attachments, inline/attached/data-URI image extraction, PNG previews,
and local Tesseract OCR. Original bytes are preserved. External image URLs are
never fetched and reads preserve message flags. GPT-OSS 20B is text-only; use OCR
for image text. Account credentials stay in the VM and are not part of this repo.
The published OpenCode snapshot assumes that existing MCP deployment; this folder
does not install the mail stack or its MCP server.

The host's live download preview at `http://127.0.0.1:8765/?resources=1` also shows:

- CPU percentage per core and I/O wait.
- Used/available guest RAM and root disk space.
- VM network receive/transmit rates, uptime and load averages.
- GPU device availability. GPU utilization is unavailable from this virtual driver.

[`ubuntu-resource-monitor.py`](ubuntu-resource-monitor.py) samples once per second
and serves JSON on guest loopback port 9109 at `/api/resources`, forwarded locally
by Lima. It runs under `ai-resource-monitor.service`, enabled at boot, with a 64 MiB
memory limit and a 5% CPU quota. [`download-dashboard.html`](download-dashboard.html)
is the deployed frontend. It additionally needs the host download service's
`/api/status` endpoint; this folder is a source snapshot, not a standalone dashboard
installer. Both endpoints were checked with advancing samples and dashboard CORS.
A disconnected VM is shown as reconnecting, not as a zero resource reading.

The root disk card excludes the host-mounted model checkpoint. The VM network
card measures guest traffic; the model downloaded on the Mac, so that transfer
is not counted as Ubuntu network usage. The Mac must remain awake and the VM
running for the local services and remote coding sessions to remain reachable.
