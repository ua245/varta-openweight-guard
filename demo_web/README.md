# Web demo — Agent Guard Console

`index.html` is a self-contained page (no server, no network) that animates the same
prompt-injection attack twice: without the guard (the secret leaks) and with it (blocked,
task still completed). The run data is embedded from real `agent.run` executions; the raw
copy is in `demo-data.json`.

## Use it
- Local: open `index.html` in a browser.
- On stage: published as a Claude Artifact (private link). Toggle **Guard OFF → Run**, then
  **Guard ON → Run** to show the before/after. Space bar also runs.

## Refresh the embedded data from new runs
Run both phases, then re-embed:
```bash
python3 -m agent.demo --scenario v3            # writes eval/results/demo-phase1.json / -phase2.json
# then rebuild demo_web/demo-data.json from those two files (see tools/embed_demo.py if present)
```
