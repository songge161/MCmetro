# MTR integration investigation

Checked 2026-10-27. Statuses in this document are deliberately conservative.

## Confirmed from public documentation

1. The MTR project describes 4.0.0 as a complete rewrite.
2. The public [MTR API reference](https://wiki.minecrafttransitrailway.com/mtr:development:api_reference) is explicitly marked outdated and says the HTTP API was removed in the official MTR 4.0 release.
3. The [Transport Simulation Core architecture document](https://github.com/Minecraft-Transit-Railway/Transport-Simulation-Core/blob/master/docs/ARCHITECTURE.md) describes a standalone Java 21 core with per-dimension `Simulator` state, persisted data, a simulator-thread queue, and embedded-host message queues.
4. That architecture document names data concepts including stations, platforms, routes, depots, sidings, vehicles, rails and paths, and describes `update_data` as an operation key exchanged through the embedded message-queue path.
5. The same project exposes read-oriented map/OBA HTTP surfaces. Public documentation does not establish that these endpoints are a supported external write interface for an arbitrary mod or offline planner.

## Unverified for this project

- exact MTR 4.0.x artifact for Minecraft 1.20.1 and its loader/API dependency set;
- exact Java runtime requirement for that released artifact;
- whether a third-party Fabric mod can legally and safely invoke the embedded core's message queue from the selected MTR build;
- the concrete serialisation classes and versioned schemas needed to create station/platform/rail/route/depot/vehicle state;
- the relationship between Minecraft rail blocks, MTR rail data and Station Builder-created blocks in the selected build;
- save/reload behaviour after a programmatic mutation from outside the normal MTR UI;
- transaction, rollback and partial-failure semantics for a multi-object update;
- a supported way to verify in-game that a generated route is rideable after a restart.

## Current adapter decision

The repository exposes no real `Mtr4FabricAdapter`. The only safe first-round positions are:

- `MockTransitAdapter`: test-only, never claims a train runs;
- `ManualMtrAdapter`: future export of a human-readable configuration checklist;
- real adapter: blocked until the selected release source and a disposable-world spike verify the entire lifecycle.

The offline planner therefore writes `mtr_adapter: unverified_manual_or_mock_only` and marks every route `demo_topology` / `geometry_only_demo`.

## Minimum next spike

1. Pin the exact MTR and Fabric artefacts in a disposable Minecraft 1.20.1 instance.
2. Create two stations, one platform per station, one continuous rail path and one route manually.
3. Inspect the matching source and runtime data before attempting any code-driven mutation.
4. Restart the world and verify station, route, depot and vehicle state.
5. Only then prototype a read-only probe, followed by a dry-run operation preview. No direct data-file editing.

## Evidence links

- MTR project: https://github.com/Minecraft-Transit-Railway/Minecraft-Transit-Railway
- MTR API warning: https://wiki.minecrafttransitrailway.com/mtr:development:api_reference
- Transport Simulation Core README: https://github.com/Minecraft-Transit-Railway/Transport-Simulation-Core/blob/master/README.md
- Transport Simulation Core architecture: https://github.com/Minecraft-Transit-Railway/Transport-Simulation-Core/blob/master/docs/ARCHITECTURE.md
- Transport Simulation Core schema notes: https://github.com/Minecraft-Transit-Railway/Transport-Simulation-Core/blob/master/docs/SCHEMA.md
- Station Builder 1.20.1 Fabric release: https://modrinth.com/mod/station-builder/version/FABRIC-0.1.1%2B1.20.1

