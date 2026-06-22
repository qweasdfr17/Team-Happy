import { PresetIcon } from "@/components/agent/PresetIcon";
import { PROVIDER_DISPLAY_NAMES_ZH } from "@/utils/model-display";

export const PROVIDER_NAMES: Record<string, string> = PROVIDER_DISPLAY_NAMES_ZH;

const PROVIDER_ICON_KEYS: Record<string, string> = {
  ark: "Volcengine",
  dashscope: "Bailian",
  minimax: "Minimax",
  openai: "OpenAI",
  vidu: "Vidu",
};

function providerIconKey(providerId: string): string | null {
  if (providerId === "gemini-vertex") return "VertexAI";
  if (providerId.startsWith("gemini")) return "Gemini";
  if (providerId.startsWith("grok")) return "Grok";
  return PROVIDER_ICON_KEYS[providerId] ?? null;
}

/**
 * 根据 providerId 渲染对应供应商图标。
 * 支持 gemini-aistudio、gemini-vertex、grok、ark、dashscope、minimax、openai、vidu，其余显示首字母。
 */
export function ProviderIcon({
  providerId,
  className,
  size = 24,
}: {
  providerId: string;
  className?: string;
  size?: number;
}) {
  const cls = className ?? "h-6 w-6";
  const iconKey = providerIconKey(providerId);
  if (iconKey) return <PresetIcon iconKey={iconKey} size={size} className={cls} />;
  return (
    <span
      className={`inline-flex items-center justify-center rounded border border-hairline-soft bg-bg-grad-b/70 text-xs font-bold uppercase text-text-2 ${cls}`}
    >
      {providerId[0]}
    </span>
  );
}
