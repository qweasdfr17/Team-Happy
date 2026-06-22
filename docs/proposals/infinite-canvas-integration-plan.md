# AI 漫剧无限画布接入开发方案

## 1. 可行性结论

结论：可行，建议采用 `@xyflow/react` 作为新画布底座，不再使用 tldraw，也不建议引入 Vue Flow。

原因：

1. 当前项目是 React + Vite + TypeScript，前端依赖中已经存在 `@xyflow/react`，并且 `frontend/src/components/canvas/flow/ProjectFlowMap.tsx` 已经在使用 React Flow。
2. 用户提供的 RunningHub 技术说明本质上描述的是 Vue Flow 的交互架构：统一 pan/zoom transform 层、节点绝对坐标、SVG 贝塞尔连线、handle 连接点、自动平移、节点类型注册。React Flow 与 Vue Flow 属于同一生态方向，核心能力基本一致。
3. 项目已有完整工作台业务链路：项目数据、剧集脚本、参考生视频单元、提示词、引用资产、视频生成任务都已经有 API 和 store。新画布不需要重建业务系统，只需要做第二套空间化操作界面。
4. 之前移除 tldraw 后，项目已无 tldraw 残留，画布可以重新从干净入口接入，避免许可证、UI 风格和数据模型被旧方案绑定。

不可直接照搬 RunningHub 的部分：

1. RunningHub 使用 Vue Flow，当前项目不能引入 Vue 运行时做混合前端，否则复杂度和维护成本会明显上升。
2. RunningHub 的 `rh-image/rh-video/rh-ai/rh-text/group` 是它自己的业务节点，不能直接复用，只能复刻交互原则和视觉手感。
3. 当前项目的核心业务不是通用节点编排，而是漫剧生产流程，因此节点类型必须围绕“剧集、视频单元、镜头、角色、场景、道具、生成任务、Agent 操作”设计。

## 2. 目标定位

新画布不是独立玩具模块，而是工作台的第二操作界面。

目标：

1. 工作台修改的数据，进入画布后能同步显示。
2. 画布修改的数据，保存后能同步回工作台。
3. 用户既可以用列表/表单式工作台，也可以用空间化拖拽/连线式画布完成同一套漫剧制作流程。
4. 画布布局、节点坐标、缩放视角属于画布视图状态；提示词、引用资产、时长、视频生成任务属于业务数据，必须写回现有业务接口。

核心原则：

1. 业务数据单一真相：`project.json`、剧集脚本、reference video units、任务队列仍由现有后端和 store 管理。
2. 画布只额外持久化视图状态：节点位置、分组位置、视口、折叠状态、用户自定义布局。
3. 画布节点编辑必须调用现有业务 API，不允许只改画布本地状态。
4. 生成视频前必须复用现有引用同步逻辑，保证提示词框、引用资产、提交给上游的图片参考一致。

## 3. 推荐技术方案

### 3.1 画布底座

使用：

```ts
@xyflow/react
```

理由：

1. 已在项目中安装，减少新增依赖。
2. 与 RunningHub 使用的 Vue Flow 能力相近。
3. 支持自定义节点、连线、handle、拖拽、缩放、平移、MiniMap、Controls、Background、fitView。
4. 可通过 CSS 覆盖实现 RunningHub 风格的流畅交互：
   - viewport/transformation pane 使用 transform 矩阵。
   - 节点使用 translate 定位。
   - 连线使用 SVG path。
   - 通过 `will-change: transform`、短反馈动画、贝塞尔曲线实现顺滑手感。

### 3.2 不建议自研底层 pan/zoom

不建议从零实现 d3-zoom + 自绘 SVG + 自定义命中检测。

原因：

1. 初期开发量会明显上升。
2. 节点拖拽、连线、handle 命中、键盘操作、缩放适配、移动端手势、自动平移都需要重新踩坑。
3. 当前需求重点是业务画布，不是底层渲染引擎。

React Flow 足够承接第一版和中期版本。若后续节点规模达到数千级且性能不足，再考虑独立渲染层或 Canvas/WebGL 混合方案。

## 4. 画布信息架构

建议新增入口：

```text
/creative-canvas
```

中文导航名：

```text
创作画布
```

画布分为四层：

