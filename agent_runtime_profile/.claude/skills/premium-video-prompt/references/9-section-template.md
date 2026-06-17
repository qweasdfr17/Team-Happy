# 九板块提示词模板 (Placeholder)

> ⚠️ 此文件为占位。请将实战调试完成的九板块提示词模板填入此文件。

## 预计板块结构

1. 图片引用声明（图1/图2/图3）
2. 场景光影基调
3. 基础设定（角色/场景/声音）
4. 氛围与画质
5. 分镜内容（按秒拆解）
6. 运镜补充
7. 对白/配音指令
8. 负面约束
9. 音效设计

## 示例模板

```
【图片引用声明】
图片1：角色参考图 — {character_name}
图片2：场景参考图 — {scene_name}
图片3：道具参考图 — {prop_name}

【场景光影基调】
主光源：{direction}，{quality}，色温{kelvin}K
暗区：{position}，{reason}
空气介质：{medium}

【基础设定】
角色：{names}
场景：{scene}
声音：仅保留音效和环境音，无BGM，无字幕

【氛围与画质】
{film_stock}，{color_tone}，{aspect_ratio}，{grain}

【分镜内容】
分镜1 | 时长 {duration}s
景别：{shot_type}
运镜：{camera_motion}
构图：{composition}
动作：{action_description}

【负面约束】
{negative_rules}

【音效设计】
{sfx_timeline}
```
