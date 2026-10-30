# MC Metro

一个面向 Minecraft 的外部城市地图与交通网络生成器。

以 [项目章程](doc/PROJECT_KICKOFF.md) 为当前范围与验收依据：本地优先、创造模式探索、
真实街区生成先行，模组材料和交通分层接入。产品不限定城市，池袋是首个验证地点。
旧版大地图设想已 [归档](docs/archive/PROJECT_KICKOFF_v0.1.md)，不作为当前执行目标。

项目从真实地理数据、铁路数据和设计约束出发，在 Minecraft 世界之外完成城市布局、空间压缩、建筑规划、街道立面生成和交通网络规划，最后再导出为可以预览、校验和导入游戏的构建计划。

当前支持离线规划和真实街区方块样板的 `.schem` 导出，不直接修改 Minecraft 世界。
游戏内导入验收和可运行 MTR 线路仍未完成。

## 当前能力

- 从 YAML 配置读取站点和线路；
- 对站点进行确定性空间压缩；
- 校验站点坐标、路线拓扑、最小间距和世界边界；
- 输出 BuildPlan v1 JSON；
- 输出校验结果和 SVG 平面预览；
- 生成门面模块计划，包括楼层、店面数量、窗户密度和街道立面风格；
- 使用语义材料槽位和首选/降级方块方案；
- 使用固定 seed 重复生成相同结果；
- 明确区分演示拓扑、几何规划和真实游戏交通对象。
- 从真实局部快照生成道路、建筑、入口、开放楼层、楼梯和基础照明；
- 导出 Java 1.20.1 方块状态的 Sponge v2 `.schem`、二维与方块体量预览、Windows 测试包。

当前示例包含五个演示站点、两条演示线路。示例连接只用于验证规划流程，不代表完整的现实铁路线路。

## 快速开始

需要 Python 3.9 或更高版本。

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'

python -m minijapan doctor
python -m minijapan validate --config data/samples/tokyo_demo.yaml
python -m minijapan plan --config data/samples/tokyo_demo.yaml --out out/demo
python -m pytest
```

也可以运行完整验证脚本：

```bash
./scripts/verify.sh
```

## 输出文件

当前采用“本地区域数据优先”的采集策略：下载一次区域 OSM 数据包，
在本机裁切池袋等样板区并反复生成。不会建设或依赖线上地图服务。
数据源登记在 `data/sources/`：`tokyo_bbbike.yaml`（当前使用，约 92MB）
和 `kanto_geofabrik.yaml`（备选，约 595MB）。原始包和生成快照均不提交 Git。

现有的 Overpass 快照处理命令仍可用于已取得的 JSON 数据：

```bash
python -m minijapan fetch-area --config data/regions/ikebukuro_east.yaml --out data/raw/area_snapshot
```

输出原始 `osm.json`、WGS84 坐标的 `features.geojson`、`preview.svg`、
数据质量 `quality.json` 和包含来源、时间、SHA256、许可的 `manifest.json`。
每次使用新目录，避免覆盖历史快照。原始地图数据不提交到 Git。
已有快照用 `--input 路径/osm.json` 离线重处理，此时不会声称重新获取了在线数据。

池袋等样板区的默认来源是本地 `.osm.pbf`，需要先安装 `osmium-tool`
（`brew install osmium-tool`）。裁切与解析分两层：osmium 负责流式裁切，
Python 负责语义解析，不引入额外的 Python 地理依赖。

```bash
python -m minijapan extract-area \
  --config data/regions/ikebukuro_east.yaml \
  --pbf data/raw/tokyo.osm.pbf \
  --source data/sources/tokyo_bbbike.yaml \
  --out data/processed/ikebukuro_east
```

输出 `features.geojson`、`quality.json`、`manifest.json`（含 PBF 的 SHA256、
裁切 bbox、osmium 版本和许可）和 `preview.svg`。中间文件默认在成功后删除，
加 `--keep-intermediate` 可保留。

当前支持道路折线、闭合建筑轮廓和兴趣点。关系型复合建筑尚未拼接，
会逐项记录在质量报告中，完整成员仍保留在原始快照。缺失高度不自动补造，
采集边界外的完整对象暂不裁切。数据遵循
[OpenStreetMap 许可与署名要求](https://www.openstreetmap.org/copyright)。

## 实际街区生成

使用已有真实快照生成小范围样板：

```bash
python -m minijapan generate-district \
  --snapshot data/processed/ikebukuro_east \
  --config data/regions/ikebukuro_pilot.yaml \
  --out out/ikebukuro_pilot_v5
