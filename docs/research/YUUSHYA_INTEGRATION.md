# Yuushya 材料接入调查

核查日期：2026-10-30。阶段：官方包静态检查与定向材料测试文件生成，不是游戏内兼容性验收。

## 已获取的包

已从作者的 [Modrinth 发布页](https://modrinth.com/mod/yuushya-townscape/version/uEQ2095H)
获取 `yuushya-1.20.1-fabric-2.3.0.jar`，28,161,213 字节。
发布接口标记为 **beta**，本轮用于材料结构调查，尚未锁定为最终游戏基线。
下载文件 SHA512 与发布摘要一致；来源和完整摘要见
[数据源登记](../../data/sources/yuushya_fabric_1_20_1.yaml)。

本地路径：`data/raw/mods/yuushya-1.20.1-fabric-2.3.0.jar`。
文件处于 Git 忽略范围，只读分析，不执行 JAR、不安装到游戏、不再分发素材。

## 可复现的静态检查

```bash
python -m minijapan inspect-mod \
  --jar data/raw/mods/yuushya-1.20.1-fabric-2.3.0.jar \
  --out out/yuushya_1_20_1_2_3_0/catalog.json \
  --sha512 3c944f3648a1bf86c065767d6dc57cc171fc843136f254db11bce736d429bfed893ae37f7f60d041032690e2dbab61670f73f4be47b2f9683a0c0079a7521065
```

输出必须使用新路径。检查读取 `fabric.mod.json`、`assets/*/blockstates/*.json`
和同命名空间的 `lang/zh_cn.json`，提取资源候选身份、名称、渲染选择条件和模型引用。
支持摘要核对、大小限制、拒绝重名条目；不解包到文件系统、不加载模组代码。

实际结果：

- 5,773 个 blockstate 资源候选，全部位于 `yuushya` 命名空间。
- 其中 1,331 个直接匹配中文名称。
- 数量不是已验证可用方块数，不代表 5,773 种独立建材；派生形态和未注册资源需要进一步区分。
- `runtime_verified=false`；未把目录送入实际街区材料替换。

部分已观察到的候选：

| 候选 ID | 中文名称 | 仍需核查 |
| --- | --- | --- |
| `yuushya:gray_wall` | 灰墙 | 注册、默认状态、碰撞与贴图 |
| `yuushya:black_windows_0` | 黑色窗框 0 | 朝向和 `pos` / `ypos` 连接行为 |
| `yuushya:air_conditioner` | 空调 | 朝向、碰撞、附着与实际外观 |

`variants` 表示渲染选择条件，不是完整合法状态集，不能据此猜测默认值。
模组包还包含 `data/yuushya/register/` 下的自定义注册定义，下一步应结合加载代码解析，
再与运行时注册表对照，而不是仅凭名称把资源强行写入世界。

## 依赖与许可边界

该 JAR 的元数据声明：Fabric Loader >=0.16.0、Minecraft ~1.20.1、Java >=17、
Architectury >=9.2.14，以及 Fabric API。以上为本文件声明，不是已通过启动测试的组合。
[官方下载说明](https://yuushya.com/townscape/download-list/townscape.html)
还要求配套资源和连接纹理支持；本轮未验证这部分效果。

[作者仓库](https://github.com/XiLaiTL/Yuushya-Townscape) 区分代码 MIT 与美术资源 CC BY-NC-SA 4.0。
JAR 的 `license: MIT` 仅原样记录，不能据此将模型与贴图一并视作 MIT。
使用和发布前核对 [作者使用协议](https://github.com/XiLaiTL/Yuushya-Townscape/blob/master/Terms_yuushya_user.md)。

## 下一步验收

灰墙与黑窗框已经完成定向注册定义/类文件核对，并生成 11 组独立测试单元。
详见 [首组材料样板](../architecture/MATERIAL_PROBE.md)；下列流程中的游戏验证仍未完成，
不能从这两个条目推广为整个模组兼容。

1. 核对自定义注册定义和匹配版本源码，选少量静态建材而非一次支持全部资源。
2. 明确候选的合法状态、默认值、形态、碰撞及是否需要方块实体。
3. 建立首批墙面/玻璃/窗框映射，生成小型材料测试样板。
4. 在匹配依赖的 Minecraft 测试实例中检查渲染、行走与保存，记录通过/失败。
5. 验证通过后才替换真实街区；复杂门、招牌文字、连接模型分项推进。

用户暂不提供 Windows 整合包不会阻止前两步，但最终仍需对齐实际安装版本。
