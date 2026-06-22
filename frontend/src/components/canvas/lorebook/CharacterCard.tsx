import { useCallback, useEffect, useId, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { AudioLines, ImagePlus, Trash2, Upload, User } from "lucide-react";
import { API } from "@/api";
import { AddToLibraryButton } from "@/components/assets/AddToLibraryButton";
import { VersionTimeMachine } from "@/components/canvas/timeline/VersionTimeMachine";
import { AspectFrame } from "@/components/ui/AspectFrame";
import { GenerateButton } from "@/components/ui/GenerateButton";
import { ImageFlipReveal } from "@/components/ui/ImageFlipReveal";
import { PreviewableImageFrame } from "@/components/ui/PreviewableImageFrame";
import { useAppStore } from "@/stores/app-store";
import { useProjectsStore } from "@/stores/projects-store";
import { errMsg } from "@/utils/async";
import type { Character } from "@/types";

interface CharacterSavePayload {
  description: string;
  voiceStyle: string;
  referenceFile?: File | null;
}

interface CharacterCardProps {
  name: string;
  character: Character;
  projectName: string;
  onSave: (name: string, payload: CharacterSavePayload) => Promise<void>;
  onGenerate: (name: string) => void;
  onRestoreVersion?: () => Promise<void> | void;
  onReload?: () => Promise<unknown> | void;
  generating?: boolean;
}

const FIELD_STYLE: React.CSSProperties = {
  background:
    "linear-gradient(180deg, oklch(0.20 0.011 265 / 0.6), oklch(0.18 0.010 265 / 0.45))",
  border: "1px solid var(--color-hairline)",
  color: "var(--color-text)",
  boxShadow: "inset 0 1px 2px oklch(0 0 0 / 0.2)",
};

export function CharacterCard({
  name,
  character,
  projectName,
  onSave,
  onGenerate,
  onRestoreVersion,
  onReload,
  generating = false,
}: CharacterCardProps) {
  const { t } = useTranslation(["dashboard", "assets"]);
  const sheetFp = useProjectsStore(
    (s) => character.character_sheet ? s.getAssetFingerprint(character.character_sheet) : null,
  );
  const referenceFp = useProjectsStore(
    (s) => character.reference_image ? s.getAssetFingerprint(character.reference_image) : null,
  );
  const [description, setDescription] = useState(character.description);
  const [voiceStyle, setVoiceStyle] = useState(character.voice_style ?? "");
  const [imgError, setImgError] = useState(false);
  const [referenceFile, setReferenceFile] = useState<File | null>(null);
  const [referencePreview, setReferencePreview] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [uploadingSheet, setUploadingSheet] = useState(false);
  const [deletingSheet, setDeletingSheet] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [uploadingVoice, setUploadingVoice] = useState(false);
  const [deletingVoice, setDeletingVoice] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const sheetInputRef = useRef<HTMLInputElement>(null);
  const voiceInputRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const descId = useId();
  const voiceId = useId();

  const handleSheetUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    setUploadingSheet(true);
    try {
      await API.uploadFile(projectName, "character", file, name);
      await onReload?.();
      useAppStore.getState().pushToast(t("assets:upload_sheet_success", { name }), "success");
    } catch (err) {
      useAppStore.getState().pushToast(errMsg(err), "error");
    } finally {
      setUploadingSheet(false);
    }
  };

  const handleDeleteSheet = async () => {
    const confirmed = window.confirm(t("assets:delete_sheet_confirm", { name }));
    if (!confirmed) return;
    setDeletingSheet(true);
    try {
      await API.deleteCharacterSheet(projectName, name);
      await onReload?.();
      useAppStore.getState().pushToast(t("assets:delete_sheet_success", { name }), "success");
    } catch (err) {
      useAppStore.getState().pushToast(errMsg(err), "error");
    } finally {
      setDeletingSheet(false);
    }
  };

  const handleVoiceUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    setUploadingVoice(true);
    try {
      await API.uploadCharacterVoiceReference(projectName, name, file);
      await onReload?.();
      useAppStore.getState().pushToast(t("assets:upload_sheet_success", { name }), "success");
    } catch (err) {
      useAppStore.getState().pushToast(errMsg(err), "error");
    } finally {
      setUploadingVoice(false);
    }
  };

  const handleDeleteVoice = async () => {
    const confirmed = window.confirm(t("assets:delete_voice_confirm", { name }));
    if (!confirmed) return;
    setDeletingVoice(true);
    try {
      await API.deleteCharacterVoiceReference(projectName, name);
      await onReload?.();
      useAppStore.getState().pushToast(t("assets:delete_sheet_success", { name }), "success");
    } catch (err) {
      useAppStore.getState().pushToast(errMsg(err), "error");
    } finally {
      setDeletingVoice(false);
    }
  };

  useEffect(() => {
    // 上游角色变化时同步本地草稿字段
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setDescription(character.description);
    setVoiceStyle(character.voice_style ?? "");
  }, [character.description, character.voice_style]);

  useEffect(() => {
    // 角色立绘变化时重置图片加载错误标记
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setImgError(false);
  }, [character.character_sheet, sheetFp]);

  useEffect(() => {
    // 上游参考图变化时清空本地未提交的上传文件 + 释放 blob URL
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setReferenceFile(null);
    setReferencePreview((prev) => {
      if (prev) URL.revokeObjectURL(prev);
      return null;
    });
  }, [character.reference_image]);

  useEffect(() => {
    return () => {
      if (referencePreview) {
        URL.revokeObjectURL(referencePreview);
      }
    };
  }, [referencePreview]);

  const autoResize = useCallback(() => {
    const el = textareaRef.current;
    if (el) {
      el.style.height = "auto";
      el.style.height = `${el.scrollHeight}px`;
    }
  }, []);

  useEffect(() => {
    autoResize();
  }, [autoResize, description]);

  const isDirty =
    description !== character.description ||
    voiceStyle !== (character.voice_style ?? "") ||
    referenceFile !== null;

  const handleReferenceChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setReferenceFile(file);
    setReferencePreview((prev) => {
      if (prev) URL.revokeObjectURL(prev);
      return URL.createObjectURL(file);
    });
    e.target.value = "";
  };

  const clearPendingReference = () => {
    setReferenceFile(null);
    setReferencePreview((prev) => {
      if (prev) URL.revokeObjectURL(prev);
      return null;
    });
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await onSave(name, {
        description,
        voiceStyle,
        referenceFile,
      });
    } finally {
      setSaving(false);
    }
  };

  const sheetUrl = character.character_sheet
    ? API.getFileUrl(projectName, character.character_sheet, sheetFp)
    : null;

  const savedReferenceUrl = character.reference_image
    ? API.getFileUrl(projectName, character.reference_image, referenceFp)
    : null;

  const voiceUrl = character.voice_reference_audio
    ? API.getFileUrl(projectName, character.voice_reference_audio)
    : null;

  const displayedReferenceUrl = referencePreview ?? savedReferenceUrl;
  const hasSavedReference = Boolean(savedReferenceUrl) && !referencePreview;

  return (
    <div
      id={`character-${name}`}
      className="relative overflow-hidden rounded-xl p-5"
      data-workspace-editing={isEditing || isDirty ? "true" : undefined}
      onFocusCapture={() => setIsEditing(true)}
      onBlurCapture={(event) => {
        const nextTarget = event.relatedTarget;
        if (nextTarget instanceof Node && event.currentTarget.contains(nextTarget)) {
          return;
        }
        setIsEditing(false);
      }}
      style={{
        background:
          "linear-gradient(180deg, oklch(0.22 0.012 265 / 0.55), oklch(0.19 0.010 265 / 0.40))",
        border: "1px solid var(--color-hairline-soft)",
        boxShadow:
          "inset 0 1px 0 oklch(1 0 0 / 0.04), 0 12px 30px -12px oklch(0 0 0 / 0.4)",
      }}
    >
      {/* Top accent hairline */}
      <span
        aria-hidden
        className="pointer-events-none absolute inset-x-5 top-0 h-px"
        style={{
          background:
            "linear-gradient(90deg, transparent, var(--color-accent-soft), transparent)",
        }}
      />

      {/* ---- Header: 单排 icon + name + icon-only 工具栏 ---- */}
      <div className="mb-4 flex items-center gap-2.5">
        <span
          aria-hidden
          className="grid h-7 w-7 shrink-0 place-items-center rounded-md"
          style={{
            background: "var(--color-accent-dim)",
            border: "1px solid var(--color-accent-soft)",
            color: "var(--color-accent-2)",
          }}
        >
          <User className="h-3.5 w-3.5" />
        </span>
        <h3
          className="display-serif min-w-0 flex-1 truncate text-[16px] font-semibold tracking-tight"
          style={{ color: "var(--color-text)" }}
        >
          {name}
        </h3>
        <div className="flex shrink-0 items-center gap-0.5">
          <button
            type="button"
            onClick={() => sheetInputRef.current?.click()}
            disabled={uploadingSheet}
            title={t("assets:upload_sheet")}
            aria-label={t("assets:upload_sheet")}
            className="focus-ring inline-flex h-7 w-7 items-center justify-center rounded-md transition-colors hover:bg-[oklch(1_0_0_/_0.05)] disabled:opacity-40"
            style={{ color: "var(--color-text-3)" }}
          >
            <Upload className="h-3.5 w-3.5" />
          </button>
          <input
            ref={sheetInputRef}
            type="file"
            accept=".png,.jpg,.jpeg,.webp"
            aria-label={t("assets:upload_sheet")}
            className="hidden"
            onChange={(e) => void handleSheetUpload(e)}
          />
          {character.character_sheet && (
            <button
              type="button"
              onClick={() => void handleDeleteSheet()}
              disabled={deletingSheet}
              title={t("assets:delete_sheet")}
              aria-label={t("assets:delete_sheet")}
              className="focus-ring inline-flex h-7 w-7 items-center justify-center rounded-md transition-colors hover:bg-[oklch(1_0_0_/_0.05)] disabled:opacity-40"
              style={{ color: "var(--color-text-3)" }}
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          )}
          <AddToLibraryButton
            resourceType="character"
            resourceId={name}
            projectName={projectName}
            initialDescription={character.description}
            initialVoiceStyle={character.voice_style ?? ""}
            sheetPath={character.character_sheet}
            className="focus-ring inline-flex h-7 w-7 items-center justify-center rounded-md text-[var(--color-text-3)] transition-colors hover:bg-[oklch(1_0_0_/_0.05)]"
          />
          <VersionTimeMachine
            projectName={projectName}
            resourceType="characters"
            resourceId={name}
            onRestore={onRestoreVersion}
            iconOnly
          />
        </div>
      </div>

      {/* ---- Image area ---- */}
      <div className="mb-4 space-y-3">
        <div>
          <div className="flex items-center justify-between">
            <CapsLabel>{t("character_design")}</CapsLabel>
            {character.character_sheet && (
              <button
                type="button"
                onClick={() => sheetInputRef.current?.click()}
                disabled={uploadingSheet}
                className="focus-ring text-[11px] text-[var(--color-text-3)] transition-colors hover:text-[var(--color-text)]"
              >
                {uploadingSheet ? "..." : t("assets:replace_image")}
              </button>
            )}
          </div>
          <div
            className="mt-1.5 overflow-hidden rounded-lg"
            style={{ border: "1px solid var(--color-hairline-soft)" }}
          >
            <PreviewableImageFrame
              src={sheetUrl && !imgError ? sheetUrl : null}
              alt={`${name} ${t("character_design")}`}
            >
              <AspectFrame ratio="16:9">
                <ImageFlipReveal
                  src={sheetUrl && !imgError ? sheetUrl : null}
                  alt={`${name} ${t("character_design")}`}
                  className="h-full w-full object-contain"
                  onError={() => setImgError(true)}
                  fallback={
                    <div
                      className="flex h-full w-full flex-col items-center justify-center gap-2"
                      style={{ color: "var(--color-text-4)" }}
                    >
                      <User className="h-10 w-10" />
                      <span className="text-xs">{t("click_to_generate")}</span>
                    </div>
                  }
                />
              </AspectFrame>
            </PreviewableImageFrame>
          </div>
        </div>

        <div>
          <div className="flex items-center justify-between">
            <CapsLabel>{t("reference_image")}</CapsLabel>
            {(referenceFile || hasSavedReference) && (
              <button
                type="button"
                onClick={() =>
                  referenceFile
                    ? clearPendingReference()
                    : fileInputRef.current?.click()
                }
                className="focus-ring text-[11px] text-[var(--color-text-3)] transition-colors hover:text-[var(--color-text)]"
              >
                {referenceFile ? t("cancel_pending") : t("replace")}
              </button>
            )}
          </div>

          {displayedReferenceUrl ? (
            <PreviewableImageFrame
              src={displayedReferenceUrl}
              alt={`${name} ${t("reference_image")}`}
              buttonClassName="right-2.5 top-2.5"
            >
              <div
                className="relative mt-1.5 overflow-hidden rounded-lg"
                style={{ border: "1px solid var(--color-hairline-soft)" }}
              >
                <img
                  src={displayedReferenceUrl}
                  alt={`${name} ${t("reference_image")}`}
                  className="h-28 w-full object-cover"
                />
                <div
                  className="absolute inset-x-0 bottom-0 flex items-center justify-between px-3 py-2"
                  style={{
                    background:
                      "linear-gradient(180deg, transparent, oklch(0 0 0 / 0.65))",
                  }}
                >
                  <span
                    className="flex items-center gap-1.5 text-[11px]"
                    style={{ color: "var(--color-text)" }}
                  >
                    <ImagePlus className="h-3.5 w-3.5" />
                    {referenceFile ? t("unsaved_reference") : t("saved_reference")}
                  </span>
                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    className="focus-ring rounded px-2 py-0.5 text-[11px] transition-colors"
                    style={{
                      background: "oklch(0 0 0 / 0.5)",
                      color: "var(--color-text)",
                      border: "1px solid oklch(1 0 0 / 0.1)",
                    }}
                  >
                    {t("change")}
                  </button>
                </div>
              </div>
            </PreviewableImageFrame>
          ) : (
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="focus-ring mt-1.5 flex w-full items-center justify-center gap-2 rounded-lg border border-dashed border-[var(--color-hairline)] px-3 py-4 text-sm text-[var(--color-text-4)] transition-colors hover:border-[var(--color-accent-soft)] hover:text-[var(--color-text-2)]"
              style={{ background: "oklch(0.18 0.010 265 / 0.35)" }}
            >
              <Upload className="h-4 w-4" />
              {t("upload_reference")}
            </button>
          )}
          <input
            ref={fileInputRef}
            type="file"
            accept=".png,.jpg,.jpeg,.webp"
            aria-label={t("upload_character_ref_aria")}
            onChange={handleReferenceChange}
            className="hidden"
          />
        </div>
      </div>

      {/* ---- Voice reference ---- */}
      <div className="mb-4">
        <div className="flex items-center justify-between">
          <CapsLabel>{t("assets:voice_reference")}</CapsLabel>
          <div className="flex items-center gap-0.5">
            <button
              type="button"
              onClick={() => voiceInputRef.current?.click()}
              disabled={uploadingVoice}
              title={
                character.voice_reference_audio
                  ? t("assets:replace_voice_reference")
                  : t("assets:upload_voice_reference")
              }
              aria-label={
                character.voice_reference_audio
                  ? t("assets:replace_voice_reference")
                  : t("assets:upload_voice_reference")
              }
              className="focus-ring inline-flex h-7 w-7 items-center justify-center rounded-md transition-colors hover:bg-[oklch(1_0_0_/_0.05)] disabled:opacity-40"
              style={{ color: "var(--color-text-3)" }}
            >
              <AudioLines className="h-3.5 w-3.5" />
            </button>
            <input
              ref={voiceInputRef}
              type="file"
              accept=".mp3,.wav,.m4a,.aac,.ogg,.flac"
              aria-label={t("assets:upload_voice_reference")}
              className="hidden"
              onChange={(e) => void handleVoiceUpload(e)}
            />
            {character.voice_reference_audio && (
              <button
                type="button"
                onClick={() => void handleDeleteVoice()}
                disabled={deletingVoice}
                title={t("assets:delete_voice_reference")}
                aria-label={t("assets:delete_voice_reference")}
                className="focus-ring inline-flex h-7 w-7 items-center justify-center rounded-md transition-colors hover:bg-[oklch(1_0_0_/_0.05)] disabled:opacity-40"
                style={{ color: "var(--color-text-3)" }}
              >
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            )}
          </div>
        </div>
        {voiceUrl ? (
          <div className="mt-1.5">
            <audio controls className="w-full" style={{ height: 32 }}>
              <source src={voiceUrl} />
              <track kind="captions" />
            </audio>
          </div>
        ) : (
          <button
            type="button"
            onClick={() => voiceInputRef.current?.click()}
            disabled={uploadingVoice}
            className="focus-ring mt-1.5 flex w-full items-center justify-center gap-2 rounded-lg border border-dashed border-[var(--color-hairline)] px-3 py-3 text-[12px] transition-colors hover:border-[var(--color-accent-soft)]"
            style={{ color: "var(--color-text-4)" }}
          >
            <AudioLines className="h-3.5 w-3.5" />
            {t("assets:upload_voice_reference")}
          </button>
        )}
      </div>

      {/* ---- Costume references ---- */}
      <CostumeSection
        name={name}
        character={character}
        projectName={projectName}
        onReload={onReload}
        t={t}
      />

      {/* ---- Character variants ---- */}
      <VariantSection
        name={name}
        character={character}
        projectName={projectName}
        onReload={onReload}
        t={t}
      />

      <CapsLabel htmlFor={descId}>{t("description")}</CapsLabel>
      <textarea
        ref={textareaRef}
        id={descId}
        value={description}
        onChange={(e) => setDescription(e.target.value)}
        onInput={autoResize}
        rows={3}
        className="focus-ring mt-1.5 w-full resize-none overflow-hidden rounded-lg px-3 py-2 text-[13px] leading-[1.55] outline-none transition-[border-color,box-shadow]"
        style={FIELD_STYLE}
        placeholder={t("character_desc_placeholder")}
      />

      <div className="mt-3">
        <CapsLabel htmlFor={voiceId}>{t("voice_style")}</CapsLabel>
        <input
          id={voiceId}
          type="text"
          value={voiceStyle}
          onChange={(e) => setVoiceStyle(e.target.value)}
          className="focus-ring mt-1.5 w-full rounded-lg px-3 py-2 text-[13px] outline-none transition-[border-color,box-shadow]"
          style={FIELD_STYLE}
          placeholder={t("voice_style_example")}
        />
      </div>

      {isDirty && (
        <button
          type="button"
          onClick={() => void handleSave()}
          disabled={saving}
          className="focus-ring mt-3 inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-[12px] font-medium transition-transform disabled:cursor-not-allowed disabled:opacity-50"
          style={{
            color: "oklch(0.14 0 0)",
            background:
              "linear-gradient(135deg, var(--color-accent-2), var(--color-accent))",
            boxShadow:
              "inset 0 1px 0 oklch(1 0 0 / 0.35), 0 6px 18px -4px var(--color-accent-glow), 0 0 0 1px var(--color-accent-soft)",
          }}
        >
          {saving ? t("common:saving") : t("common:save")}
        </button>
      )}

      <div className="mt-4">
        <GenerateButton
          onClick={() => onGenerate(name)}
          loading={generating}
          label={character.character_sheet ? t("regenerate_design") : t("generate_design")}
          className="w-full justify-center"
        />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Small utilities
// ---------------------------------------------------------------------------

function CapsLabel({
  children,
  htmlFor,
}: {
  children: React.ReactNode;
  htmlFor?: string;
}) {
  return (
    <label
      htmlFor={htmlFor}
      className="text-[10px] font-semibold uppercase tracking-[0.12em]"
      style={{ color: "var(--color-text-4)" }}
    >
      {children}
    </label>
  );
}

// ---------------------------------------------------------------------------
// Costume section
// ---------------------------------------------------------------------------

function CostumeSection({
  name,
  character,
  projectName,
  onReload,
  t,
}: {
  name: string;
  character: Character;
  projectName: string;
  onReload?: () => Promise<unknown> | void;
  t: (key: string, vars?: Record<string, string>) => string;
}) {
  const [adding, setAdding] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [label, setLabel] = useState("");
  const [desc, setDesc] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);
  const [pendingFile, setPendingFile] = useState<File | null>(null);

  const costumes = character.costume_references ?? [];

  const handleUpload = async () => {
    if (!pendingFile || !label.trim()) return;
    setUploading(true);
    try {
      await API.uploadCharacterCostume(projectName, name, pendingFile, label.trim(), desc.trim());
      setPendingFile(null);
      setLabel("");
      setDesc("");
      setAdding(false);
      await onReload?.();
      useAppStore.getState().pushToast(t("assets:upload_sheet_success", { name }), "success");
    } catch (err) {
      useAppStore.getState().pushToast(errMsg(err), "error");
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (costumeId: string, costumeLabel: string) => {
    if (!window.confirm(t("assets:delete_costume_confirm", { name, label: costumeLabel }))) return;
    try {
      await API.deleteCharacterCostume(projectName, name, costumeId);
      await onReload?.();
    } catch (err) {
      useAppStore.getState().pushToast(errMsg(err), "error");
    }
  };

  return (
    <div className="mb-4">
      <div className="flex items-center justify-between">
        <CapsLabel>{t("assets:costume_references")}</CapsLabel>
        <button
          type="button"
          onClick={() => setAdding(!adding)}
          className="focus-ring text-[11px] text-[var(--color-text-3)] transition-colors hover:text-[var(--color-text)]"
        >
          {adding ? t("cancel") : "+ " + t("assets:add_costume")}
        </button>
      </div>
      {adding && (
        <div className="mt-1.5 space-y-1.5 rounded-lg p-2" style={{ background: "oklch(0.18 0.010 265 / 0.35)", border: "1px solid var(--color-hairline)" }}>
          <input
            type="text"
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            placeholder={t("assets:costume_label_placeholder")}
            className="w-full rounded px-2 py-1 text-[12px] outline-none"
            style={FIELD_STYLE}
          />
          <input
            type="text"
            value={desc}
            onChange={(e) => setDesc(e.target.value)}
            placeholder={t("assets:costume_desc_placeholder")}
            className="w-full rounded px-2 py-1 text-[12px] outline-none"
            style={FIELD_STYLE}
          />
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => fileRef.current?.click()}
              className="focus-ring rounded px-2 py-1 text-[11px]"
              style={{ color: "var(--color-accent-2)", border: "1px solid var(--color-accent-soft)" }}
            >
              {pendingFile ? pendingFile.name.slice(0, 20) : t("assets:upload_sheet_short")}
            </button>
            <input ref={fileRef} type="file" accept=".png,.jpg,.jpeg,.webp" className="hidden" onChange={(e) => { const f = e.target.files?.[0]; if (f) setPendingFile(f); }} />
            <button
              type="button"
              onClick={() => void handleUpload()}
              disabled={uploading || !pendingFile || !label.trim()}
              className="focus-ring rounded px-2 py-1 text-[11px] font-medium disabled:opacity-40"
              style={{ color: "oklch(0.14 0 0)", background: "var(--color-accent-2)" }}
            >
              {uploading ? "..." : t("assets:upload_sheet_short")}
            </button>
          </div>
        </div>
      )}
      {costumes.length > 0 && (
        <div className="mt-1.5 space-y-1">
          {costumes.map((c) => {
            const url = c.image_path ? API.getFileUrl(projectName, c.image_path) : null;
            return (
              <div key={c.id} className="flex items-center gap-2 rounded-lg p-1.5" style={{ background: "oklch(0.18 0.010 265 / 0.25)", border: "1px solid var(--color-hairline-soft)" }}>
                {url ? (
                  <img src={url} alt={c.label} className="h-10 w-10 shrink-0 rounded object-cover" />
                ) : (
                  <div className="h-10 w-10 shrink-0 rounded" style={{ background: "var(--color-hairline)" }} />
                )}
                <div className="min-w-0 flex-1">
                  <div className="truncate text-[12px] font-medium" style={{ color: "var(--color-text)" }}>{c.label}</div>
                  {c.description && <div className="truncate text-[11px]" style={{ color: "var(--color-text-4)" }}>{c.description}</div>}
                </div>
                <button
                  type="button"
                  onClick={() => void handleDelete(c.id, c.label)}
                  title={t("assets:delete_costume")}
                  className="focus-ring shrink-0 rounded p-0.5 hover:bg-[oklch(1_0_0_/_0.05)]"
                  style={{ color: "var(--color-text-4)" }}
                >
                  <Trash2 className="h-3 w-3" />
                </button>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Variant section
// ---------------------------------------------------------------------------

function VariantSection({
  name,
  character,
  projectName,
  onReload,
  t,
}: {
  name: string;
  character: Character;
  projectName: string;
  onReload?: () => Promise<unknown> | void;
  t: (key: string, vars?: Record<string, string>) => string;
}) {
  const [adding, setAdding] = useState(false);
  const [saving, setSaving] = useState(false);
  const [vLabel, setVLabel] = useState("");
  const [vDesc, setVDesc] = useState("");

  const variants = character.variants ?? [];

  const handleAdd = async () => {
    if (!vLabel.trim()) return;
    setSaving(true);
    try {
      await API.addCharacterVariant(projectName, name, {
        label: vLabel.trim(),
        description: vDesc.trim(),
      });
      setVLabel("");
      setVDesc("");
      setAdding(false);
      await onReload?.();
    } catch (err) {
      useAppStore.getState().pushToast(errMsg(err), "error");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (variantId: string, variantLabel: string) => {
    if (!window.confirm(t("assets:delete_variant_confirm", { name, label: variantLabel }))) return;
    try {
      await API.deleteCharacterVariant(projectName, name, variantId);
      await onReload?.();
    } catch (err) {
      useAppStore.getState().pushToast(errMsg(err), "error");
    }
  };

  const handleSheetUpload = async (variantId: string, file: File) => {
    try {
      await API.uploadVariantSheet(projectName, name, variantId, file);
      await onReload?.();
      useAppStore.getState().pushToast(t("assets:upload_sheet_success", { name }), "success");
    } catch (err) {
      useAppStore.getState().pushToast(errMsg(err), "error");
    }
  };

  return (
    <div className="mb-4">
      <div className="flex items-center justify-between">
        <CapsLabel>{t("assets:variants")}</CapsLabel>
        <button
          type="button"
          onClick={() => setAdding(!adding)}
          className="focus-ring text-[11px] text-[var(--color-text-3)] transition-colors hover:text-[var(--color-text)]"
        >
          {adding ? t("cancel") : "+ " + t("assets:add_variant")}
        </button>
      </div>
      {adding && (
        <div className="mt-1.5 space-y-1.5 rounded-lg p-2" style={{ background: "oklch(0.18 0.010 265 / 0.35)", border: "1px solid var(--color-hairline)" }}>
          <input
            type="text"
            value={vLabel}
            onChange={(e) => setVLabel(e.target.value)}
            placeholder={t("assets:variant_label_placeholder")}
            className="w-full rounded px-2 py-1 text-[12px] outline-none"
            style={FIELD_STYLE}
          />
          <input
            type="text"
            value={vDesc}
            onChange={(e) => setVDesc(e.target.value)}
            placeholder={t("assets:variant_desc_placeholder")}
            className="w-full rounded px-2 py-1 text-[12px] outline-none"
            style={FIELD_STYLE}
          />
          <button
            type="button"
            onClick={() => void handleAdd()}
            disabled={saving || !vLabel.trim()}
            className="focus-ring rounded px-2 py-1 text-[11px] font-medium disabled:opacity-40"
            style={{ color: "oklch(0.14 0 0)", background: "var(--color-accent-2)" }}
          >
            {saving ? "..." : t("create")}
          </button>
        </div>
      )}
      {variants.length > 0 && (
        <div className="mt-1.5 space-y-1.5">
          {variants.map((variant) => (
            <VariantRow
              key={variant.id}
              variant={variant}
              projectName={projectName}
              onDelete={handleDelete}
              onSheetUpload={handleSheetUpload}
              t={t}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function VariantRow({
  variant,
  projectName,
  onDelete,
  onSheetUpload,
  t,
}: {
  variant: NonNullable<Character["variants"]>[number];
  projectName: string;
  onDelete: (variantId: string, variantLabel: string) => Promise<void>;
  onSheetUpload: (variantId: string, file: File) => Promise<void>;
  t: (key: string, vars?: Record<string, string>) => string;
}) {
  const sheetInputRef = useRef<HTMLInputElement>(null);
  const sheetUrl = variant.character_sheet ? API.getFileUrl(projectName, variant.character_sheet) : null;

  return (
    <div className="rounded-lg p-2" style={{ background: "oklch(0.18 0.010 265 / 0.25)", border: "1px solid var(--color-hairline-soft)" }}>
      <div className="flex items-start justify-between">
        <div className="min-w-0 flex-1">
          <div className="text-[12px] font-medium" style={{ color: "var(--color-text)" }}>{variant.label}</div>
          {variant.description && <div className="mt-0.5 text-[11px]" style={{ color: "var(--color-text-4)" }}>{variant.description}</div>}
        </div>
        <button
          type="button"
          onClick={() => void onDelete(variant.id, variant.label)}
          title={t("assets:delete_variant")}
          className="focus-ring shrink-0 rounded p-0.5 hover:bg-[oklch(1_0_0_/_0.05)]"
          style={{ color: "var(--color-text-4)" }}
        >
          <Trash2 className="h-3 w-3" />
        </button>
      </div>
      <div className="mt-1.5 flex items-center gap-2">
        {sheetUrl ? (
          <PreviewableImageFrame src={sheetUrl} alt={variant.label}>
            <img src={sheetUrl} alt={variant.label} className="h-14 w-24 rounded object-cover" style={{ border: "1px solid var(--color-hairline-soft)" }} />
          </PreviewableImageFrame>
        ) : (
          <div className="flex h-14 w-24 items-center justify-center rounded" style={{ border: "1px dashed var(--color-hairline)", color: "var(--color-text-4)" }}>
            <span className="text-[10px]">{t("assets:upload_variant_sheet")}</span>
          </div>
        )}
        <button
          type="button"
          onClick={() => sheetInputRef.current?.click()}
          className="focus-ring rounded px-2 py-0.5 text-[11px]"
          style={{ color: "var(--color-text-3)", border: "1px solid var(--color-hairline)" }}
        >
          {sheetUrl ? t("replace") : t("assets:upload_sheet_short")}
        </button>
        <input
          ref={sheetInputRef}
          type="file"
          accept=".png,.jpg,.jpeg,.webp"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0];
            e.target.value = "";
            if (file) void onSheetUpload(variant.id, file);
          }}
        />
      </div>
    </div>
  );
}
