# MC Metro

一个面向 Minecraft 的外部城市地图与交通网络生成器。

项目从真实地理数据、铁路数据和设计约束出发，在 Minecraft 世界之外完成城市布局、空间压缩、建筑规划、街道立面生成和交通网络规划，最后再导出为可以预览、校验和导入游戏的构建计划。

当前阶段先实现离线规划内核，不直接修改 Minecraft 世界，也不声称已经创建了可运行的 MTR 线路。

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

运行 `plan` 后会生成：

- `plan.json`：城市、站点、线路几何和执行参数；
- `validation.json`：错误、警告和当前适配能力；
- `preview.svg`：城市布局和演示线路的二维预览。

## 产品方向

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
- `.schem` 或 `.litematic` 导出；
- 真实 GIS 数据导入；
- Minecraft 方块注册表扫描和其他模组方块的运行时解析；
- 门面计划到实际方块的体素生成；
- 真实 MTR 写入适配器；
- 游戏内可乘坐线路的验收。

详见：

- [项目路线图](docs/ROADMAP.md)
- [MTR 集成调查](docs/research/MTR_INTEGRATION.md)
- [版本策略](docs/decisions/ADR-0001-version-strategy.md)
- [许可证决策](LICENSE_DECISION.md)
