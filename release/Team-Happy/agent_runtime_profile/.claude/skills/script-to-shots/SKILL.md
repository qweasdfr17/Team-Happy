---
name: script-to-shots
description: 剧本拆镜。把某一集原文转成镜头列表/分镜结构，不替代分集规划。当用户说"拆成镜头""分镜""把这段剧本变成 shots"时使用。
user-invocable: true
---

# 剧本改分镜（Script to Shots）

本 skill 负责把指定集原文转换成镜头列表，不替代分集规划。

## 定位

- 输入：单集剧本原文（source/episode_N.txt 或 scripts/episode_N.json）
- 输出：镜头列表 + image_prompt + video_prompt + 资产引用
- **不负责**：分集规划、规范化剧本、生成视频

## script_policy 遵守

开始前先检查 `project.json` 的 `script_policy.mode`：

| 模式 | 行为 |
|------|------|
| **preserve**（默认） | 只能拆镜和生成提示词，**不得修改原文文字**。原文作为 `novel_text` 或 shot text 逐字保留 |
| **suggest_rewrite** | 改稿建议写入 `proposals/`，不写回正式 `scripts/` |
| **rewrite_approved** | （预留）用户确认后才应用改写 |

## 工作流

1. **读取原文**：某集的 `source/episode_N.txt` 或 `scripts/episode_N.json` 的 shot text
2. **读取 context_pack**：获取角色/场景/道具/风格信息
3. **拆镜**：
   - 按场景切换/对话轮次/动作节拍确定镜头边界
   - 每个镜头产出：shot_id + duration_seconds + section + voiceover_text（如有）
4. **生成提示词**：
   - `image_prompt.scene`：描述此刻画面（不从原文改写，只补充视觉细节）
   - `video_prompt.action`：描述镜头内动作
   - 引用角色/场景/道具名称到 characters_in_shot / scenes / props
5. **原文保留**：preserve 模式下，原文以 `novel_text` 或 shot text 原样保留

## 边界

- preserve 模式下，`image_prompt.scene` 和 `video_prompt.action` 是**视觉补充**，不得改变原文剧情
- 不确定的切镜点（如连续对话无法拆分）保持原文完整，不强行切
- 不替代分集规划、不替代规范化剧本
