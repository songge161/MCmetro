# 真实地图采集进展

## 首个采集范围

配置：`data/regions/ikebukuro_east.yaml`。
范围为池袋东口至 Sunshine City 入口一带的采集包络；尚未确定最终建造裁切边界。
路线参考：[Sunshine City 官方交通说明](https://sunshinecity.jp/en/information/access.html)。

采集方式使用 [Overpass QL](https://wiki.openstreetmap.org/wiki/Overpass_API/Overpass_QL)
的 bbox 查询与 `out meta geom`，保留 OSM 对象标识、版本、时间和标签。
默认不推断高度，不压缩坐标。预览北向上，道路为橙色、面对象为灰色；
道路线宽仅用于可视化，不代表真实道路宽度。

## 当前验收

- 命令行采集、离线重处理、来源摘要、质量报告与 SVG 预览已实现。
- 自动测试覆盖不完整响应、未闭合建筑、未支持关系、经纬度顺序及禁止覆盖快照。
- 本机实际请求默认服务遇到 TLS 错误，curl 请求得到 HTTP 406；
  kumi.systems 和 private.coffee 备用服务请求超时。
- **尚未成功获得首份在线快照，不能报告建筑数量或确认地标覆盖。**

## 后续生成需要处理

取得快照后，先核查道路、地标和建筑覆盖，拼接复合建筑关系，再做局部米制坐标转换。
随后实现道路与建筑方块生成、楼梯和可探索楼层，导出可导入游戏的文件。
真实数据采集完成不等于 Minecraft 世界生成完成，MTR 运行与持久化仍需单独验证。