1. 顶部工具栏：刷新同步、保存布局、自动整理、视图切换、生成任务状态。
2. 无限画布区：节点、分组、连线、背景网格、MiniMap。
3. 右侧属性面板：根据选中节点显示提示词、引用资产、时长、任务、预检问题。
4. 上下文浮层：节点上的快捷操作，例如编辑提示词、添加引用、生成视频、打开工作台。

## 5. 节点类型设计

### 5.1 EpisodeNode 剧集节点

来源：

```ts
ProjectData.episodes[]
```

展示：

1. 第几集、标题。
2. 剧本状态。
3. 视频单元数量。
4. 完成度。

操作：

1. 打开工作台对应剧集。
2. 展开/折叠该集的视频单元。
3. 触发重新同步剧集数据。

### 5.2 VideoUnitNode 视频单元节点

来源：

```ts
ReferenceVideoUnit
```

展示：

1. `unit_id`。
2. 总时长。
3. shots 数量。
4. 引用资产数量。
5. 生成状态。
6. 提示词摘要。

操作：

1. 编辑提示词。
2. 编辑引用资产。
3. 修改时长。
4. 生成视频。
5. 打开工作台对应视频单元。

写回接口：

```ts
API.patchReferenceVideoUnit(projectName, episode, unitId, patch)
API.generateReferenceVideoUnit(projectName, episode, unitId)
```

### 5.3 ShotNode 镜头节点

第一版可以不单独展开成节点，只作为 `VideoUnitNode` 内部列表展示。

第二版再支持镜头级节点：

1. 单镜头时长。
2. 单镜头画面描述。
3. 单镜头动作/运镜。
4. 拖拽调整顺序。
5. 拆分/合并视频单元。

注意：Sundance 2.0 单镜头上限 15 秒，画布中任何镜头编辑都必须走同一套时长校验。

### 5.4 AssetNode 资产节点

资产类型：

1. 角色 `character`
2. 场景 `scene`
3. 道具 `prop`
4. 后续广告模式可加入产品 `product`

来源：

```ts
ProjectData.characters
ProjectData.scenes
ProjectData.props
ProjectData.products
```

展示：

1. 名称。
2. 类型。
3. 是否已有资产图。
4. 被哪些视频单元引用。

操作：

1. 打开资产详情。
2. 拖拽连接到视频单元，形成引用关系。
3. 从视频单元移除引用。

写回规则：

资产节点与视频单元节点建立连接时，不只保存 edge，还必须写回：

```ts
ReferenceVideoUnit.references
ReferenceVideoUnit.shots[].text 中的 @引用段落
```

推荐复用：

```ts
deriveReferencesFromPrompt
syncPromptReferenceSection
appendReferenceMention
removeReferenceFromPrompt
```

### 5.5 AgentNode 智能体操作节点

第二阶段引入。

用途：

1. 重新调整剧本。
2. 剧本改分镜。
3. 写提示词。
4. 重新拆分视频单元。

要求：

所有需要用户确认的 Agent 行为，必须进入现有 Agent 会话框并留下记录，不能只在画布中静默执行。

## 6. 数据同步设计

### 6.1 业务数据来源

画布页面加载时读取：

1. `useProjectsStore.currentProjectData`
2. `useProjectsStore.currentScripts`
3. `useReferenceVideoStore.unitsByEpisode`
4. 任务队列 store

如果缺少当前剧集视频单元，则调用：

```ts
useReferenceVideoStore.getState().loadUnits(projectName, episode)
```

### 6.2 画布布局数据

建议新增后端接口，但只保存视图状态，不保存业务内容。

接口：

```text
GET /api/v1/projects/{project_name}/creative-canvas-layouts/main
PUT /api/v1/projects/{project_name}/creative-canvas-layouts/main
```

保存路径建议：

```text
projects/{project}/canvas_layouts/creative-main.json
```

数据结构：

```ts
export interface CreativeCanvasLayout {
  version: 1;
  viewport?: {
    x: number;
    y: number;
    zoom: number;
  };
  nodes: Record<string, {
    x: number;
    y: number;
    w?: number;
    h?: number;
    collapsed?: boolean;
    groupId?: string | null;
  }>;
  groups?: Record<string, {
    title: string;
    x: number;
    y: number;
    w: number;
    h: number;
    collapsed?: boolean;
  }>;
}
```

节点 id 规范：

```text
episode:{episode}
unit:{episode}:{unit_id}
asset:character:{name}
asset:scene:{name}
asset:prop:{name}
agent:{operation}
```

