import { useCallback, useRef, useState, type CSSProperties } from "react";
import { useTranslation } from "react-i18next";
import { Popover } from "@/components/ui/Popover";
import { isContinuousIntegerRange } from "@/utils/duration_format";

export interface DurationPillProps {
  seconds: number;
  segmentId: string;
  durationOptions: number[];
  onUpdatePrompt?: (
    segmentId: string,
    fieldOrPatch: string | Record<string, unknown>,
    value?: unknown,
  ) => void | Promise<void>;
}

export function DurationPill({
  seconds,
  segmentId,
  durationOptions,
  onUpdatePrompt,
}: DurationPillProps) {
  const { t } = useTranslation("dashboard");
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLButtonElement>(null);

  const [draftSeconds, setDraftSeconds] = useState<number | null>(null);
  const displaySeconds = draftSeconds ?? seconds;
  const commitDraft = useCallback(() => {
    if (draftSeconds == null) return;
    if (draftSeconds !== seconds) {
      void onUpdatePrompt?.(segmentId, "duration_seconds", draftSeconds);
    }
    setDraftSeconds(null);
  }, [draftSeconds, seconds, segmentId, onUpdatePrompt]);

  const editable = !!onUpdatePrompt;
  const noOptions = durationOptions.length === 0;
  const isIncompatible =
    durationOptions.length > 0 && !durationOptions.includes(seconds);
  const incompatibleLabel = t("duration_incompatible_warning", {
    value: seconds,
    supported: durationOptions.join(", "),
  });
  const useSlider =
    isContinuousIntegerRange(durationOptions) && durationOptions.length >= 5;

  const baseClass =
    "inline-flex items-center gap-1.5 rounded-md px-2 py-[3px] text-[11.5px] focus-ring";
  const baseStyle: CSSProperties = {
    background: isIncompatible
      ? "oklch(0.32 0.10 75 / 0.35)"
      : "oklch(0.22 0.011 265 / 0.6)",
    border: isIncompatible
      ? "1px solid oklch(0.65 0.12 75 / 0.5)"
      : "1px solid var(--color-hairline-soft)",
    color: isIncompatible ? "oklch(0.85 0.12 80)" : "var(--color-text-2)",
  };

  if (!editable) {
    return (
      <span className={baseClass} style={baseStyle}>
        <span style={{ color: "var(--color-text-4)" }}>⏱</span>
        <span className="num">
          {t("duration_seconds_value_text", { value: seconds })}
        </span>
        {isIncompatible && (
          <span aria-label={incompatibleLabel} title={incompatibleLabel}>
            ⚠
          </span>
        )}
      </span>
    );
  }

  return (
    <>
      <button
        ref={ref}
        type="button"
        onClick={() => !noOptions && setOpen((o) => !o)}
        disabled={noOptions}
        aria-disabled={noOptions || undefined}
        title={noOptions ? t("duration_no_options") : undefined}
        className={`${baseClass} transition-colors disabled:cursor-not-allowed disabled:opacity-60`}
        style={baseStyle}
      >
        <span style={{ color: "var(--color-text-4)" }}>⏱</span>
        <span className="num">
          {t("duration_seconds_value_text", { value: seconds })}
        </span>
        {isIncompatible && (
          <span aria-label={incompatibleLabel} title={incompatibleLabel}>
            ⚠
          </span>
        )}
      </button>
      <Popover
        open={open}
        onClose={() => setOpen(false)}
        anchorRef={ref}
        width="w-auto"
        align="start"
        sideOffset={6}
        backgroundColor="oklch(0.21 0.012 265 / 0.98)"
        className="rounded-lg p-2"
        style={{
          border: "1px solid var(--color-hairline)",
          boxShadow:
            "0 24px 60px -20px oklch(0 0 0 / 0.7), 0 0 0 1px var(--color-hairline-soft)",
          backdropFilter: "blur(12px)",
          WebkitBackdropFilter: "blur(12px)",
        }}
      >
        {useSlider ? (
          <div className="flex items-center gap-2 px-1 py-1">
            <input
              type="range"
              aria-label={t("duration_selector_aria")}
              aria-valuetext={t("duration_seconds_value_text", { value: displaySeconds })}
              min={durationOptions[0]}
              max={durationOptions[durationOptions.length - 1]}
              step={1}
              value={displaySeconds}
              onChange={(e) => setDraftSeconds(parseInt(e.target.value, 10))}
              onPointerUp={commitDraft}
              onKeyUp={(e) => {
                if (
                  e.key === "ArrowLeft" ||
                  e.key === "ArrowRight" ||
                  e.key === "ArrowUp" ||
                  e.key === "ArrowDown" ||
                  e.key === "Home" ||
                  e.key === "End" ||
                  e.key === "PageUp" ||
                  e.key === "PageDown"
                ) {
                  commitDraft();
                }
              }}
              onBlur={commitDraft}
              className="theme-slider w-40"
            />
            <span
              className="num min-w-[2.25rem] text-right text-[11.5px]"
              style={{ color: "var(--color-text-2)" }}
            >
              {t("duration_seconds_value_text", { value: displaySeconds })}
            </span>
          </div>
        ) : (
          <div
            className="flex flex-wrap gap-1"
            role="radiogroup"
            aria-label={t("duration_selector_aria")}
          >
            {durationOptions.map((d) => {
              const checked = d === seconds;
              return (
                <button
                  key={d}
                  role="radio"
                  type="button"
                  aria-checked={checked}
                  onClick={() => {
                    void onUpdatePrompt(segmentId, "duration_seconds", d);
                    setOpen(false);
                  }}
                  className="num rounded-md px-2.5 py-1 text-[11.5px] font-medium transition-colors focus-ring"
                  style={
                    checked
                      ? {
                          background:
                            "linear-gradient(180deg, var(--color-accent-2), var(--color-accent))",
                          color: "oklch(0.14 0 0)",
                          boxShadow:
                            "inset 0 1px 0 oklch(1 0 0 / 0.25), 0 2px 6px -2px var(--color-accent-glow)",
                        }
                      : {
                          background: "oklch(0.22 0.011 265 / 0.5)",
                          color: "var(--color-text-2)",
                          border: "1px solid var(--color-hairline-soft)",
                        }
                  }
                >
                  {t("duration_seconds_value_text", { value: d })}
                </button>
              );
            })}
          </div>
        )}
      </Popover>
    </>
  );
}
