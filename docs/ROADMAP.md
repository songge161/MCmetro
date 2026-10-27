# Roadmap

## M0 — Foundation and compatibility survey

Status: `PARTIAL`.

Done in this first pass:

- Python package and CLI scaffold;
- local environment report via `minijapan doctor`;
- version-strategy ADR and source register;
- offline test path with a deterministic seed;
- explicit MTR integration boundary and research notes.

Still blocked or unverified:

- no Minecraft 1.20.1 + Fabric + MTR 4.0.x test instance exists locally;
- no exact target MTR release has been selected for a runtime smoke test;
- no safe, public batch write API has been proven for the target MTR build.

## M1 — Tokyo five-station compression prototype

Status: `DONE` for the offline acceptance path.

The YAML sample produces a schema-shaped plan, four geometry-only rail edges, validation output, and SVG preview. The routes are deliberately marked `demo_topology` and `requires_verified_mtr_adapter`.

## M1.5 — 门面与材料兼容计划原型

Status: `DONE` for the external planning layer.

The sample now produces two `facade_module` structure plans. Each module records its anchor station, footprint, floors, storefront count, window density, style profile and material intents. Semantic material slots have deterministic preferred and fallback blocks.

This milestone does not place blocks, inspect an installed mod registry, or preserve block-entity data. The selected materials are explicitly marked as availability-unchecked until a Minecraft bridge provides a registry manifest.

## M2 — One Minecraft district

Next smallest executable milestone:

1. Pin a Minecraft 1.20.1 Fabric instance and a specific MTR 4.0.x release.
2. Build one hand-authored Tokyo Station shell as a structure fixture.
3. Add a dry-run block executor and a reversible transaction manifest.
4. Test import into a disposable world before touching any user save.

## M3 — MTR functional gate

Do not implement a real adapter until source and in-game evidence show how the selected MTR build creates, persists, reloads, and runs stations, platforms, rails, routes, depots, and vehicles. If two focused spikes fail, keep `ManualMtrAdapter`/`MockMtrAdapter` and document the manual configuration path instead.
