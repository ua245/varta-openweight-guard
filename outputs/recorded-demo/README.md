# VARTA hackathon demo

Submit `verta-poc-demo.mp4`. It contains the business scenario, original Roundcube email, image-payload explanation, two fresh GPT-OSS runs, and the observed result. Spoken narration and on-screen captions explain the sequence.

The firm, client, settlement record, email, and capture endpoint are synthetic. The model and policy decisions are real. The supposed external portal resolves to a capture service inside the isolated worker. No data is sent to an external recipient.

## What changes between the runs

VARTA off executes the model's proposed tools directly. VARTA on checks each proposed operation against the firm's policy. The email bytes, decoded payload, privileged fixture, model configuration, worker image, and trusted briefing step are the same in both runs. The hidden image text is extracted by an explicit RGB-LSB decoder; the local vision model transcribes visible content.

Both modes run correspondence intake followed by the same trusted internal-briefing task. The same Guard object retains its state across those stages when VARTA is on. Successful drafting demonstrates this configured workflow's closeout behavior.

## Supporting files

- `verta-poc-demo.srt` contains the spoken transcript with timestamps.
- `narration.txt` provides a plain-text transcript.
- `recording-manifest.json` identifies the two runs, source hashes, capture events, and validation results.
- `verification.json` records media and evidence checks.
- `evidence/` contains the recorded runs' actual manifests, capture bodies, audit decisions, events, and saved briefs.
- The screenshots are frames captured during the recording, not replacements for the model runs.

The presenter layer adds chapter labels, readable type, captions, and highlights derived from actual events. Historical results are masked until a fresh run starts. It does not change model requests, tool results, or guard decisions. Narration uses the offline macOS Daniel synthetic voice.

The video uses fresh runs identified in its manifest. The companion walkthrough also records earlier validated test pairs. Screen captures retain their original wall-clock spacing; waiting time is not accelerated.

## Recreate the recording

Core project: [PoC branch on GitHub](https://github.com/ua245/imperial_hackathon_submission_-projectname-_1/tree/poc/law-firm-prompt-injection-demo). The bundle includes the recording files under `eval/law_demo/`; place them in that checkout before rerunning.

On the presenter Mac, keep SSH forwarding active for the dashboard and mailbox:

```bash
ssh -N -L 8095:127.0.0.1:8095 -L 8096:127.0.0.1:8096 ua@100.67.66.68
```

From the repository root, install the recording dependencies into the existing environment, then record:

```bash
uv pip install --python .venv/bin/python -r eval/law_demo/recording-requirements.txt
.venv/bin/python -m playwright install ffmpeg
.venv/bin/python -m eval.law_demo.record_demo --preview
.venv/bin/python -m eval.law_demo.record_demo
```

The recorder expects Google Chrome on macOS and the private mailbox-account file at `outputs/law-demo-mail-account.json`. Credentials are used before recording starts and are excluded from the deliverables. New recordings replace the output files; keep a copy of a submission before rerunning.
