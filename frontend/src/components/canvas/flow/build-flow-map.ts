/** build-flow-map — 从 projectData + scripts 构建 React Flow nodes/edges。
 *
 * 纯函数：不访问 DOM / 网络 / 文件系统。
 */

import type { Node, Edge } from "@xyflow/react";

export interface FlowMapInput {
  title?: string;
  contentMode?: string;
  episodes?: { episode: number; title?: string; script_file?: string }[];
  characters?: Record<string, Record<string, unknown>>;
  scenes?: Record<string, Record<string, unknown>>;
  props?: Record<string, Record<string, unknown>>;
  products?: Record<string, Record<string, unknown>>;
  scripts?: Record<string, { shots?: unknown[]; video_units?: unknown[]; reference_units?: unknown[] }>;
}

export type FlowStatus = "idle" | "active" | "done" | "warn" | "blocked";

function statusColor(s: FlowStatus): string {
  switch (s) {
    case "idle": return "#4a4a5a";
    case "active": return "#3b82f6";
    case "done": return "#22c55e";
    case "warn": return "#f59e0b";
    case "blocked": return "#ef4444";
  }
}

function _shotCount(scripts: FlowMapInput["scripts"]): number {
  if (!scripts) return 0;
  let n = 0;
  for (const s of Object.values(scripts)) {
    if (Array.isArray(s.shots)) n += s.shots.length;
  }
  return n;
}

function _unitCount(scripts: FlowMapInput["scripts"]): number {
  if (!scripts) return 0;
  let n = 0;
  for (const s of Object.values(scripts)) {
    if (Array.isArray(s.video_units)) n += s.video_units.length;
    if (Array.isArray(s.reference_units)) n += s.reference_units.length;
  }
  return n;
}

function _hasSheet(items: Record<string, Record<string, unknown>> | undefined, key: string): number {
  if (!items) return 0;
  let n = 0;
  for (const v of Object.values(items)) {
    if (typeof v[key] === "string" && v[key]) n++;
  }
  return n;
}

function _hasProductImages(products: FlowMapInput["products"]): number {
  if (!products) return 0;
  let n = 0;
  for (const p of Object.values(products)) {
    if (typeof p.product_sheet === "string" && p.product_sheet) n++;
    else if (Array.isArray(p.reference_images) && p.reference_images.length > 0) n++;
  }
  return n;
}

