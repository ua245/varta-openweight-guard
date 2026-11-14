"""Small functional checks for a local GPT-OSS OpenAI-compatible server."""
import json
import os
import time
import urllib.request
from pathlib import Path

BASE = os.environ.get("AI_BASE_URL", "http://127.0.0.1:8080/v1").rstrip("/")


def request(messages, **options):
    payload = dict(model="gpt-oss-20b", messages=messages, max_tokens=256,
                   temperature=0, reasoning_effort="low", **options)
    req = urllib.request.Request(BASE + "/chat/completions",
        data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    return urllib.request.urlopen(req, timeout=180)


def main():
    results = {"model": "gpt-oss-20b", "checks": {}}
    start = time.monotonic()
    first_content = None
    text = ""
    with request([{"role": "user", "content": "Reply with only OK."}], stream=True) as response:
        for line in response:
            if not line.startswith(b"data: ") or line.strip() == b"data: [DONE]":
                continue
            chunk = json.loads(line[6:])
            for choice in chunk.get("choices", []):
                content = choice.get("delta", {}).get("content") or ""
                if content and first_content is None:
                    first_content = time.monotonic() - start
                text += content
    assert text.strip() == "OK", text
    results["checks"]["streaming"] = {"passed": True, "answer": text,
        "first_visible_content_seconds": first_content, "total_seconds": time.monotonic() - start}

    messages = [{"role": "user", "content": "Call add with a=19 and b=23. After its result, answer with just the sum."}]
    tools = [{"type": "function", "function": {"name": "add", "description": "Add two integers.",
        "parameters": {"type": "object", "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}}, "required": ["a", "b"]}}}]
    start = time.monotonic()
    with request(messages, tools=tools, tool_choice={"type": "function", "function": {"name": "add"}}) as response:
        call_result = json.load(response)
    message = call_result["choices"][0]["message"]
    call = message["tool_calls"][0]
    args = json.loads(call["function"]["arguments"])
    assert call["function"]["name"] == "add" and args == {"a": 19, "b": 23}, call
    messages += [message, {"role": "tool", "tool_call_id": call["id"], "content": str(args["a"] + args["b"])}]
    with request(messages, tools=tools, tool_choice="none") as response:
        answer = json.load(response)
    assert answer["choices"][0]["message"]["content"].strip() == "42", answer
    results["checks"]["tool_roundtrip"] = {"passed": True, "arguments": args,
        "answer": "42", "total_seconds": time.monotonic() - start,
        "generation_tokens_per_second": call_result.get("timings", {}).get("predicted_per_second")}
    path = Path(os.environ.get("AI_VERIFY_REPORT", "validation.json"))
    path.write_text(json.dumps(results, indent=2) + "\n")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
