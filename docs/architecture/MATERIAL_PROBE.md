# Yuushya 首组材料测试区

日期：2026-10-30。状态：已经离线生成并检查，尚未在 Minecraft 中运行验收。
本轮不替换真实街区，不宣称实现通用模组兼容或运行时注册表扫描。

## 产物和复现

```bash
python -m minijapan material-probe \
  --jar data/raw/mods/yuushya-1.20.1-fabric-2.3.0.jar \
  --out out/yuushya_material_probe_v2
```

只接受已核对的发布包 SHA256（见 [来源登记](../../data/sources/yuushya_fabric_1_20_1.yaml)），
不同版本或修改后的 JAR 必须重新审查，不能自动沿用状态。输出目录必须未存在。

样板尺寸为 36×8×26（X/Y/Z），地板 Y=0、玩家脚底 Y=1。
包含 36 个 Yuushya 灰墙、49 个 Yuushya 黑窗框、20 个原版玻璃对照块；
加上底座和空气，导出调色板共 44 个状态。

11 个测试单元：灰墙面板、玻璃面板、四向单窗、四向 3×3 窗组、5×5 灰墙嵌窗。
产物为 `yuushya-probe.schem`、`probe.json`、平面索引 `preview.svg`、`导入与验收.md`
及 `yuushya-probe-package.zip`。测试包不含模组、模型或贴图；预览不是材质渲染或游戏截图。

## 定向静态核对

使用官方 JAR 内注册 JSON、渲染选择条件、碰撞文件和 `javap -c -p` 只读反汇编。
未执行模组代码、未构建 Minecraft 运行实例；未以主分支源码代替发布版本证据。
匹配包内每份所用资源与关键类文件的摘要进入 `probe.json`。

| 证据 | 观察结果 |
| --- | --- |
| `Yuushya.init` / `AddonLoader.getRegister` | 加载注册资源、合并类定义并交给注册层 |
| `YuushyaRegistryConfig` | `class_type` 对应基础模板，实例定义优先；本轮只处理两个条目的必要标量字段 |
| `texture.json` 中 `gray_wall` | 继承 `block`，使用 `block` 模板，具有碰撞与实体形状 |
| `block_window.json` 中 `black_windows_0` | 继承 `WindowsBlock`，覆盖为 `pole_line` 模板，实例开启碰撞 |
| `YuushyaBlockFactory` / `BlockWithClassTypeNormal` | 非 solid 条目添加含水属性；窗框非 solid 不表示没有碰撞 |
| `PoleLineBlock` / `LineBlock` / `PoleBlock` | 朝向、横向连接、纵向连接和邻接更新逻辑 |
| 包内 collision 文件 | 灰墙为 16 单位立方体；窗框有 64 个选择条件，部分边界超出单格 |

反混淆符号通过 Fabric 的
[属性映射](https://maven.fabricmc.net/docs/yarn-1.20.1+build.10/net/minecraft/state/property/Properties.html)、
[方向映射](https://maven.fabricmc.net/docs/yarn-1.20.1+build.10/net/minecraft/util/math/Direction.html) 和
[坐标映射](https://maven.fabricmc.net/docs/yarn-1.20.1+build.10/net/minecraft/util/math/BlockPos.html)
核对。尤其 `field_12508` 是 WATERLOGGED，不出现在渲染选择条件中不代表状态不存在。

本轮显式导出：

- 灰墙：`yuushya:gray_wall`，不人为添加方向属性。
- 窗框：`yuushya:black_windows_0[facing=...,pos=...,waterlogged=false,ypos=...]`。
- 单窗：`pos=none,ypos=none`。
- 横向成组：列沿 +X（南北朝向）或 +Z（东西朝向）增加；北/东朝向首列为 left，南/西首列为 right，中间为 middle。
- 纵向成组：底层 bottom、中间 middle、顶层 top。

这些是被核对并用于实验的显式状态，不是对所有 Yuushya 材料默认状态的推断。
渲染模型只核查直接引用存在，没有展开全部模型继承与贴图，也没有复制碰撞引擎。
独立 NBT 解析能证明状态已写入文件，不能证明 WorldEdit 与 Minecraft 会按预期加载。

## 必须完成的游戏内验收

在独立 Java 1.20.1 Fabric 测试实例中准备匹配 Yuushya、依赖和 WorldEdit，按测试包说明导入。
本轮版本为 2.3.0 beta，不是用户整合包或最终产品基线的替换决定。

1. 无未知 ID/状态警告、没有缺失贴图；确认单块和成组样本都存在。
2. 正反两面观察四向窗组，检查透明度、窗框边缘和中央连接。
3. 步行靠近墙面和窗框，检查碰撞和超出方格的部分，不假定窗框为完整立方体。
4. 在测试副本拆除并恢复窗组中心，验证邻接更新后状态仍正确。
5. 保存退出、重进，检查上述结果。

全部待测。遇到错误保留样本 ID、精确版本与截图；先修复独立样板，不扩散到整片街区。
