/** FlowNodeDetailsPanel — 流程地图节点详情面板（只读）。 */

import { useTranslation } from "react-i18next";
import { ExternalLink, X } from "lucide-react";
import type { FlowNodeDetail } from "./build-flow-map";

interface Props {
  detail: FlowNodeDetail;
  onClose: () => void;
  onNavigate: (path: string) => void;
}

export function FlowNodeDetailsPanel({ detail, onClose, onNavigate }: Props) {
  const { t } = useTranslation("dashboard");

  const navigate = (path: string) => {
    const base = window.location.hash.replace(/^#/, "");
    const parts = base.split("/");
    const projIdx = parts.indexOf("app") + 2; // /app/projects/{name}
    const prefix = parts.slice(0, projIdx).join("/");
    window.location.hash = "#/" + prefix + path;
  };

  return (
    <div
      style={{
        width: 340, height: "100%", overflowY: "auto",
        background: "oklch(0.18 0.010 265 / 0.95)",
        borderLeft: "1px solid var(--color-hairline)",
        padding: "16px",
        color: "var(--color-text)",
        fontSize: 13,
      }}
    >
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
        <span style={{ fontWeight: 700, fontSize: 15 }}>{detail.title}</span>
        <button onClick={onClose} style={{ background: "none", border: "none", color: "var(--color-text-3)", cursor: "pointer" }} aria-label={t("common:close")}>
          <X size={16} />
        </button>
      </div>

      {/* Status */}
      <div style={{ marginBottom: 12 }}>
        <span style={{ fontSize: 11, color: "var(--color-text-4)", textTransform: "uppercase" }}>状态</span>
        <span style={{
          display: "inline-block", marginLeft: 8, padding: "2px 8px", borderRadius: 4, fontSize: 12,
          background: detail.status === "done" ? "#22c55e" : detail.status === "active" ? "#3b82f6" : detail.status === "warn" ? "#f59e0b" : detail.status === "blocked" ? "#ef4444" : "#4a4a5a",
          color: "#fff",
        }}>
          {detail.status === "done" ? t("flow_status_done") : detail.status === "active" ? t("flow_status_active") : detail.status === "warn" ? t("flow_status_warn") : detail.status === "blocked" ? t("flow_status_blocked") : t("flow_status_idle")}
        </span>
      </div>

      {/* Counts */}
      {detail.counts && Object.keys(detail.counts).length > 0 && (
        <div style={{ marginBottom: 12 }}>
          <div style={{ fontSize: 11, color: "var(--color-text-4)", textTransform: "uppercase", marginBottom: 6 }}>{t("flow_detail_counts")}</div>
          {Object.entries(detail.counts).map(([k, v]) => (
            <div key={k} style={{ fontSize: 12, padding: "2px 0", color: "var(--color-text-2)" }}>
              {t(`flow_count_${k}`, k)}: <strong>{v}</strong>
            </div>
          ))}
        </div>
      )}

      {/* Items checklist */}
      {detail.items && detail.items.length > 0 && (
        <div style={{ marginBottom: 12 }}>
          <div style={{ fontSize: 11, color: "var(--color-text-4)", textTransform: "uppercase", marginBottom: 6 }}>{t("flow_detail_items")}</div>
          {detail.items.map((item, i) => (
            <div key={i} style={{ fontSize: 12, padding: "2px 0", color: item.ok ? "#22c55e" : "#f59e0b" }}>
              {item.ok ? "✅" : "⚠️"} {item.label}
            </div>
          ))}
        </div>
      )}

      {/* Kind-specific info */}
      {detail.kind === "source" && (
        <div style={{ fontSize: 12, color: "var(--color-text-3)", marginBottom: 12 }}>
          {t("flow_source_note")}
        </div>
      )}
      {detail.kind === "preflight" && (
        <div style={{ fontSize: 12, color: "var(--color-text-3)", marginBottom: 12 }}>
          {t("flow_preflight_placeholder")}
        </div>
      )}
      {detail.kind === "video-gen" && (
        <div style={{ fontSize: 12, color: "var(--color-text-3)", marginBottom: 12 }}>
          {t("flow_video_gen_note")}
        </div>
      )}

      {/* Navigate button */}
      {detail.targetPath && (
        <button
          onClick={() => { navigate(detail.targetPath!); }}
          style={{
            display: "inline-flex", alignItems: "center", gap: 6,
            padding: "6px 14px", borderRadius: 6, border: "1px solid var(--color-hairline)",
            background: "oklch(0.22 0.011 265 / 0.6)", color: "var(--color-text-2)",
            cursor: "pointer", fontSize: 12, fontWeight: 600,
          }}
        >
          <ExternalLink size={14} />
          {t("flow_go_to")}
        </button>
      )}
    </div>
  );
}
