# Source register

Checked 2026-10-27. This is a research register, not a statement that every source is already imported into the planner.

| Name | URL | Current version or revision observed | Licence | MC compatibility | Usable now | Evidence and risk |
|---|---|---|---|---|---|---|
| Minecraft Transit Railway | https://github.com/Minecraft-Transit-Railway/Minecraft-Transit-Railway | repository page describes 4.0.0 | repository licence file must be rechecked before redistribution | target family is MTR 4.0; exact MC build not pinned here | research only | 4.0 is a rewrite; version/API drift risk |
| MTR API reference | https://wiki.minecrafttransitrailway.com/mtr:development:api_reference | page applies to 4.0.0 beta | documentation page; not a code dependency | beta documentation | no | page explicitly says HTTP API was removed in official 4.0; do not copy endpoint code |
| Transport Simulation Core | https://github.com/Minecraft-Transit-Railway/Transport-Simulation-Core | `master`, checked 2026-10-27; README describes Java 21 | repository licence file must be rechecked before embedding | not a Minecraft mod by itself | research only | useful architecture and schema evidence; master may differ from released MTR artefacts |
| Station Builder | https://modrinth.com/mod/station-builder | project page checked 2026-10-27; concrete `0.1.1` Fabric `1.20.1` release | MIT | 1.20.1 Fabric/Forge and newer listed; 1.20.x MTR 4.0.x dependency family | candidate later | construction helper, not proof of MTR object persistence or a public automation API |
| mcbuild | https://github.com/harrynull/mcbuild | `main`, checked 2026-10-27 | MIT, with bundled Minecraft asset notices | live mod path is NeoForge 1.21.1; not Fabric 1.20.1 | research only | useful DSL/voxel/preview ideas; cannot be dropped into the target runtime |
| Arnis | https://github.com/louis-e/arnis | latest release observed `v3.3.0` | repository licence file must be rechecked before reuse | project README says Java 1.21.4+; also Bedrock/Luanti | research only | useful OSM/elevation/world pipeline; target version mismatch |
| plateau2minecraft | https://github.com/Project-PLATEAU/plateau2minecraft | `main`, checked 2026-10-27 | repository licence and PLATEAU data terms must be checked per asset | kickoff evidence says Java 1.19.4 test; no 1.20.1 claim made | research only | useful CityGML conversion reference; version/data assumptions need a fresh build |
| Project PLATEAU open data | https://www.mlit.go.jp/plateau/open-data/ | open-data portal checked 2026-10-27 | varies by dataset/provider; verify dataset terms | not an MC mod | later data source | official portal provides 3D city models; city, LOD and capture year vary |
| Japan N02 railway GIS 2025 | https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-N02-2025.html | 2025 nationwide WGS84 listing, `N02-25_GML.zip`, 14.2 MB | official dataset terms must be followed | not an MC mod | later ETL source | strong candidate for railway geometry; schema/licence attribution must be carried into provenance |
| OpenStreetMap | https://www.openstreetmap.org/ | live data, revision must be recorded at download time | ODbL; attribution and share-alike obligations | not an MC mod | later ETL source | suitable for roads/rail/POI; no live API dependency in the offline demo |
| OSM copyright and licence | https://www.openstreetmap.org/copyright | checked 2026-10-27 | ODbL for data; CC BY-SA 2.0 for documentation | not an MC mod | attribution guidance | derived datasets and published previews need appropriate attribution and licence handling |

## Operating rule

Before importing any live data or third-party asset, record the exact download date, URL, release/commit, checksum where practical, coordinate reference system, licence text, and transformation steps under `data/provenance/` or the relevant research document.

