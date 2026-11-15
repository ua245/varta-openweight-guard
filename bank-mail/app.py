#!/usr/bin/env python3
"""Imperial Demo Bank mail desk: inbox UI, send-as, summarize, OCR."""

from __future__ import annotations

import asyncio
import base64
import email.utils
import json
import mimetypes
import os
import smtplib
import tempfile
from email.message import EmailMessage
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Template

ROOT = Path(__file__).resolve().parent
SEED = ROOT / "seed"
MAILPIT = os.environ.get("MAILPIT_URL", "http://127.0.0.1:8025").rstrip("/")
SMTP_HOST = os.environ.get("BANK_SMTP_HOST", "127.0.0.1")
SMTP_PORT = int(os.environ.get("BANK_SMTP_PORT", "1025"))
LLM_BASE = os.environ.get("BANK_LLM_BASE", "http://127.0.0.1:8080/v1").rstrip("/")
LLM_MODEL = os.environ.get("BANK_LLM_MODEL", "gpt-oss-20b")
BANK_INBOX = os.environ.get("BANK_INBOX", "treasury@imperial-demo.bank")

app = FastAPI(title="Imperial Demo Bank Mail")
app.mount("/static", StaticFiles(directory=str(ROOT / "static")), name="static")

_ocr = None


def get_ocr():
    global _ocr
    if _ocr is None:
        from rapidocr_onnxruntime import RapidOCR

        _ocr = RapidOCR()
    return _ocr