```

输出 `district.schem`、`district.json`、`preview.svg`、`preview-3d.svg`、
`导入说明.md`、逐栋 `验收清单.md` 和可复制到 Windows 的 `district-package.zip`。输出目录必须是新目录。
当前样板约 181×156 格，38 栋建筑，其中 29 栋多层、9 栋因楼梯空间约束简化为单层，共 149 个开放楼层。
双宽/单宽楼梯按实际空间与连通检查选择；入口附近增加原版橱窗和饰带，不代表真实店铺。
已实现每个入口接入地面道路、每层开放空间连通性检查及确定性导出。
检查基于体素近似，不是 Minecraft 碰撞引擎，游戏内导入和行走仍须实测。

首版采用未压缩的平面米制坐标、原版方块和开放楼层。无高度数据时默认三层，
高度标签推定、楼层上限、入口和外观设计均明确记录。跨边界轮廓、复合建筑、
地下与高架尚未生成；不将程序设计标为真实门面还原。
参见 [首个街区样板与验收](docs/architecture/DISTRICT_PILOT.md)。

运行 `plan` 后会生成：

- `plan.json`：城市、站点、线路几何和执行参数；
- `validation.json`：错误、警告和当前适配能力；
- `preview.svg`：城市布局和演示线路的二维预览。

## 产品方向

### 模组材料检查

已增加只读 Fabric JAR 资源检查，不运行模组，也不把资源目录当作实际方块注册表：

```bash
python -m minijapan inspect-mod --jar 路径/模组.jar --out out/mod-catalog.json
```

可通过 `--sha512` 核对发布摘要，输出路径必须未存在。
Yuushya 官方包已完成首轮静态检查，具体版本、候选材料和未验证项见
[Yuushya 接入调查](docs/research/YUUSHYA_INTEGRATION.md)。游戏中的材料替换尚未完成。

首组灰墙与窗框测试文件可单独生成，不替换现有街区：

```bash
python -m minijapan material-probe \
  --jar data/raw/mods/yuushya-1.20.1-fabric-2.3.0.jar \
  --out out/yuushya_material_probe_v2
```

输出 11 组材料测试单元、`.schem` 与验收说明；只接受已核对摘要的发布包。
玻璃为原版对照，游戏内验证仍待完成。见 [材料样板说明](docs/architecture/MATERIAL_PROBE.md)。

### 外部生成器与游戏内适配

MC Metro 是一个外部地图生成系统，不是单独依赖游戏运行的建筑 Mod。

外部系统负责：

- 地理与铁路数据处理；
- 城市空间压缩；
- 建筑体量和街区风格规划；
- 门面、招牌、窗户和街道细节生成；
- 材料与其他模组方块的兼容选择；
- 生成前预览、校验、Dry Run 和回滚计划。

Minecraft 内的辅助 Mod 或导入工具未来负责：

- 将构建计划写入世界；
- 检查当前安装的方块和模组；
- 分区执行建造任务；
- 对接具有运行逻辑的交通模组；
- 读取游戏状态并完成结果验证。

## 当前状态

离线规划基础：`已完成`。

以下内容尚未实现：

- Minecraft 世界写入；
- `.litematic` 导出和游戏内导入验收；
- 复合建筑关系拼接、地形高程与选择性街段压缩；
- Minecraft 方块注册表扫描和其他模组方块的运行时解析；
- 精细门面、AI 设计文件到方块生成的连接；
- 真实 MTR 写入适配器；
- 游戏内可乘坐线路的验收。

详见：

- [项目路线图](docs/ROADMAP.md)
- [MTR 集成调查](docs/research/MTR_INTEGRATION.md)
- [版本策略](docs/decisions/ADR-0001-version-strategy.md)
- [许可证决策](LICENSE_DECISION.md)
