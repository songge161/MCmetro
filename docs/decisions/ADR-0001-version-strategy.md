# ADR-0001: Candidate version strategy

- Status: `proposed`
- Date: 2026-10-27
- Decision scope: offline planning MVP and the future Minecraft runtime

## Decision

Keep Minecraft Java 1.20.1 + Fabric + MTR 4.0.x as the first compatibility candidate because the kickoff document prioritises that combination and Station Builder publishes a Fabric 1.20.1 build that lists MTR 4.0.x as its 1.20.x dependency family. This is a candidate baseline, not a compatibility claim.

The Python planner is intentionally independent of Minecraft and uses Python 3.9+ in this repository. A future runtime module must pin an exact Minecraft, Fabric Loader/API, MTR and Java combination after a disposable-world smoke test.

## Local evidence

Checked 2026-10-27 on macOS ARM64:

| Tool | Observed result | Consequence |
|---|---|---|
| Python | 3.9.6 | Sufficient for the offline planner; Python 3.11+ remains a later candidate for GIS wheels |
| Java | 25 LTS | Present, but not evidence that a particular MTR release accepts it |
| Gradle | not installed as a system command | Future Java work must use a project-provided Gradle wrapper |
| Minecraft runtime | not present in this repository | No game-integration claim is possible in M0/M1 |

## External evidence checked

- [MTR repository](https://github.com/Minecraft-Transit-Railway/Minecraft-Transit-Railway) describes 4.0.0 as a rewrite.
- [Station Builder 1.20.1 Fabric release](https://modrinth.com/mod/station-builder/version/FABRIC-0.1.1%2B1.20.1) is a concrete 1.20.1 Fabric build; its project page says 1.20.x uses MTR 4.0.x.
- [Transport Simulation Core README](https://github.com/Minecraft-Transit-Railway/Transport-Simulation-Core/blob/master/README.md) currently describes a Java 21 standalone backend. This must not be silently applied to every MTR distribution.
- [MTR API reference](https://wiki.minecrafttransitrailway.com/mtr%3Adevelopment%3Aapi_reference) is labelled outdated and says the HTTP API was removed in official MTR 4.0.

## Rejected assumptions

- `MTR 4.0.x` is not an exact build pin.
- A Station Builder dependency line is not proof that MiniJapan can create persistent MTR simulation objects.
- Java 25 being installed locally is not proof of MTR runtime compatibility.
- A read-only map endpoint or Transport Simulation Core message queue is not automatically a supported external write API.

## Exit criteria for changing the baseline

Change the candidate only after a documented spike shows that the exact 1.20.1 + Fabric + MTR 4.0.x combination cannot build, launch, persist, or support the required two-station test. Compare a 1.21.1/1.21.4 alternative in a new ADR before migrating.