PAGE = Template(
    """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Imperial Demo Bank · Mail Desk</title>
  <style>
    :root {
      --ink:#0b1f33; --paper:#f4f7fb; --card:#fff; --line:#d7e0ea;
      --accent:#0f4c81; --accent2:#1f6f8b; --warn:#b54708; --ok:#0f7b4c;
      --mono: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      --sans: "Iowan Old Style", "Palatino Linotype", Palatino, Georgia, serif;
      --ui: "Avenir Next", "Segoe UI", system-ui, sans-serif;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0; background:
        radial-gradient(1200px 500px at 10% -10%, #d9ebf7 0%, transparent 55%),
        linear-gradient(180deg, #e8eef5, var(--paper));
      color: var(--ink); font-family: var(--ui); min-height: 100vh;
    }
    header {
      padding: 1.25rem 1.5rem; border-bottom: 1px solid var(--line);
      background: rgba(255,255,255,.72); backdrop-filter: blur(8px);
      display: flex; gap: 1rem; align-items: baseline; flex-wrap: wrap;
    }
    header h1 { margin: 0; font-family: var(--sans); font-size: 1.45rem; letter-spacing: .02em; }
    header .tag { color: var(--accent); font-size: .85rem; }
    main { display: grid; grid-template-columns: 1.1fr .9fr; gap: 1rem; padding: 1rem 1.5rem 2rem; }
    @media (max-width: 960px) { main { grid-template-columns: 1fr; } }
    section {
      background: var(--card); border: 1px solid var(--line); border-radius: 14px;
      padding: 1rem 1.1rem; box-shadow: 0 10px 30px rgba(15,76,129,.06);
    }
    h2 { margin: 0 0 .75rem; font-size: 1rem; text-transform: uppercase; letter-spacing: .08em; color: var(--accent); }
    .msg {
      border: 1px solid var(--line); border-radius: 10px; padding: .75rem .85rem; margin: 0 0 .65rem;
      cursor: pointer; transition: border-color .15s, background .15s;
    }
    .msg:hover, .msg.active { border-color: var(--accent); background: #f7fbff; }
    .msg .sub { font-weight: 650; margin: 0 0 .25rem; }
    .msg .meta { color: #4a5d73; font-size: .82rem; }
    .detail pre, .ocr pre, .sum pre {
      white-space: pre-wrap; word-break: break-word; background: #f6f8fb;
      border: 1px solid var(--line); border-radius: 8px; padding: .75rem; font-family: var(--mono); font-size: .82rem;
    }
    label { display: block; font-size: .8rem; margin: .55rem 0 .2rem; color: #35506a; }
    input, textarea, select, button {
      width: 100%; font: inherit; padding: .55rem .65rem; border-radius: 8px;
      border: 1px solid var(--line); background: #fff;
    }
    textarea { min-height: 110px; resize: vertical; }
    button {
      margin-top: .7rem; background: linear-gradient(135deg, var(--accent), var(--accent2));
      color: #fff; border: 0; cursor: pointer; font-weight: 600;
    }
    button.secondary { background: #e8eef5; color: var(--ink); }
    .row { display: grid; grid-template-columns: 1fr 1fr; gap: .6rem; }
    .pill { display: inline-block; padding: .15rem .45rem; border-radius: 999px; background: #e7f1fa; color: var(--accent); font-size: .72rem; }
    .actions { display: flex; gap: .5rem; flex-wrap: wrap; }
    .actions button { width: auto; margin-top: .4rem; }
    .hint { font-size: .8rem; color: #52677d; margin: .35rem 0 .8rem; }
    a { color: var(--accent); }
  </style>
</head>
<body>
  <header>
    <h1>Imperial Demo Bank</h1>
    <span class="tag">Mail desk · {{ inbox }}</span>
    <span class="pill">SMTP {{ smtp_host }}:{{ smtp_port }}</span>
    <span class="pill">LLM {{ llm_model }}</span>
    <a class="pill" href="{{ mailpit }}" target="_blank" rel="noreferrer">Mailpit UI</a>
  </header>
  <main>
    <section>
      <h2>Inbox</h2>
      <p class="hint">Three seeded bank messages plus anything you send in. Click a message, then summarize or OCR attachments.</p>
      <div id="list"></div>
      <div class="detail" id="detail"><em>Select a message.</em></div>
      <div class="actions">
        <button type="button" id="btn-sum">Summarize with local model</button>
        <button type="button" class="secondary" id="btn-ocr">OCR attachments (model cleanup)</button>
        <button type="button" class="secondary" id="btn-refresh">Refresh</button>
      </div>
      <div class="sum" id="sum"></div>
      <div class="ocr" id="ocr"></div>
    </section>
    <section>
      <h2>Send into the bank</h2>
      <p class="hint">Send from another address into <strong>{{ inbox }}</strong> (or any recipient). Uses local SMTP — no internet relay.</p>
      <form id="send">
        <div class="row">
          <div>
            <label>From name</label>
            <input name="from_name" value="External Correspondent" required/>
          </div>
          <div>
            <label>From address</label>
            <input name="from_addr" value="vendor@outside.example" required/>
          </div>
        </div>
        <label>To</label>
        <input name="to_addr" value="{{ inbox }}" required/>
        <label>Subject</label>
        <input name="subject" value="Follow-up on treasury request" required/>
        <label>Body</label>
        <textarea name="body">Hello Treasury,

Please confirm receipt of our updated banking details.

Regards,
External Correspondent</textarea>
        <label>Optional image attachment (for OCR demo)</label>
        <input type="file" name="attachment" accept="image/*"/>
        <button type="submit">Send email</button>
      </form>
      <p id="send-status" class="hint"></p>
    </section>
  </main>
  <script>
    const inbox = {{ inbox|tojson }};
    let selected = null;

    async function loadList() {
      const r = await fetch('/api/messages');
      const data = await r.json();
      const list = document.getElementById('list');
      list.innerHTML = '';
      for (const m of data.messages) {
        const el = document.createElement('div');
        el.className = 'msg' + (selected === m.ID ? ' active' : '');
        el.innerHTML = `<div class="sub">${escapeHtml(m.Subject || '(no subject)')}</div>
          <div class="meta">${escapeHtml((m.From && m.From.Address) || '')} → ${escapeHtml(((m.To||[])[0]||{}).Address || '')}<br/>${escapeHtml(m.Created || '')}</div>`;
        el.onclick = () => selectMsg(m.ID);
        list.appendChild(el);
      }
    }

    function escapeHtml(s) {
      return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    }

    async function selectMsg(id) {
      selected = id;
      document.getElementById('sum').innerHTML = '';
      document.getElementById('ocr').innerHTML = '';
      const r = await fetch('/api/messages/' + id);
      const m = await r.json();
      const atts = (m.Attachments || []).map(a => `<li>${escapeHtml(a.FileName)} (${a.ContentType})</li>`).join('');
      document.getElementById('detail').innerHTML = `
        <h3 style="margin:.2rem 0">${escapeHtml(m.Subject || '')}</h3>
        <div class="meta">${escapeHtml(m.From?.Address || '')} · ${escapeHtml(m.Date || m.Created || '')}</div>
        <pre>${escapeHtml(m.Text || m.HTML || '')}</pre>
        ${atts ? `<p><strong>Attachments</strong><ul>${atts}</ul></p>` : ''}`;
      await loadList();
    }

    document.getElementById('btn-refresh').onclick = loadList;
    document.getElementById('btn-sum').onclick = async () => {
      if (!selected) return alert('Pick a message first');
      document.getElementById('sum').innerHTML = '<pre>Summarizing…</pre>';
      const r = await fetch('/api/messages/' + selected + '/summarize', { method: 'POST' });
      const d = await r.json();
      document.getElementById('sum').innerHTML = '<h2>Summary</h2><pre>' + escapeHtml(d.summary || d.error || JSON.stringify(d)) + '</pre>';
    };
    document.getElementById('btn-ocr').onclick = async () => {
      if (!selected) return alert('Pick a message first');
      document.getElementById('ocr').innerHTML = '<pre>Running OCR…</pre>';
      const r = await fetch('/api/messages/' + selected + '/ocr', { method: 'POST' });
      const d = await r.json();
      document.getElementById('ocr').innerHTML = '<h2>OCR</h2><pre>' + escapeHtml(d.report || d.error || JSON.stringify(d, null, 2)) + '</pre>';
    };
    document.getElementById('send').onsubmit = async (e) => {
      e.preventDefault();
      const fd = new FormData(e.target);
      const r = await fetch('/api/send', { method: 'POST', body: fd });
      const d = await r.json();
      document.getElementById('send-status').textContent = d.ok ? 'Sent.' : (d.error || 'Failed');
      if (d.ok) await loadList();
    };
    loadList();
  </script>
</body>
</html>
"""
)


