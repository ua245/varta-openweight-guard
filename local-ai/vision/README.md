# Local image reader for GPT-OSS

GPT-OSS 20B remains the text-only agent on port 8080. The optional Qwen3-VL
2B reader receives image pixels on loopback port 8081, then returns text through
`Tools.view_image`. The text remains untrusted input to the guard. Model prompts
are transcription guidance, not the security boundary.

```python
from agent.llm import OpenAICompatLLM
from agent.tools import Tools

tools = Tools(workspace, issues={}, vision=OpenAICompatLLM(
    "http://127.0.0.1:8081/v1", "qwen3-vl-2b-local"))
```

If the reader fails, `view_image` returns an error without forwarding pixels to
GPT-OSS. With no separate reader configured, the existing native-vision behavior
is preserved for models that support it.

The service uses the official Qwen Q4_K_M language weights (1,107,409,952 bytes)
and Q8_0 vision projector (445,053,216 bytes), 4,096 context tokens, one inference
slot, and at most 1,024 image tokens. Dense or small text may need cropped images.
The container has a 4 GiB RAM limit with no additional swap allowance. Startup
does not change GPT-OSS or other services.

Place the two model files in `models/`, then run `bash start.sh`. The script
deliberately fails if a container with the same name exists. After a successful
`python3 verify.py` smoke test, persistence can be enabled with
`docker update --restart unless-stopped varta-local-vision`.

`verify.py` generates an English invoice image and records its hash, exact
transcription, timing, and success condition. It requires Pillow and a Linux
DejaVu Sans font. This verifies visible-text reading only. It does not establish
legal-document accuracy, reliable handwriting recognition, steganographic
decoding, or native GPT-OSS image support. LSB extraction requires a separate
explicit decoder. Qwen advertises OCR in 32 languages; only English is exercised
by this smoke test.

Primary sources:

- [Official Qwen GGUF weights and usage](https://huggingface.co/Qwen/Qwen3-VL-2B-Instruct-GGUF)
- [Official Qwen model card and OCR language claim](https://huggingface.co/Qwen/Qwen3-VL-2B-Instruct)
- [llama.cpp official CUDA container documentation](https://github.com/ggml-org/llama.cpp/blob/master/docs/docker.md)
- [llama.cpp multimodal API and projector options](https://github.com/ggml-org/llama.cpp/blob/master/docs/multimodal.md)