### 6.3 写回规则

画布操作不能直接修改本地对象后结束，必须调用业务写回接口。

典型操作：

| 画布操作 | 写回目标 |
| --- | --- |
| 编辑视频单元提示词 | `patchReferenceVideoUnit(prompt, references)` |
| 添加/删除资产引用 | `patchReferenceVideoUnit(prompt, references)` |
| 拖资产节点连接到视频单元 | 同步 prompt @引用 + references |
| 修改视频单元时长 | `patchReferenceVideoUnit(duration_seconds)` |
| 点击生成视频 | 若提示词脏，先保存，再 `generateReferenceVideoUnit` |
| 打开工作台 | 路由跳转 + `triggerScrollTo(reference_unit)` |

## 7. 文件结构建议

```text
frontend/src/components/canvas/creative/
  CreativeCanvasPage.tsx
  CreativeCanvasToolbar.tsx
  CreativeCanvasViewport.tsx
  CreativeCanvasDetailsPanel.tsx
  nodes/
    EpisodeNode.tsx
    VideoUnitNode.tsx
    AssetNode.tsx
    AgentNode.tsx
  edges/
    CreativeBezierEdge.tsx
  model/
    build-creative-canvas.ts
    creative-canvas-types.ts
    use-creative-canvas-model.ts
    use-creative-canvas-layout.ts
    creative-canvas-actions.ts
  styles/
    creative-canvas.css
```

后端：

```text
server/routers/creative_canvas_layouts.py
tests/server/test_creative_canvas_layouts_router.py
```

类型：

```text
frontend/src/types/creative-canvas.ts
```

## 8. React Flow 接入要点

### 8.1 基础组件

```tsx
<ReactFlow
  nodes={nodes}
  edges={edges}
  nodeTypes={nodeTypes}
  edgeTypes={edgeTypes}
  onNodesChange={onNodesChange}
  onEdgesChange={onEdgesChange}
  onConnect={onConnect}
  panOnDrag
  zoomOnScroll
  zoomOnPinch
  nodesDraggable
  nodesConnectable
  fitView={false}
>
  <Background gap={24} />
  <Controls />
  <MiniMap />
</ReactFlow>
```

### 8.2 RunningHub 风格性能 CSS

```css
.creative-canvas .react-flow__viewport {
  transform-origin: 0 0;
  will-change: transform;
  transition: transform 0s;
}

.creative-canvas .react-flow__node {
  will-change: transform;
  transition: transform 0s;
}

.creative-canvas .react-flow__edge-path {
  vector-effect: non-scaling-stroke;
}

.creative-canvas .react-flow__handle {
  width: 10px;
  height: 10px;
  border-radius: 999px;
  border: 2px solid var(--color-hairline);
  background: var(--color-bg);
  transition: border-color 160ms, background 160ms, transform 160ms;
}
```

### 8.3 三阶贝塞尔连线

React Flow 默认 smoothstep 已经可用，但为了贴近 RunningHub，可以做自定义 edge：

```ts
function bezierPath(sx: number, sy: number, tx: number, ty: number): string {
  const mx = (sx + tx) / 2;
  return `M${sx},${sy} C${mx},${sy} ${mx},${ty} ${tx},${ty}`;
}
```

## 9. 开发阶段规划

### 第一阶段：可读可跳转画布

目标：

1. 增加 `/creative-canvas` 页面和左侧入口“创作画布”。
2. 基于现有项目数据生成 EpisodeNode、VideoUnitNode、AssetNode。
3. 支持 pan/zoom、拖动节点、自动保存布局。
4. 点击视频单元节点，右侧展示详情。
5. 支持从画布跳回工作台对应视频单元。

验收：

1. 工作台已有视频单元能在画布中显示。
2. 拖动节点刷新后位置不丢。
3. 画布不写业务数据，只写布局数据。

### 第二阶段：提示词与引用双向编辑

目标：

1. 右侧面板可编辑视频单元提示词。
2. 可添加/删除引用资产。
3. 资产节点拖线到视频单元后，自动写入引用。
4. 保存后工作台同步更新。
5. 工作台更新后刷新画布能同步显示。

验收：

1. 画布保存提示词后，工作台提示词一致。
2. 画布添加引用后，工作台引用资产面板一致。
3. 生成视频前实际提交的 references 与画布/工作台显示一致。

