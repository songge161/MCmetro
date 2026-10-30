# Facade generation and material compatibility

本文记录演示规划器的门面与语义材料协议，受 [项目章程](../../doc/PROJECT_KICKOFF.md) 约束。
它与真实街区生成器尚未完整打通；真实样板已有原版基础门面方块，见
[街区样板](DISTRICT_PILOT.md)。下文“计划层”不表示整个项目仍不能生成方块。

## Generation unit

The first generation unit is a `facade_module`, not an entire building interior. A module records:

- an anchor station and an offset from that anchor;
- width, depth and floor count;
- a street-facing style profile;
- storefront count and window density;
- semantic material intents;
- a deterministic seed and a non-replica flag.

This gives the system enough structure to make a street frontage coherent without pretending to reproduce every real shop exactly.

## Material resolution

The planner describes visual intent rather than hard-coding one mod's block IDs:

```yaml
materials:
  profile: vanilla_safe
  slots:
    facade_wall:
      preferred: [minecraft:bricks]
      fallback: minecraft:stone
```

The offline planner selects the first preferred candidate deterministically, but marks availability as unchecked. A future Minecraft bridge can provide the installed registry and resolve the first available preferred block, then the fallback. The report must retain the selected block and the reason for the selection.

## Compatibility boundary

Static blocks can usually be represented by namespaced IDs and block states. Block entities, inventories, text-bearing signs, machines, MTR rails and other functional objects require a version-specific runtime adapter. They must not be silently treated as decorative blocks.

Compatibility therefore has three states:

1. `preview`: the material intent can be drawn in a planning preview;
2. `structure`: a version-aware structure exporter can encode the block state;
3. `runtime`: an in-game adapter can place and verify the object and any required block entity data.

The semantic facade-module contract currently reaches the planning state only.
The district generator separately exports vanilla shopfront blocks; it does not yet consume this
material resolver or AI facade files. Yuushya static inventory and runtime validation remain distinct.