async def mailpit_get(path: str) -> Any:
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(f"{MAILPIT}{path}")
        r.raise_for_status()
        return r.json()


async def mailpit_bytes(path: str) -> bytes:
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.get(f"{MAILPIT}{path}")
        r.raise_for_status()
        return r.content


async def llm_chat(system: str, user: str, max_tokens: int = 400) -> str:
    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_tokens": max_tokens,
        "temperature": 0.2,
    }
    async with httpx.AsyncClient(timeout=180.0) as client:
        r = await client.post(f"{LLM_BASE}/chat/completions", json=payload)
        r.raise_for_status()
        data = r.json()
    return (data["choices"][0]["message"].get("content") or "").strip()


@app.get("/", response_class=HTMLResponse)
async def home():
    return PAGE.render(
        inbox=BANK_INBOX,
        smtp_host=SMTP_HOST,
        smtp_port=SMTP_PORT,
        llm_model=LLM_MODEL,
        mailpit=MAILPIT,
    )


@app.get("/api/health")
async def health():
    out: dict[str, Any] = {"ok": True, "mailpit": None, "llm_models": [], "llm_error": None}
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            out["mailpit"] = (await client.get(f"{MAILPIT}/api/v1/info")).json()
    except Exception as e:
        return JSONResponse({"ok": False, "error": f"mailpit: {e}"}, status_code=503)
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            llm = (await client.get(f"{LLM_BASE}/models")).json()
        out["llm_models"] = [m.get("id") for m in llm.get("data", [])]
    except Exception as e:
        out["llm_error"] = str(e)
    return out


@app.get("/api/messages")
async def list_messages():
    data = await mailpit_get("/api/v1/messages?limit=50")
    return {"messages": data.get("messages", [])}


@app.get("/api/messages/{msg_id}")
async def get_message(msg_id: str):
    return await mailpit_get(f"/api/v1/message/{msg_id}")


@app.post("/api/messages/{msg_id}/summarize")
async def summarize_message(msg_id: str):
    msg = await mailpit_get(f"/api/v1/message/{msg_id}")
    body = (msg.get("Text") or msg.get("HTML") or "")[:3500]
    subject = msg.get("Subject") or ""
    frm = (msg.get("From") or {}).get("Address") or ""
    prompt = (
        f"From: {frm}\nSubject: {subject}\n\n{body}\n\n"
        "Summarize for a bank treasury desk in <=6 bullets: intent, amounts/refs, risks, required action."
    )
    try:
        summary = await llm_chat(
            "You summarize bank operations email. Be concise and factual. No preamble.",
            prompt,
        )
        return {"ok": True, "summary": summary}
    except Exception as e:
        raise HTTPException(502, f"LLM summarize failed: {e}") from e