### 第三阶段：视频生成与任务状态

目标：

1. 画布中可直接点击生成视频。
2. 若提示词未保存，先保存再入队。
3. 节点显示 running/ready/failed 状态。
4. 任务完成后自动刷新节点预览。

验收：

1. 画布触发生成与工作台触发生成走同一后端接口。
2. 不出现“画布显示已引用但生成未上传引用资产”的问题。

### 第四阶段：镜头级空间化操作

目标：

1. 视频单元可展开为 ShotNode。
2. 支持镜头拆分、合并、调整顺序。
3. 所有镜头时长强制不超过 15 秒。
4. 拆分后自动生成/刷新对应提示词。

验收：

1. 任意保存后的 shot duration <= 15。
2. 拆分后叙事顺序不乱。
3. 工作台视频单元列表与画布一致。

### 第五阶段：Agent 节点与会话确认

目标：

1. 加入“调整剧本、剧本改分镜、写提示词、重新拆分” Agent 操作节点。
2. 节点触发后进入现有 Agent 会话流程。
3. 所有需要用户确认的内容必须在会话框里出现。

验收：

1. 子 Agent 需要确认时，用户能在会话中看到并确认。
2. 画布操作不会绕过会话记录。

## 10. 主要风险与处理

### 风险 1：画布状态与工作台状态不一致

等级：严重。

处理：

1. 业务数据只通过现有 API 写回。
2. 保存成功后刷新 store。
3. 画布节点由 store 重新派生，不维护第二份业务副本。

### 风险 2：引用资产显示一致但生成提交不一致

等级：严重。

处理：

1. 所有提示词保存都走 `deriveReferencesFromPrompt + syncPromptReferenceSection`。
2. 生成视频前检查 dirty prompt，未保存则先 patch。
3. 生成按钮只调用现有 `generateReferenceVideoUnit`。

### 风险 3：节点数量增多后性能下降

等级：一般。

处理：

1. 第一版只展开剧集、视频单元和资产，不默认展开 shot。
2. 超过一定节点数时折叠集群。
3. 节点卡片内容做摘要，不在节点内渲染大文本编辑器。
4. 编辑器放右侧详情面板。

### 风险 4：React Flow 默认 UI 不符合预期

等级：一般。

处理：

1. 使用完全自定义 nodeTypes。
2. 用项目自己的 CSS token 做视觉。
3. React Flow 只作为底层交互与连线引擎。

### 风险 5：布局文件污染业务交付

等级：提示。

处理：

1. 布局文件放 `canvas_layouts/`。
2. 布局缺失时自动生成默认布局。
3. 打包分发时可选择保留或忽略布局文件，不影响业务数据。

## 11. 测试计划

前端单元测试：

1. `build-creative-canvas.test.ts`
   - project + scripts + units 能生成正确节点。
   - 引用资产能生成 asset nodes。
   - 缺布局时能生成默认位置。

2. `creative-canvas-actions.test.ts`
   - 添加引用会同步 prompt 和 references。
   - 删除引用会同步 prompt 和 references。
   - 生成视频前 dirty prompt 会先保存。

3. `CreativeCanvasPage.test.tsx`
   - 路由能渲染。
   - 选中节点显示详情。
   - 点击打开工作台能触发跳转。

后端测试：

1. `test_creative_canvas_layouts_router.py`
   - 缺布局返回空布局。
   - PUT 后 GET 能读回。
   - 非法 project name 被拒绝。
   - 非法 layout id 被拒绝。

手工验收：

1. 在工作台改提示词，刷新画布后同步。
2. 在画布改提示词，回工作台后同步。
3. 在画布添加引用，工作台引用资产面板同步。
4. 从画布生成视频，后端任务包含正确引用资产。
5. 拖动画布 100 个节点时无明显卡顿。

## 12. 建议首个开发切片

建议第一步只做“可读可跳转 + 布局保存”的最小闭环：

1. 新增 `/creative-canvas` 路由和入口。
2. 新增 `CreativeCanvasPage`。
3. 用 `@xyflow/react` 渲染 EpisodeNode、VideoUnitNode、AssetNode。
4. 新增 `build-creative-canvas.ts` 纯函数。
5. 新增布局保存 API。
6. 支持点击视频单元跳回工作台。

这个切片风险最低，不涉及提示词写回，也能尽快验证新画布底座手感是否符合预期。
