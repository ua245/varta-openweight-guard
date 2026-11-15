#!/usr/bin/env python3
"""Local-only image API smoke test; Pillow is needed to generate the fixture."""
import argparse
import base64
import hashlib
import io
import json
import time
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8081/v1")
    parser.add_argument("--output", default="vision-verification.json")
    args = parser.parse_args()
    image = Image.new("RGB", (900, 240), "white")
    draw = ImageDraw.Draw(image)
    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    font = ImageFont.truetype(font_path, 46)
    expected = "NORTHBRIDGE LEGAL\nInvoice 7429\nTotal GBP 123.45"
    draw.multiline_text((28, 25), expected, font=font, fill="black", spacing=10)
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    payload = buf.getvalue()
    body = {
        "model": "qwen3-vl-2b-local", "temperature": 0, "max_tokens": 160,
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": "Transcribe the visible text exactly. Return only the transcription."},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64," + base64.b64encode(payload).decode()}},
        ]}],
    }
    start = time.monotonic()
    req = urllib.request.Request(args.url.rstrip("/") + "/chat/completions",
                                 data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as response:
        result = json.load(response)
    content = result["choices"][0]["message"]["content"]
    passed = all(value in content for value in ("NORTHBRIDGE", "7429", "123.45"))
    evidence = {"passed": passed, "endpoint": args.url, "model": result.get("model"),
                "image_sha256": hashlib.sha256(payload).hexdigest(), "expected": expected,
                "response": content, "seconds": round(time.monotonic() - start, 3),
                "usage": result.get("usage"), "scope": "Generated English image, no cloud calls"}
    Path(args.output).write_text(json.dumps(evidence, indent=2) + "\n")
    Path(args.output).with_suffix(".png").write_bytes(payload)
    print(json.dumps(evidence, indent=2))
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
