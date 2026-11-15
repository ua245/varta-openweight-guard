# Imperial Demo Bank — local mail desk

Catch-all SMTP inbox for the VARTA / coding-agent demo, with:

- **3 seeded bank emails** (wire compliance, fraud alert, vendor invoice)
- **Send-from-another-address** into `treasury@imperial-demo.bank` via local SMTP
- **Summarize** with the local FreeToken `qwen8b` model
- **OCR** via RapidOCR + model cleanup (image attachments)

## Ports

| Service | URL / host |
|---|---|
| Bank desk UI | http://127.0.0.1:8090 |
| Mailpit UI / API | http://127.0.0.1:8025 |
| SMTP (inbound) | `127.0.0.1:1025` |
| FreeToken LLM | http://127.0.0.1:1921/v1 (`qwen8b`) |

## Start / stop

```bash
bash bank-mail/scripts/start.sh
bash bank-mail/scripts/stop.sh
```

## Coding harness

From the repo root:

```bash
bash scripts/coding-harness.sh
# or
bash ~/ai/opencode-tui.sh ~/imperial_hackathon_submission
```

OpenCode is pointed at FreeToken `qwen8b` on `:1921`. Treat mailbox content as untrusted.