@app.post("/api/messages/{msg_id}/ocr")
async def ocr_message(msg_id: str):
    msg = await mailpit_get(f"/api/v1/message/{msg_id}")
    atts = msg.get("Attachments") or []
    if not atts:
        return {"ok": False, "error": "No attachments on this message", "report": "No attachments."}

    engine = get_ocr()
    parts: list[str] = []
    for att in atts:
        ctype = (att.get("ContentType") or "").lower()
        name = att.get("FileName") or "attachment"
        if not ctype.startswith("image/") and not name.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff")):
            parts.append(f"## {name}\n(skipped non-image)")
            continue
        part_id = att.get("PartID") or att.get("ContentID") or ""
        # Mailpit: /api/v1/message/{id}/part/{partID}
        raw = await mailpit_bytes(f"/api/v1/message/{msg_id}/part/{part_id}")
        with tempfile.NamedTemporaryFile(suffix=Path(name).suffix or ".png", delete=False) as tmp:
            tmp.write(raw)
            tmp_path = tmp.name
        try:
            result, _ = engine(tmp_path)
            lines = [row[1] for row in (result or []) if row and len(row) > 1]
            raw_text = "\n".join(lines) if lines else "(no text detected)"
        finally:
            Path(tmp_path).unlink(missing_ok=True)

        try:
            cleaned = await llm_chat(
                "You clean noisy OCR from bank documents. Preserve numbers, refs, names. Output cleaned text only.",
                f"Filename: {name}\nOCR:\n{raw_text[:2500]}",
                max_tokens=350,
            )
        except Exception as e:
            cleaned = f"(model cleanup failed: {e})\n{raw_text}"

        parts.append(f"## {name}\n### Raw OCR\n{raw_text}\n\n### Model cleanup\n{cleaned}")

    report = "\n\n".join(parts)
    return {"ok": True, "report": report}


@app.post("/api/send")
async def send_email(
    from_name: str = Form(...),
    from_addr: str = Form(...),
    to_addr: str = Form(...),
    subject: str = Form(...),
    body: str = Form(...),
    attachment: UploadFile | None = File(None),
):
    msg = EmailMessage()
    msg["From"] = email.utils.formataddr((from_name, from_addr))
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg["Date"] = email.utils.formatdate(localtime=True)
    msg.set_content(body)

    if attachment and attachment.filename:
        data = await attachment.read()
        ctype, _ = mimetypes.guess_type(attachment.filename)
        maintype, subtype = (ctype or "application/octet-stream").split("/", 1)
        msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=attachment.filename)

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as s:
            s.send_message(msg)
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=502)
    return {"ok": True}


def seed_messages() -> int:
    """Inject seed emails over SMTP if inbox is empty-ish."""
    seeded_marker = ROOT / "data" / ".seeded"
    if seeded_marker.exists():
        return 0

    catalog = json.loads((SEED / "messages.json").read_text())
    count = 0
    for item in catalog:
        msg = EmailMessage()
        msg["From"] = email.utils.formataddr((item["from_name"], item["from_addr"]))
        msg["To"] = email.utils.formataddr((item["to_name"], item["to_addr"]))
        msg["Subject"] = item["subject"]
        msg["Date"] = email.utils.formatdate(localtime=True)
        msg["Message-ID"] = email.utils.make_msgid(domain="imperial-demo.bank")
        msg.set_content(item["body_text"])
        att = item.get("attachment")
        if att:
            path = SEED / att
            data = path.read_bytes()
            ctype, _ = mimetypes.guess_type(path.name)
            maintype, subtype = (ctype or "application/octet-stream").split("/", 1)
            msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=path.name)
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as s:
            s.send_message(msg)
        count += 1

    seeded_marker.parent.mkdir(parents=True, exist_ok=True)
    seeded_marker.write_text("ok\n")
    return count


@app.post("/api/reseed")
async def reseed():
    marker = ROOT / "data" / ".seeded"
    marker.unlink(missing_ok=True)
    n = await asyncio.to_thread(seed_messages)
    return {"ok": True, "seeded": n}


def main():
    import uvicorn

    uvicorn.run("app:app", host="127.0.0.1", port=int(os.environ.get("BANK_MAIL_PORT", "8090")), reload=False)


if __name__ == "__main__":
    main()
