import type { ProjectData } from "@/types";
import type { AssetKind, ReferenceResource } from "@/types/reference-video";

/**
 * Mention regex shared across frontend tokenizers. Mirrors backend
 * `lib/reference_video/shot_parser.py` mention scanner — keep in sync.
 *
 * 前后端字面不同但语义等价：
 * - JS `\w` 永远是 ASCII-only，`(?<!\w)` 直接表达"左侧不是 ASCII 词字符"。
 * - Python `\w` 默认 Unicode-aware（中文属 `\w`），所以后端改用显式
 *   `[A-Za-z0-9_]` 字符类，避免误拒 `你好@张三` 这类中文前缀。
 *
 * CJK 字符（`\u4e00-\u9fff`）在两边都不在词字符集内，所以中文前缀合法。
 *
 * Supports legacy `@名称` plus wrapped `@[名称]` for asset names
 * containing punctuation, spaces, or parentheses.
 *
 * Curly-brace wrapping (`@{名称}`) is intentionally unsupported: the editor
 * only emits `@[名称]`, and narrowing the parser avoids carrying an unused
 * alternate syntax through highlight / merge / backend replacement paths.
 */
export const MENTION_RE = /(?<!\w)@(?:\[([^\]\r\n]+)\]|([\w\u4e00-\u9fff]+))/g;

export function mentionNameFromMatch(match: RegExpMatchArray): string {
  return match[1] ?? match[2] ?? "";
}

export function extractMentions(text: string): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const m of text.matchAll(MENTION_RE)) {
    const name = mentionNameFromMatch(m);
    if (!seen.has(name)) {
      seen.add(name);
      out.push(name);
    }
  }
  return out;
}

type ProjectBuckets = Pick<ProjectData, "characters" | "scenes" | "props">;

export function resolveMentionType(
  project: ProjectBuckets | null | undefined,
  name: string,
): AssetKind | undefined {
  if (!project) return undefined;
  if (project.characters && name in project.characters) return "character";
  if (project.scenes && name in project.scenes) return "scene";
  if (project.props && name in project.props) return "prop";
  return undefined;
}

/**
 * Re-derive the references list for a unit given new prompt text.
 *
 * Rules:
 *  1. Preserve the order of `existing` entries whose names still appear in prompt.
 *  2. Drop entries whose names no longer appear.
 *  3. Append new mentions (in first-appearance order) that resolve to a known bucket.
 *  4. Skip unknown mentions (they become UI warning chips, not references).
 *  5. Deduplicate by name.
 */
export function mergeReferences(
  prompt: string,
  existing: ReferenceResource[],
  project: ProjectBuckets | null | undefined,
): ReferenceResource[] {
  const mentioned = new Set(extractMentions(prompt));
  const kept: ReferenceResource[] = [];
  const keptNames = new Set<string>();
  for (const ref of existing) {
    if (mentioned.has(ref.name) && !keptNames.has(ref.name)) {
      kept.push(ref);
      keptNames.add(ref.name);
    }
  }
  for (const name of mentioned) {
    if (keptNames.has(name)) continue;
    const type = resolveMentionType(project, name);
    if (!type) continue;
    kept.push({ type, name });
    keptNames.add(name);
  }
  return kept;
}

const IMG_DECL_RE = /(?:图|图片|image|img|\[图)\s*\d+\s*\]?/i;
const IMG_DECL_LINE_RE = /^\s*(?:图片|图|image|img|\[图)\s*\d+\s*\]?\s*[：:-]\s*(.+?)\s*$/i;

function refKey(ref: ReferenceResource): string {
  return `${ref.type}:${ref.name}`;
}

function knownReferences(
  existing: ReferenceResource[],
  project: ProjectBuckets | null | undefined,
): ReferenceResource[] {
  const out: ReferenceResource[] = [];
  const seen = new Set<string>();
  const add = (ref: ReferenceResource) => {
    const key = refKey(ref);
    if (seen.has(key)) return;
    out.push(ref);
    seen.add(key);
  };

  existing.forEach(add);
  for (const [type, bucket] of [
    ["character", project?.characters],
    ["scene", project?.scenes],
    ["prop", project?.props],
  ] as const) {
    for (const name of Object.keys(bucket ?? {})) add({ type, name });
  }
  return out;
}

function normalizeDeclaredName(raw: string): string {
  const trimmed = raw.trim();
  const mention = [...trimmed.matchAll(MENTION_RE)][0];
  if (mention) return mentionNameFromMatch(mention);
  return trimmed.replace(/[，,。；;：:\s]+$/g, "");
}

