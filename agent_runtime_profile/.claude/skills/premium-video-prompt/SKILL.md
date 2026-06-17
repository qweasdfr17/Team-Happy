---
name: premium-video-prompt
description: 精品视频提示词生成器。基于剧本原文 + context_pack + prompt_library 精品模板，生成正式 video_prompt 或 reference_video unit prompt。当用户说"生成视频提示词""写 video prompt""做精品提示词"时使用。
user-invocable: true
---

# 精品视频提示词生成器

本 skill 是正式 video_prompt 生成器，不是参考资料。

## 输入

1. **剧本原文**：脚本分镜原文或 unit shot text（只读）
2. **context_pack**：`context/context_pack.json`（项目级剧本理解）
3. **资产引用**：角色/场景/道具/产品的 @mention + sheet 图
4. **prompt_library**：通过 `prompt-library` API 查询精品模板（category=video_prompt, tags=...）

## 工作流

1. **读取 context_pack**：从 `context/context_pack.json` 获取 shot_intent_map、characters_with_aliases、style_bible
2. **查询 prompt_library**：根据 content_mode / style / 镜头类型 取 1-3 条最相关模板
3. **逐个镜头生成 video_prompt**：
   - 剧本原文**不得改写**（遵守 `script_policy.mode`）
   - 从 prompt_library 模板填入 action / camera_motion / ambiance_audio / dialogue
   - 引用资产名通过 @mention 注册，不重复描述外观
4. **输出**：video_prompt 或 reference_video unit prompt
5. **写回**：通过 `patch_episode_script` 写回，**不得覆盖原始剧本文字**

## 边界

- **preserve 模式**：只能生成 video_prompt 字段，不得修改剧本原文
- **suggest_rewrite 模式**：改稿建议写入 `proposals/`，不写回正式剧本
- 产品镜头自动注入产品参考图（不需要手动在 prompt 里描述产品外观）
- 反面提示词从 prompt_library 的 negative_prompt 模板获取
