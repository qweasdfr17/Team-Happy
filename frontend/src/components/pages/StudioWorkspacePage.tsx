import { lazy, Suspense, useEffect } from "react";
import { useParams } from "wouter";

import { API } from "@/api";
import { StudioLayout } from "@/components/layout";
import { useAssistantStore } from "@/stores/assistant-store";
import { useProjectsStore } from "@/stores/projects-store";

const StudioCanvasRouter = lazy(() =>
  import("@/components/canvas/StudioCanvasRouter").then((m) => ({ default: m.StudioCanvasRouter })),
);

function StudioCanvasLoading() {
  return <div className="flex min-h-0 flex-1 items-center justify-center text-[13px] text-text-4" />;
}

export function StudioWorkspacePage() {
  const params = useParams<{ projectName: string }>();
  const projectName = params.projectName ?? null;
  const { setCurrentProject, setProjectDetailLoading } = useProjectsStore();

  useEffect(() => {
    if (!projectName) return;
    let cancelled = false;

    const assistantState = useAssistantStore.getState();
    assistantState.setSessions([]);
    assistantState.setCurrentSessionId(null);
    assistantState.setTurns([]);
    assistantState.setDraftTurn(null);
    assistantState.setSessionStatus(null);
    assistantState.setIsDraftSession(false);

    setProjectDetailLoading(true);
    API.getProject(projectName)
      .then((res) => {
        if (!cancelled) {
          setCurrentProject(projectName, res.project, res.scripts ?? {}, res.asset_fingerprints);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setCurrentProject(projectName, null);
        }
      })
      .finally(() => {
        if (!cancelled) setProjectDetailLoading(false);
      });

    return () => {
      cancelled = true;
      setCurrentProject(null, null);
    };
  }, [projectName, setCurrentProject, setProjectDetailLoading]);

  return (
    <StudioLayout>
      <Suspense fallback={<StudioCanvasLoading />}>
        <StudioCanvasRouter />
      </Suspense>
    </StudioLayout>
  );
}
