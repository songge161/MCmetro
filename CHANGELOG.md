# Changelog

## Unreleased

- 新增 `material-probe`：版本摘要锁定的 Yuushya 灰墙/窗框测试区，含四向单窗与连接窗组；独立导出，不替换街区，游戏内待测。
- 新增只读 `inspect-mod`：Fabric JAR 来源摘要、中文名称与 blockstate 资源候选目录；不宣称运行时已兼容。
- 完成 Yuushya 1.20.1 Fabric 2.3.0 发布包摘要校验和首轮静态调查，记录 beta 状态与游戏验证边界。
- 发布 MC Metro v0.2 项目章程：明确通用城市生成器、本地优先和分层模组适配；原启动需求书完整归档。
- 同步 README、路线图与规划层边界说明，保留现有 Python 包名和 CLI 兼容性。
- 新增单宽直跑楼梯、候选失败重试和降层原因记录；真实样板增至 29 栋多层、149 个开放楼层。
- 新增轮廓内橱窗与入口饰带，以及含逐栋入口坐标的 Windows 验收清单；不宣称真实店铺还原。
- 新增 `generate-district`：真实快照到道路、建筑、入口、楼层、楼梯与基础照明。
- 新增 Sponge v2 `.schem` 导出、方块体量预览与 Windows 导入测试包。
- 新增楼层连通性、确定性输出和独立 NBT 解析验证；游戏内验收尚未完成。
- Added `extract-area` for clipping a local `.osm.pbf` by region bbox via `osmium-tool`.
- Split the data toolchain into a streaming clip layer (osmium) and a Python semantic parser.
- Added source register `data/sources/kanto_geofabrik.yaml` with retention and licence metadata.
- Switched the region data strategy to local-first; online Overpass is no longer a prerequisite.
- Added structured facade-module plans for street-frontage generation.
- Added semantic material slots with deterministic preferred/fallback resolution.
- Added facade footprint validation and material availability reporting.

## 0.1.0 — 2026-10-27

- Added the offline Python planner package and `minijapan` CLI.
- Added deterministic five-station/two-route Tokyo sample configuration.
- Added BuildPlan v1 JSON, validation JSON and SVG preview output.
- Added topology, coordinate, spacing, bounds and determinism tests.
- Added version strategy, source register and MTR integration investigation.
- Explicitly kept real Minecraft/MTR writes out of this milestone.
