# GPT-OSS second-tool-turn PEG failure: primary-source diagnosis

Researched 2026-11-15 without modifying code or services. Target build supplied by the active investigation: `b12387-a956a852c`; resolved source commit `a956a852c9c8bc1fb07206364838ddef299178c0`.

The strongest candidate is discarded historical reasoning. The current `agent/llm.py` only reads `message.reasoning` and drops `message.reasoning_content`; `agent/loop.py` removes its own `reasoning` field before appending the assistant message to history. llama.cpp's GPT-OSS handler explicitly copies historical `reasoning_content` into the `thinking` field consumed by its Harmony template. This supports fixing client transcript preservation before changing generation settings. It does not prove the exact local failing request has that single cause. [Pinned GPT-OSS handler, lines 7–17](https://github.com/ggml-org/llama.cpp/blob/a956a852c9c8bc1fb07206364838ddef299178c0/common/parsers/gpt-oss.cpp#L7), [local client](../agent/llm.py), [local loop](../agent/loop.py).

A directly matching upstream issue contains unusually useful confirmation: a maintainer says omitting `reasoning_content` on assistant tool-call messages causes erratic GPT-OSS behavior. The reporter then reproduced zero parser failures in 120 turns with reasoning retained versus seven in 120 when stripped, and withdrew an earlier cache-origin theory. Treat these as the reporter's experiment, not a measured local rate. The recommended client change is to retain the exact server-returned `reasoning_content` on assistant tool-call messages sent back to the same model; logging/display of reasoning is separate. [Maintainer guidance](https://github.com/ggml-org/llama.cpp/issues/27720#issuecomment-5417498538), [reporter's follow-up](https://github.com/ggml-org/llama.cpp/issues/27720#issuecomment-5426766551).

The exact error describes a generated response that fails the native chat parser. The upstream issue above reproduces it using text plus ordinary tool histories; it does not establish an image-specific fault. Since the reported local failure occurs before an image tool executes and the request contains text only, blaming PNG bytes or GPT-OSS image handling is unsupported. [Upstream issue](https://github.com/ggml-org/llama.cpp/issues/27720).

## Request settings, verified at the target revision

| Setting | Supported behavior | Relevance |
|---|---|---|
| `reasoning_content` in historical assistant messages | GPT-OSS template remaps it to `thinking` | First candidate: preserve exact returned value through client and loop |
| `chat_template_kwargs` | Per-request values merge over server defaults | No restart needed; template-dependent |
| top-level `reasoning_effort: "low"` | Passed into template; `none` disables thinking | Low is an available setting, not a demonstrated parser cure |
| `parallel_tool_calls: false` | Overrides model/template capability default | Simplifies multi-tool output; does not repair missing history |
| `tool_choice: "required"` | GPT-OSS uses eager grammar instead of its normal lazy tool grammar | Forces a tool call, so reserve for a legitimate known intake step; changes evaluation semantics if applied to every turn |
| `grammar` with active tools | Explicitly rejected by server | Do not add an ad hoc grammar alongside normal tools |
| `grammar_lazy`, `grammar_triggers`, `preserved_tokens` | Removed from request sampling parameters because the chat session owns them | Setting `grammar_lazy:false` in the request is ineffective here |
| `reasoning_format: "none"` | Changes extraction to raw content | Does not relax the native tool format; not a recommended fix |
| `response_format` schema | GPT-OSS constructs an eager schema response grammar | Appropriate for an explicitly structured response path; changes the output protocol and is not a drop-in tool-loop repair |

[Server request handling, lines 1512–1635](https://github.com/ggml-org/llama.cpp/blob/a956a852c9c8bc1fb07206364838ddef299178c0/tools/server/server-common.cpp#L1512), [GPT-OSS grammar selection, lines 63–151](https://github.com/ggml-org/llama.cpp/blob/a956a852c9c8bc1fb07206364838ddef299178c0/common/parsers/gpt-oss.cpp#L63), [server request documentation](https://github.com/ggml-org/llama.cpp/blob/a956a852c9c8bc1fb07206364838ddef299178c0/tools/server/README.md#post-v1chatcompletions-openai-compatible-chat-completions-api).

A separate official issue documents bare-final/schema-induced Harmony parsing failures and distinguishes prompt-only JSON demands from `response_format`. Its initial suggestion that streaming avoids the error is not a general guarantee; other issue reports show streamed malformed headers too. No universal per-request parser-relaxation flag is established by these sources. [Issue 25321](https://github.com/ggml-org/llama.cpp/issues/25321).

## Bounded implementation recommendation

First preserve assistant `reasoning_content` in the existing loop and retry the frozen failing transcript. Record success/failure with the exact same tools, prompt, sampling, guard arm and model. Keep any extra generation-setting experiments separate.

A disclosed deterministic intake stage is also a reasonable product workflow: perform the legitimate mail read and signature-image analysis before asking GPT-OSS to reason over resulting text. Every actual read and image analysis must still pass the normal VARTA dispatch/inspection gate, and external provenance must survive into the model's session. Start the subsequent model transcript with the actual untrusted extracted content and real intake audit trail; do not fabricate model-selected tool calls. This avoids requiring the model to self-select `view_image`, but changes the workflow and should be applied consistently to both guard arms. It remains a real model-driven action test if the later confidential read and transfer proposals come from GPT-OSS and actual effects are captured.
