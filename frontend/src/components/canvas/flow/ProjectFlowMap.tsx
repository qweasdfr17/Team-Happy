/** ProjectFlowMap — 只读流程地图，可视化项目当前状态。 */

import { useMemo, useCallback, useState } from "react";
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
import { buildFlowMap, type FlowMapInput, type FlowStatus, type FlowNodeDetail } from "./build-flow-map";
import { FlowNodeDetailsPanel } from "./FlowNodeDetailsPanel";

export function ProjectFlowMap() {
  const { t } = useTranslation("dashboard");
  const project = useProjectsStore((s) => s.currentProjectData);

  const input: FlowMapInput = useMemo(() => ({
    title: project?.title,
    contentMode: project?.content_mode,
    scriptPolicyMode: (project as unknown as Record<string, unknown> | null)?.script_policy
      ? (((project as unknown as Record<string, unknown>).script_policy as Record<string, unknown>)?.mode as string | undefined)
      : undefined,
    episodes: project?.episodes?.map((e) => ({
      episode: e.episode, title: e.title, script_file: e.script_file,
    })),
    characters: project?.characters as Record<string, Record<string, unknown>> | undefined,
    scenes: project?.scenes as Record<string, Record<string, unknown>> | undefined,
    props: project?.props as Record<string, Record<string, unknown>> | undefined,
    products: project?.products as Record<string, Record<string, unknown>> | undefined,
    scripts: {},
  }), [project]);

  const { nodes: rawNodes, edges } = useMemo(() => buildFlowMap(input), [input]);

  const nodes = useMemo(() => rawNodes.map((n) => ({
    ...n,
    data: {
      ...n.data,
      label: (
        <div>
          <div style={{ fontWeight: 600 }}>{(n.data as Record<string, unknown>).label as string || ""}</div>
          {((n.data as Record<string, unknown>).sub as string) && <div style={{ fontSize: 10, opacity: 0.7, marginTop: 2 }}>{(n.data as Record<string, unknown>).sub as string}</div>}
        </div>
      ),
    },
  })), [rawNodes]);

  const [selectedDetail, setSelectedDetail] = useState<FlowNodeDetail | null>(null);

  const onNodeClick = useCallback((_event: React.MouseEvent, node: Node) => {
    const detail = (node.data as Record<string, unknown>).detail as FlowNodeDetail | undefined;
    setSelectedDetail(detail || null);
  }, []);

  const onPaneClick = useCallback(() => setSelectedDetail(null), []);

  const handleNavigate = useCallback((path: string) => {
    const base = window.location.hash.replace(/^#/, "");
    const parts = base.split("/");
    const projIdx = parts.indexOf("app") + 2;
    const prefix = parts.slice(0, projIdx).join("/");
    window.location.hash = "#/" + prefix + path;
  }, []);

  return (
    <div style={{ width: "100%", height: "100%", display: "flex", background: "oklch(0.14 0.010 260 / 0.95)" }}>
      {/* Main flow area */}
      <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column" }}>
        <div style={{ padding: "8px 16px", borderBottom: "1px solid var(--color-hairline)", display: "flex", alignItems: "center", gap: 16, background: "oklch(0.18 0.010 265 / 0.6)" }}>
          <span style={{ fontWeight: 700, fontSize: 14, color: "var(--color-text)" }}>🗺️ {t("flow_map_title")}</span>
          <span style={{ fontSize: 11, color: "var(--color-text-3)" }}>{project?.title}</span>
          <span style={{ flex: 1 }} />
          <span style={{ fontSize: 10, color: "var(--color-text-4)" }}>{t("flow_readonly_hint")}</span>
        </div>
        <div style={{ flex: 1 }}>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            nodesDraggable={false}
            nodesConnectable={false}
            edgesFocusable={false}
            onNodeClick={onNodeClick}
            onPaneClick={onPaneClick}
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
      </div>

      {/* Detail panel */}
      {selectedDetail && (
        <FlowNodeDetailsPanel
          detail={selectedDetail}
          onClose={() => setSelectedDetail(null)}
          onNavigate={handleNavigate}
        />
      )}
    </div>
  );
}
