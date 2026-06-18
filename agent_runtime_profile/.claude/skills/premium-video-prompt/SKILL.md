---
name: premium-video-prompt
description: 精品视频提示词写作方法论。从大量实战提示词中提炼的九段式模板、时间颗粒度、镜头术语、情绪表演、光影设计、音效设计等全套技法。结合 context_pack + 资产引用 + prompt_library 生成高质量 video_prompt。当用户需要写视频生成提示词时使用。触发词：写提示词、视频提示词、AI视频、运镜、分镜、电影感。
user-invocable: true
---

# 精品视频提示词生成器

本 skill 是正式 video_prompt 生成器，集成完整的视频提示词写作方法论。

## ⚠️ 最高优先级：只写提示词，不生成视频

- 本 skill 只生成/更新 video prompt，**不生成视频**。
- reference_video 模式下，必须把结果写入 video_unit prompt（WebUI 红框）。
- 必须调用 `mcp__arcreel__patch_reference_video_unit_prompt` 写入。
- **禁止**调用 `generate_video_*` 系列工具。
- 完成后回复用户：提示词已写入红框，请在页面审核，确认后再生成视频。

## ⚠️ script_policy 约束

开始前检查 `project.json` 的 `script_policy.mode`：
- **preserve**：只能基于原文生成 video_prompt，原文不可改写。image_prompt 和 video_prompt 是视觉补充
- **suggest_rewrite**：改稿建议写入 `proposals/`
- 生成的 video_prompt 不得覆盖原始剧本文字

## ⚠️ 图片引用声明规则

- 【图片引用声明】只负责资产绑定：`图片N：资产名`。
- **禁止**在图片声明中写角色外观参考、场景环境参考、道具外观参考、括号说明、角色长相、服装、环境细节。
- 资产描述只能写到后面的【场景设计】或【切片段】里。
- 按实际 references 数量输出图片1-N，不补不存在的编号，不固定必须4张。

## 工作流

1. **读取完整上下文（禁止只读摘要）**：
   - 必须读取 `scripts/episode_N.json` 的 **完整 video_units / shots**（当前 unit 的所有镜头原文、text、image_prompt、video_prompt）
   - 必须读取 `project.json` 中的 **characters / scenes / props / products** 全量资产（含 `voice_style` / `voice_reference_audio`，若角色有声音参考则生成时可感知）
   - context_pack 是辅助摘要，**不能替代**上述原文读取
   - **禁止**只根据 episode outline / 分集剧情摘要生成精品提示词
2. **查 prompt_library**：根据 style / 镜头类型取 1-3 条相关模板
3. **逐镜头生成**：reference_video 优先套用 `references/9-section-template.md`，再运用下方方法论补足细节
   - 保留当前 unit 原有的角色/场景/道具引用关系
   - 图片声明中的资产名必须来自 project.json 已注册资产
4. **写回**：reference_video 必须调用 `mcp__arcreel__patch_reference_video_unit_prompt` 写入红框
   - **必须传递 `references` 参数**：按图片1-N 顺序写出 `[{type, name}]` 列表
   - 如果忘记传递 references，工具会自动从 prompt 文本中的"图片N：资产名"推断并补全

---

# 视频提示词写作方法论

把"感觉"翻译成"参数"。不写"紧张氛围"，写"浅景深+手持晃动+呼吸声渐重+冷蓝侧光+阴影吞噬"。

---

## 一、成品提示词结构模板

reference_video unit prompt 必须优先使用 `references/9-section-template.md` 作为输出结构。

核心板块顺序：

1. 【图片引用声明】图片1/图片2/图片3/图片4分别绑定角色、场景、道具或产品。
2. 【全局视频要求】风格、帧率、画幅、无字幕、无音乐、废帧缓冲等全局规则。
3. 【场景设计】场景、时间、光线、陈设、空间氛围。
4. 【目标情绪】该 unit 的情绪曲线。
5. 【片段说明】用一句话列出每个切片段的目的。
6. 【切片段1-N】每段包含画面、运镜、对白、配音/音效。
7. 【负面约束】统一列出禁止项。

图片引用必须使用干净写法：`图片1`、`图片2`、`图片3`、`图片4`。禁止输出 `I图片1`、`!图片2`、`#图片1`、`2图片4` 等污染符号。

---

## 二、时间颗粒度：秒级拆解

- 每条分镜标注精确时间范围（如 0s~4s）
- 秒内可细分关键动作节点
- 情绪转折卡在具体秒数
- 动作要有先后因果关系

---

## 三、镜头语言术语表

| 类别 | 术语 |
|------|------|
| 景别 | 特写/近景/中景/全景/航拍/OTS过肩镜头 |
| 运镜 | 固定机位/手持跟拍/环绕轨道/推拉/摇移/whip pan/rack focus |
| 构图 | 居中对称/三分法/对角线/前景遮挡框景/低机位仰拍 |
| 光学 | 浅景深T1.4/anamorphic宽银幕/长焦压缩/50-85mm |

---

## 四、视觉DNA锁定

两种方法：首帧约束（严格匹配参考图）或关键词锚点（全片重复同套风格词）

---

## 五、动作物理逻辑

写力的传导路径，每个动作有原因和结果。

---

## 六、情绪表演：肌肉时间线

按秒拆解：眼眶→嘴角→鼻翼→肩膀→声音→崩溃，加入呼吸变化和声音质感。

---

## 七、光影设计

### 光影描述公式
```
[光源方向+时间/色温] → [光质：硬/柔/半硬] → [阴影特征] → [空气介质] → [色调倾向]
```

### 光质三态
- 硬光：锐利、高对比度、阴影清晰
- 柔光：奶油般、羽化、包覆式
- 半硬光：清晰可辨但略有羽化

### 六大经典打光
伦勃朗光/蝴蝶光/侧光/逆光剪影/顶光/底光

### 光影暗线叙事
设计一条贯穿全片的光影变化暗线，跟着人物情绪和剧情节奏走。

---

## 八、负面约束武器库

质感/运动/光影/空间/生命感/后期瑕疵/风格红线/结构层面 —— 参考 `prompt_library` 的 `negative_prompt` 分类。

---

## 九、分镜计秒与格式规范

- 每个分镜独立从 0s 重新计秒
- 分镜开头声明：`不要背景音乐，不要字幕，仅保留音效和环境音`
- 资产槽嵌入正文，参考图散落跟随台词/动作
- 物理层声明：自然肤色、真实纹理、胶片颗粒、真实光影

---

## 接入 ArcReel 工作流

1. **输入来源（必须完整读取）**：
   - `scripts/episode_N.json` → `video_units[].shots[]`（当前 unit 的完整镜头列表，含 text/image_prompt/video_prompt）
   - `project.json` → characters / scenes / props / products（全量资产，含 voice_style / voice_reference_audio）
   - context_pack style_bible + shot_intent_map 作为辅助背景
   - **禁止**仅使用 episode outline / 剧情摘要替代原文
2. **资产引用**：角色/场景/道具/产品 @mention + sheet 图。声音参考（voice_reference_audio）在上下文中可见，生成时可感知角色配音风格
3. **prompt_library**：检索 video_prompt / negative_prompt 模板
4. **输出目标**：`video_prompt` 字段或 reference_video unit prompt
5. **写回**：reference_video 调用 `mcp__arcreel__patch_reference_video_unit_prompt`，**必须同时传递 `references` 参数**；storyboard/grid 调用 `mcp__arcreel__patch_episode_script`。原文不动

## 参考资料

- **[references/9-section-template.md](references/9-section-template.md)** — reference_video 成品提示词主模板，必须优先使用
