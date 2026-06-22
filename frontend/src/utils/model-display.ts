const CUSTOM_PREFIX = "custom-";

export const PROVIDER_DISPLAY_NAMES_ZH: Record<string, string> = {
  "gemini-aistudio": "谷歌人工智能工作室",
  "gemini-vertex": "谷歌云顶点平台",
  gemini: "谷歌双子座",
  ark: "火山方舟",
  dashscope: "阿里百炼",
  minimax: "MiniMax 海螺",
  kling: "可灵",
  grok: "xAI 格洛克",
  openai: "开放人工智能",
  vidu: "生数科技 Vidu",
};

const PROVIDER_NAME_ALIASES: Record<string, string> = {
  "ai studio": "谷歌人工智能工作室",
  "gemini ai studio": "谷歌人工智能工作室",
  "google gemini": "谷歌双子座",
  gemini: "谷歌双子座",
  "vertex ai": "谷歌云顶点平台",
  ark: "火山方舟",
  volcengine: "火山引擎",
  dashscope: "阿里百炼",
  bailian: "阿里百炼",
  openai: "开放人工智能",
  vidu: "生数科技 Vidu",
};

const EXACT_MODEL_NAMES: Record<string, string> = {
  "veo-3": "谷歌视频 3",
  "veo-3.1-generate-preview": "谷歌视频 3.1 预览版",
  "veo-3.1-generate-001": "谷歌视频 3.1",
  "veo-2": "谷歌视频 2",
  "imagen-4": "谷歌图像 4",
  "imagen-4-ultra": "谷歌图像 4 超清版",
  "imagen-3": "谷歌图像 3",
  "nano-banana": "纳米香蕉图像",
  "gemini-2.5-pro": "谷歌双子座 2.5 专业版",
  "gemini-2.5-flash": "谷歌双子座 2.5 快速版",
  "gemini-2.0-flash": "谷歌双子座 2.0 快速版",
  "gpt-4o": "开放人工智能 GPT-4o",
  "gpt-4o-mini": "开放人工智能 GPT-4o 轻量版",
  "gpt-4.1": "开放人工智能 GPT-4.1",
  "gpt-4.1-mini": "开放人工智能 GPT-4.1 轻量版",
  o3: "开放人工智能 o3 推理模型",
  "o3-mini": "开放人工智能 o3 轻量推理模型",
  "tts-1": "开放人工智能语音 1",
  "tts-1-hd": "开放人工智能高清语音 1",
  sora: "开放人工智能视频生成",
  seedance: "火山方舟即梦视频",
};

const TOKEN_TRANSLATIONS: Record<string, string> = {
  generate: "生成",
  preview: "预览版",
  image: "图像",
  images: "图像",
  video: "视频",
  chat: "对话",
  text: "文本",
  audio: "音频",
  tts: "语音合成",
  t2i: "文生图",
  i2i: "图生图",
  img: "图像",
  wildcard: "通用",
  only: "专用",
  flash: "快速版",
  pro: "专业版",
  ultra: "超清版",
  mini: "轻量版",
  lite: "轻量版",
  turbo: "高速版",
  instruct: "指令版",
  reasoning: "推理版",
};

function normalizeName(value: string): string {
  return value.trim().toLowerCase();
}

function wordsFromModelId(modelId: string): string[] {
  return modelId
    .replace(/[_/]+/g, "-")
    .split("-")
    .map((part) => part.trim())
    .filter(Boolean);
}

function translateModelTokens(modelId: string): string {
  return wordsFromModelId(modelId)
    .map((part) => TOKEN_TRANSLATIONS[part.toLowerCase()] ?? part)
    .join(" ");
}

function versionAfter(prefix: string, modelId: string): string {
  return modelId.slice(prefix.length).replace(/^[-_]+/, "").replace(/[-_]+/g, " ");
}

export function localizeProviderName(providerId: string, rawName?: string): string {
  if (providerId.startsWith(CUSTOM_PREFIX)) {
    return rawName?.trim() || `自定义供应商 ${providerId.slice(CUSTOM_PREFIX.length)}`;
  }

  const byId = PROVIDER_DISPLAY_NAMES_ZH[providerId];
  if (byId) return byId;

  const raw = rawName?.trim();
  if (raw) {
    const byRaw = PROVIDER_NAME_ALIASES[normalizeName(raw)];
    if (byRaw) return byRaw;
    return raw;
  }

  return providerId;
}

export function formatModelDisplayName(providerId: string, modelId: string): string {
  const normalized = normalizeName(modelId);
  const exact = EXACT_MODEL_NAMES[normalized];
  if (exact) return exact;

  if (providerId.startsWith("gemini")) {
    if (normalized.startsWith("veo-")) return `谷歌视频 ${versionAfter("veo", modelId)}`;
    if (normalized.startsWith("imagen-")) return `谷歌图像 ${versionAfter("imagen", modelId)}`;
    if (normalized.startsWith("gemini-")) return `谷歌双子座 ${versionAfter("gemini", modelId)}`;
  }

  if (providerId === "ark") {
    if (normalized.startsWith("seedance")) return `火山方舟即梦视频 ${versionAfter("seedance", modelId)}`;
    if (normalized.startsWith("seedream")) return `火山方舟即梦图像 ${versionAfter("seedream", modelId)}`;
    if (normalized.startsWith("doubao")) return `火山方舟豆包 ${versionAfter("doubao", modelId)}`;
  }

  if (providerId === "dashscope") {
    if (normalized.startsWith("qwen")) return `阿里通义千问 ${versionAfter("qwen", modelId)}`;
    if (normalized.startsWith("wanx")) return `阿里通义万相 ${versionAfter("wanx", modelId)}`;
  }

  if (providerId === "openai") {
    if (normalized.startsWith("sora")) return `开放人工智能视频 ${versionAfter("sora", modelId)}`;
    if (normalized.startsWith("gpt")) return `开放人工智能 ${modelId.toUpperCase()}`;
    if (/^o\d/.test(normalized)) return `开放人工智能 ${modelId} 推理模型`;
  }

  if (providerId === "kling") return `可灵 ${translateModelTokens(modelId)}`;
  if (providerId === "minimax") return `MiniMax 海螺 ${translateModelTokens(modelId)}`;
  if (providerId === "vidu") return `生数科技视频 ${translateModelTokens(modelId)}`;
  if (providerId === "grok") return `xAI 格洛克 ${translateModelTokens(modelId)}`;

  return translateModelTokens(modelId);
}

export function formatBackendDisplay(backend: string, providerNames?: Record<string, string>): string {
  const slashIdx = backend.indexOf("/");
  if (slashIdx === -1) return backend;
  const providerId = backend.slice(0, slashIdx);
  const modelId = backend.slice(slashIdx + 1);
  return `${localizeProviderName(providerId, providerNames?.[providerId])} · ${formatModelDisplayName(providerId, modelId)}`;
}
