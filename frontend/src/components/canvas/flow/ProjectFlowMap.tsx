/** ProjectFlowMap — 只读流程地图，可视化项目当前状态。 */

import { useMemo, useCallback } from "react";
import { useTranslation } from "react-i18next";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  type Node,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import { useProjectsStore } from "@/stores/projects-store";
import { buildFlowMap, type FlowMapInput, type FlowStatus } from "./build-flow-map";

const STATUS_LABELS: Record<FlowStatus, string> = {
  idle: "未开始",
  active: "进行中",
  done: "已完成",
  warn: "需检查",
  blocked: "阻断",
};

export function ProjectFlowMap() {
  const { t } = useTranslation("dashboard");
  const project = useProjectsStore((s) => s.currentProjectData);

  const input: FlowMapInput = useMemo(() => ({
    title: project?.title,
    contentMode: project?.content_mode,
    episodes: project?.episodes?.map((e) => ({
      episode: e.episode, title: e.title, script_file: e.script_file,
    })),
    characters: project?.characters as Record<string, Record<string, unknown>> | undefined,
    scenes: project?.scenes as Record<string, Record<string, unknown>> | undefined,
    props: project?.props as Record<string, Record<string, unknown>> | undefined,
    products: project?.products as Record<string, Record<string, unknown>> | undefined,
    scripts: {},  // scripts data comes from currentScripts store — minimal impl for now
  }), [project]);

  const { nodes: rawNodes, edges } = useMemo(() => buildFlowMap(input), [input]);

  const nodes = useMemo(() => rawNodes.map((n) => ({
    ...n,
    data: {
      ...n.data,
      label: (
        <div>
          <div style={{ fontWeight: 600 }}>{typeof n.data.label === "string" ? n.data.label : ""}</div>
          {typeof n.data.sub === "string" && <div style={{ fontSize: 10, opacity: 0.7, marginTop: 2 }}>{n.data.sub}</div>}
        </div>
      ),
    },
  })), [rawNodes]);

  const onNodeClick = useCallback((_event: React.MouseEvent, node: Node) => {
    // 只跳转到已有页面，不触发生成
    const id = node.id;
    if (id === "source") window.location.hash = "#/app/projects/" + (project?.title || "") + "/source";
    else if (id === "assets") window.location.hash = "#/app/projects/" + (project?.title || "") + "/characters";
    else if (id.startsWith("ep-")) {
      const epNum = id.replace("ep-", "");
      window.location.hash = "#/app/projects/" + (project?.title || "") + "/episodes/" + epNum;
    }
  }, [project]);

  return (
    <div style={{ width: "100%", height: "100%", background: "oklch(0.14 0.010 260 / 0.95)" }}>
      <div style={{ padding: "8px 16px", borderBottom: "1px solid var(--color-hairline)", display: "flex", alignItems: "center", gap: 16, background: "oklch(0.18 0.010 265 / 0.6)" }}>
        <span style={{ fontWeight: 700, fontSize: 14, color: "var(--color-text)" }}>🗺️ {t("flow_map_title")}</span>
        <span style={{ fontSize: 11, color: "var(--color-text-3)" }}>{project?.title}</span>
        <span style={{ flex: 1 }} />
        <span style={{ fontSize: 10, color: "var(--color-text-4)" }}>只读 · 点击节点跳转</span>
      </div>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodesDraggable={false}
        nodesConnectable={false}
        edgesFocusable={false}
        onNodeClick={onNodeClick}
        fitView
        attributionPosition="bottom-right"
      >
        <Background color="oklch(0.25 0.01 260 / 0.3)" gap={20} />
        <Controls />
        <MiniMap
          nodeColor={(n) => {
            const s = (n.data as { status?: FlowStatus })?.status;
            if (s === "done") return "#22c55e";
            if (s === "active") return "#3b82f6";
            if (s === "warn") return "#f59e0b";
            if (s === "blocked") return "#ef4444";
            return "#4a4a5a";
          }}
        />
      </ReactFlow>
    </div>
  );
}