function resolveDeclaredReference(
  raw: string,
  existing: ReferenceResource[],
  project: ProjectBuckets | null | undefined,
): ReferenceResource | null {
  const name = normalizeDeclaredName(raw);
  const exactType = resolveMentionType(project, name);
  if (exactType) return { type: exactType, name };

  const known = knownReferences(existing, project);
  const exact = known.find((ref) => ref.name === name);
  if (exact) return exact;

  const contained = known
    .filter((ref) => name.includes(ref.name))
    .sort((a, b) => b.name.length - a.name.length)[0];
  return contained ?? null;
}

function extractOrderedPromptReferences(
  prompt: string,
  existing: ReferenceResource[],
  project: ProjectBuckets | null | undefined,
): ReferenceResource[] {
  const ordered: ReferenceResource[] = [];
  const seen = new Set<string>();
  const add = (ref: ReferenceResource | null) => {
    if (!ref) return;
    const key = refKey(ref);
    if (seen.has(key)) return;
    ordered.push(ref);
    seen.add(key);
  };

  for (const line of prompt.split(/\r?\n/)) {
    const decl = line.match(IMG_DECL_LINE_RE);
    if (decl) add(resolveDeclaredReference(decl[1] ?? "", existing, project));
    for (const mention of line.matchAll(MENTION_RE)) {
      const name = mentionNameFromMatch(mention);
      const type = resolveMentionType(project, name);
      if (type) add({ type, name });
    }
  }
  return ordered;
}

function lineDeclaresReference(line: string, ref: ReferenceResource): boolean {
  return IMG_DECL_RE.test(line) && line.includes(ref.name);
}

export function promptContainsReference(prompt: string, ref: ReferenceResource): boolean {
  if (extractMentions(prompt).includes(ref.name)) return true;
  return prompt.split(/\r?\n/).some((line) => lineDeclaresReference(line, ref));
}

/**
 * Derive the visible/submittable reference list from the current prompt.
 *
 * This is stricter than the legacy mergeReferences flow: existing references
 * stay only when they are represented in the prompt by either an @mention or a
 * numbered image declaration such as "图片1：主角". New @mentions are appended in
 * first-occurrence order.
 */
export function deriveReferencesFromPrompt(
  prompt: string,
  existing: ReferenceResource[],
  project: ProjectBuckets | null | undefined,
): ReferenceResource[] {
  return extractOrderedPromptReferences(prompt, existing, project);
}

function escapeRegExp(text: string): string {
  return text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

export function appendReferenceMention(prompt: string, ref: ReferenceResource): string {
  if (promptContainsReference(prompt, ref)) return prompt;
  const mention = `@[${ref.name}]`;
  if (!prompt.trim()) return `${mention} `;
  const lines = prompt.split(/\r?\n/);
  const headerIndex = lines.findIndex((line) => line.includes("【图片引用声明】"));
  if (headerIndex >= 0) {
    const next = [...lines];
    next.splice(headerIndex + 1, 0, mention);
    return next.join("\n");
  }
  return `${mention}\n${prompt}`;
}

export function syncPromptReferenceSection(prompt: string, references: ReferenceResource[]): string {
  const lines = prompt.split(/\r?\n/);
  const headerIndex = lines.findIndex((line) => line.includes("【图片引用声明】"));
  if (headerIndex < 0) return prompt;
  const nextDecls = references.map((ref) => `@[${ref.name}]`);
  let end = headerIndex + 1;
  while (end < lines.length) {
    const line = lines[end];
    if (line.trim() === "") break;
    if (/^【.+】/.test(line.trim())) break;
    end += 1;
  }
  return [
    ...lines.slice(0, headerIndex + 1),
    ...nextDecls,
    ...lines.slice(end),
  ].join("\n");
}

export function removeReferenceFromPrompt(prompt: string, ref: ReferenceResource): string {
  const lines = prompt.split(/\r?\n/).filter((line) => !lineDeclaresReference(line, ref));
  const withoutImageDecl = lines.join("\n");
  const legacy = new RegExp(`(?<!\\w)@${escapeRegExp(ref.name)}(?=$|[^\\w\\u4e00-\\u9fff])`, "g");
  const wrapped = new RegExp(`(?<!\\w)@\\[${escapeRegExp(ref.name)}\\]\\s?`, "g");
  return withoutImageDecl
    .replace(wrapped, "")
    .replace(legacy, "")
    .replace(/[ \t]{2,}/g, " ")
    .replace(/\n{3,}/g, "\n\n")
    .trimStart();
}
