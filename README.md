# MiniJapan AI

MiniJapan AI is an open-source-first planner for a compressed, playable Japanese city in Minecraft. The first milestone is deliberately offline: it turns a YAML station graph into a deterministic BuildPlan and SVG preview. It does not write a Minecraft world and it does not claim to create an MTR route.

## Quick start

Python 3.9+ is required. The project uses PyYAML for the input format and pytest for tests.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
minijapan doctor
minijapan validate --config data/samples/tokyo_demo.yaml
minijapan plan --config data/samples/tokyo_demo.yaml --out out/demo
pytest
```

The plan command produces:

- `plan.json`: MiniJapan BuildPlan v1 with five synthetic stations and two demonstration routes;
- `validation.json`: errors and explicit warnings;
- `preview.svg`: a lightweight two-dimensional layout preview.

The sample positions and connections are synthetic. They are not a complete reproduction of Tokyo railway services, and the rail entries are geometry-only planning data. MTR integration remains unverified and is intentionally outside this offline MVP.

## Current status

M0/M1 offline planning foundation: `DONE` for the local, reproducible path. Minecraft runtime, `.schem` export, real GIS ingestion, and a real MTR write adapter are not implemented in this milestone. See [docs/ROADMAP.md](docs/ROADMAP.md), [docs/research/MTR_INTEGRATION.md](docs/research/MTR_INTEGRATION.md), and [LICENSE_DECISION.md](LICENSE_DECISION.md).

