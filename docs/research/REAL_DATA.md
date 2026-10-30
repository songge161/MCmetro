# 真实地图采集进展

## 首个采集范围

配置：`data/regions/ikebukuro_east.yaml`。
范围为池袋东口至 Sunshine City 入口一带的采集包络；尚未确定最终建造裁切边界。
路线参考：[Sunshine City 官方交通说明](https://sunshinecity.jp/en/information/access.html)。

当前决策是本机离线优先，不部署服务器。实际使用
[BBBike Tokyo 城市提取包](https://download.bbbike.org/osm/bbbike/Tokyo/)，
源登记于 `data/sources/tokyo_bbbike.yaml`；Geofabrik 关东包保留为备选来源。

本地裁切会保留 OSM 对象标识、版本、时间和标签。默认不推断高度，不压缩坐标。
预览北向上，道路为橙色、面对象为灰色；道路线宽仅用于可视化，不代表真实道路宽度。

## 当前验收

- Overpass JSON 的命令行处理、来源摘要、质量报告与 SVG 预览已实现。
- `extract-area` 已完成本地 PBF 裁切，osmium 负责流式裁切、Python 负责语义解析。
- 自动测试覆盖不完整响应、未闭合建筑、未支持关系、经纬度顺序及禁止覆盖快照。
- 本机实际请求公共 Overpass 服务出现 TLS、容量、拒绝和超时问题，故不再把它作为
  池袋样板区的前置依赖。
- 关东全量包（Geofabrik，约 595MB）直连被重置；改用 BBBike Tokyo 提取包（约 92MB），
  经本地代理可下载，但该源拒绝 Range 请求，只能整包下载。

## 首份真实快照（2026-10-29）

来源：BBBike Tokyo 提取包，裁切 bbox `[35.7278, 139.7110, 35.7320, 139.7195]`，
产物位于 `data/processed/ikebukuro_east/`（不进 Git）。

- 原始元素 8881，产出 2509 个地物：POI 1108、道路 849、建筑 490、building_part 62。
- 闭合建筑轮廓 488 个，其中 291 个缺少 `height` / `building:levels`。
- 地标命中：池袋駅 48、東池袋 22、サンシャインシティ 11、サンシャイン60 6。
- 未拼接的 relation 185 个（POI 159、building_part 21、building 3、road 2），
  大型复合建筑目前仍会缺轮廓。
- 全流程耗时约 0.9 秒，中间文件自动清理。

## 首个方块样板

`generate-district` 已从上述真实快照生成 Sunshine 60 通西段样板：181×156 格，
38 栋建筑，其中 29 栋多层、9 栋因楼梯空间约束简化为单层，共 149 个开放楼层。
产物位于 `out/ikebukuro_pilot_v5/`；原基线保留。新增单宽楼梯恢复了 3 栋上层。
包含 Sponge v2 `.schem`、平面/方块体量预览、逐栋入口坐标验收清单、
逐建筑质量报告和 Windows 测试包。已完成离线通行检查和独立 NBT 解析验证。

下一步是游戏内导入、楼梯实际行走与重启保存验收；复合建筑、精细门面、
Yuushya 材料、街段压缩和 MTR 运行适配仍需继续实现或验证。
细节见 [街区样板说明](../architecture/DISTRICT_PILOT.md)。
