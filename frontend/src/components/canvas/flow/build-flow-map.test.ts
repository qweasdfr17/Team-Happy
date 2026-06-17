import { describe, it, expect } from "vitest";
import { buildFlowMap } from "./build-flow-map";

describe("buildFlowMap", () => {
  it("空项目生成基础节点", () => {
    const { nodes, edges } = buildFlowMap({});
    expect(nodes.length).toBeGreaterThanOrEqual(5); // source, episodes, assets, prompts, preflight, video-gen
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
      episodes: [
        { episode: 1, title: "第一集", script_file: "episode_1.json" },
      ],
      characters: { "主角": { character_sheet: "chars/主角.png" } },
    });
    const epNode = nodes.find((n) => n.id === "ep-1");
    expect(epNode).toBeTruthy();
    expect(epNode!.style!.background).toBe("#22c55e"); // done
    const srcNode = nodes.find((n) => n.id === "source");
    expect(srcNode!.style!.background).toBe("#22c55e"); // done
  });

  it("无资产时资产节点为 idle 灰色", () => {
    const { nodes } = buildFlowMap({});
    const assetNode = nodes.find((n) => n.id === "assets");
    expect(assetNode!.style!.background).toBe("#4a4a5a"); // idle
  });
});