export function buildFlowMap(input: FlowMapInput): { nodes: Node[]; edges: Edge[] } {
  const nodes: Node[] = [];
  const edges: Edge[] = [];
  const epCount = input.episodes?.length ?? 0;
  const scriptedCount = input.episodes?.filter((e) => e.script_file).length ?? 0;
  const shotCount = _shotCount(input.scripts);
  const unitCount = _unitCount(input.scripts);
  const charCount = Object.keys(input.characters ?? {}).length;
  const sceneCount = Object.keys(input.scenes ?? {}).length;
  const propCount = Object.keys(input.props ?? {}).length;
  const prodCount = Object.keys(input.products ?? {}).length;
  const charSheet = _hasSheet(input.characters, "character_sheet");
  const sceneSheet = _hasSheet(input.scenes, "scene_sheet");
  const propSheet = _hasSheet(input.props, "prop_sheet");
  const prodReady = _hasProductImages(input.products);

  const Y_STEP = 80;
  const CENTER_X = 400;
  const RIGHT_X = 700;
  const LEFT_X = 100;

  // ── 原始剧本 ──
  nodes.push({
    id: "source", type: "default",
    position: { x: CENTER_X, y: 40 },
    data: { label: `📄 原始剧本`, status: "done" as FlowStatus, sub: input.title || "" },
    style: { background: statusColor("done"), color: "#fff", border: "none", borderRadius: 8, padding: "10px 16px", fontSize: 13, fontWeight: 600 },
  });

  // ── 分集规划 ──
  const epStatus: FlowStatus = epCount > 0 ? (scriptedCount >= epCount ? "done" : "active") : "idle";
  nodes.push({
    id: "episodes", type: "default",
    position: { x: CENTER_X, y: 40 + Y_STEP },
    data: { label: `📋 分集规划`, status: epStatus, sub: epCount > 0 ? `${scriptedCount}/${epCount} 集已生成剧本` : "未开始" },
    style: { background: statusColor(epStatus), color: "#fff", border: "none", borderRadius: 8, padding: "10px 16px", fontSize: 13, fontWeight: 600 },
  });
  if (epCount > 0) edges.push({ id: "e-source-ep", source: "source", target: "episodes", animated: true });

  let epY = 40 + 2 * Y_STEP;
  for (const ep of (input.episodes ?? [])) {
    const hasScript = !!ep.script_file;
    nodes.push({
      id: `ep-${ep.episode}`, type: "default",
      position: { x: CENTER_X, y: epY },
      data: { label: `🎬 第${ep.episode}集`, status: hasScript ? "done" : "active" as FlowStatus, sub: ep.title || "" },
      style: { background: statusColor(hasScript ? "done" : "active"), color: "#fff", border: "none", borderRadius: 8, padding: "10px 16px", fontSize: 13, fontWeight: 600 },
    });
    edges.push({ id: `e-ep-${ep.episode}`, source: "episodes", target: `ep-${ep.episode}` });
    epY += Y_STEP;
  }

  // ── 资产库 ──
  const allSheets = charSheet + sceneSheet + propSheet + prodReady;
  const allAssets = charCount + sceneCount + propCount + prodCount;
  const assetStatus: FlowStatus = allAssets === 0 ? "idle" : allSheets >= allAssets ? "done" : allSheets > 0 ? "active" : "warn";
  nodes.push({
    id: "assets", type: "default",
    position: { x: LEFT_X, y: 40 + Y_STEP },
    data: {
      label: `🎭 资产库`, status: assetStatus,
      sub: `角色${charSheet}/${charCount} 场景${sceneSheet}/${sceneCount} 道具${propSheet}/${propCount} 产品${prodReady}/${prodCount}`,
    },
    style: { background: statusColor(assetStatus), color: "#fff", border: "none", borderRadius: 8, padding: "10px 16px", fontSize: 12, fontWeight: 600 },
  });
  edges.push({ id: "e-source-assets", source: "source", target: "assets" });

  // ── 提示词 / shots ──
  const shotStatus: FlowStatus = shotCount > 0 ? "done" : unitCount > 0 ? "active" : "idle";
  nodes.push({
    id: "prompts", type: "default",
    position: { x: RIGHT_X, y: 40 + Y_STEP },
    data: { label: `✏️ 提示词生成`, status: shotStatus, sub: shotCount > 0 ? `${shotCount} 镜头` : unitCount > 0 ? `${unitCount} units` : "未开始" },
    style: { background: statusColor(shotStatus), color: "#fff", border: "none", borderRadius: 8, padding: "10px 16px", fontSize: 13, fontWeight: 600 },
  });
  edges.push({ id: "e-source-prompts", source: "source", target: "prompts" });

  // ── 参考生视频 ──
  if (unitCount > 0) {
    nodes.push({
      id: "ref-video", type: "default",
      position: { x: RIGHT_X, y: 40 + 2 * Y_STEP },
      data: { label: `🎥 参考生视频`, status: "active" as FlowStatus, sub: `${unitCount} units` },
      style: { background: statusColor("active"), color: "#fff", border: "none", borderRadius: 8, padding: "10px 16px", fontSize: 13, fontWeight: 600 },
    });
    edges.push({ id: "e-prompts-ref", source: "prompts", target: "ref-video" });
  }

  // ── 预检 ──
  nodes.push({
    id: "preflight", type: "default",
    position: { x: RIGHT_X, y: 40 + (unitCount > 0 ? 3 : 2) * Y_STEP },
    data: { label: `🔍 预检`, status: "idle" as FlowStatus, sub: "生成前检查资产引用" },
    style: { background: statusColor("idle"), color: "#fff", border: "none", borderRadius: 8, padding: "10px 16px", fontSize: 13, fontWeight: 600 },
  });
  edges.push({ id: "e-prompts-preflight", source: unitCount > 0 ? "ref-video" : "prompts", target: "preflight" });

  // ── 视频生成 ──
  nodes.push({
    id: "video-gen", type: "default",
    position: { x: RIGHT_X, y: 40 + (unitCount > 0 ? 4 : 3) * Y_STEP },
    data: { label: `🚀 视频生成`, status: "idle" as FlowStatus, sub: "待确认后生成" },
    style: { background: statusColor("idle"), color: "#fff", border: "none", borderRadius: 8, padding: "10px 16px", fontSize: 13, fontWeight: 600 },
  });
  edges.push({ id: "e-preflight-video", source: "preflight", target: "video-gen" });

  return { nodes, edges };
}
