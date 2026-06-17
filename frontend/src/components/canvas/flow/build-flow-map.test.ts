import { describe, it, expect } from "vitest";
import { buildFlowMap } from "./build-flow-map";

describe("buildFlowMap", () => {
  it("空项目生成基础节点", () => {
    const { nodes, edges } = buildFlowMap({});
    expect(nodes.length).toBeGreaterThanOrEqual(5);
    const ids = nodes.map((n) => n.id);
    expect(ids).toContain("source");
    expect(ids).toContain("episodes");
    expect(ids).toContain("assets");
  });

  it("有 episodes 时生成 episode 节点", () => {
    const { nodes } = buildFlowMap({
      episodes: [
        { episode: 1, title: "第一集", script_file: "episode_1.json" },
        { episode: 2, title: "第二集" },
      ],
    });
    expect(nodes.find((n) => n.id === "ep-1")).toBeTruthy();
    expect(nodes.find((n) => n.id === "ep-2")).toBeTruthy();
  });

  it("有 video_units 时生成参考视频节点", () => {
    const { nodes } = buildFlowMap({
      scripts: { "episode_1.json": { video_units: [{ unit_id: "E1U01" }] } },
    });
    expect(nodes.find((n) => n.id === "ref-video")).toBeTruthy();
  });

  it("状态颜色计算正确", () => {
    const { nodes } = buildFlowMap({
      episodes: [{ episode: 1, title: "第一集", script_file: "episode_1.json" }],
      characters: { "主角": { character_sheet: "chars/主角.png" } },
    });
    const epNode = nodes.find((n) => n.id === "ep-1");
    expect(epNode!.style!.background).toBe("#22c55e");
    const srcNode = nodes.find((n) => n.id === "source");
    expect(srcNode!.style!.background).toBe("#22c55e");
  });

  it("无资产时资产节点为 idle 灰色", () => {
    const { nodes } = buildFlowMap({});
    const assetNode = nodes.find((n) => n.id === "assets");
    expect(assetNode!.style!.background).toBe("#4a4a5a");
  });

  // ── 详情字段 ──

  it("node.data.detail 包含 kind 和 targetPath", () => {
    const { nodes } = buildFlowMap({ episodes: [{ episode: 1, title: "测试" }] });
    const src = nodes.find((n) => n.id === "source")!;
    const d = src.data.detail as Record<string, unknown>;
    expect(d.kind).toBe("source");
    expect(d.targetPath).toBe("/source");

    const ep = nodes.find((n) => n.id === "ep-1")!;
    expect((ep.data.detail as Record<string, unknown>).targetPath).toBe("/episodes/1");
  });

  it("分集规划节点有 counts", () => {
    const { nodes } = buildFlowMap({
      episodes: [
        { episode: 1, script_file: "ep1.json" },
        { episode: 2 },
        { episode: 3 },
      ],
    });
    const ep = nodes.find((n) => n.id === "episodes")!;
    const c = (ep.data.detail as Record<string, unknown>).counts as Record<string, number>;
    expect(c.total).toBe(3);
    expect(c.scripted).toBe(1);
    expect(c.missing).toBe(2);
  });

  it("资产节点有 items", () => {
    const { nodes } = buildFlowMap({
      characters: { "A": { character_sheet: "a.png" }, "B": {} },
      scenes: { "S1": { scene_sheet: "s1.png" } },
    });
    const a = nodes.find((n) => n.id === "assets")!;
    const items = (a.data.detail as Record<string, unknown>).items as { label: string; ok: boolean }[];
    expect(items.length).toBeGreaterThanOrEqual(2);
  });

  it("视频生成节点无 targetPath（不提供生成按钮）", () => {
    const { nodes } = buildFlowMap({});
    const vg = nodes.find((n) => n.id === "video-gen")!;
    const d = vg.data.detail as Record<string, unknown>;
    expect(d.targetPath).toBeUndefined();
  });

  it("空 title 不会崩溃", () => {
    const { nodes } = buildFlowMap({ title: undefined });
    expect(nodes.length).toBeGreaterThan(0);
  });
});
