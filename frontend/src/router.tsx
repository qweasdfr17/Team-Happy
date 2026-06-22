// router.tsx — Route definitions for the studio layout

import { lazy, Suspense, useEffect, type ReactNode } from "react";
import { Route, Switch, Redirect } from "wouter";
import { useTranslation } from "react-i18next";
import { Loader2 } from "lucide-react";
import { ToastOverlay } from "@/components/layout/ToastOverlay";
import { useAuthStore } from "@/stores/auth-store";
import { useConfigStatusStore } from "@/stores/config-status-store";

const ProjectsPage = lazy(() => import("@/components/pages/ProjectsPage").then((m) => ({ default: m.ProjectsPage })));
const SystemConfigPage = lazy(() =>
  import("@/components/pages/SystemConfigPage").then((m) => ({ default: m.SystemConfigPage })),
);
const ProjectSettingsPage = lazy(() =>
  import("@/components/pages/ProjectSettingsPage").then((m) => ({ default: m.ProjectSettingsPage })),
);
const AssetLibraryPage = lazy(() =>
  import("@/components/pages/AssetLibraryPage").then((m) => ({ default: m.AssetLibraryPage })),
);
const StudioWorkspacePage = lazy(() =>
  import("@/components/pages/StudioWorkspacePage").then((m) => ({ default: m.StudioWorkspacePage })),
);
const LoginPage = lazy(() => import("@/pages/LoginPage").then((m) => ({ default: m.LoginPage })));
const NotFoundPage = lazy(() => import("@/pages/NotFoundPage").then((m) => ({ default: m.NotFoundPage })));

// ---------------------------------------------------------------------------
// ConfigStatusLoader — 登录后集中拉取一次配置完整性状态
// ---------------------------------------------------------------------------

/**
 * 配置完整性（红点 / 必需设置提醒）的单点加载器，始终挂载在路由根，跨页面导航存活。
 * 单例 store 一次初始化即覆盖所有落地页（首页 / 设置 / 项目），不再依赖某个具体页面
 * 是否在 mount 时拉取。首次失败（如后端尚未就绪）时带界次数退避重试，无需手动刷新页面。
 */
function ConfigStatusLoader() {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);

  useEffect(() => {
    if (!isAuthenticated) return;
    let cancelled = false;
    let attempts = 0;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const tick = async () => {
      await useConfigStatusStore.getState().fetch();
      if (cancelled) return;
      if (!useConfigStatusStore.getState().initialized && attempts < 5) {
        attempts += 1;
        timer = setTimeout(() => void tick(), 800 * attempts);
      }
    };
    void tick();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [isAuthenticated]);

  return null;
}

function RouteLoading() {
  const { t } = useTranslation("common");
  return (
    <div
      role="status"
      aria-live="polite"
      className="flex min-h-screen items-center justify-center gap-2 bg-bg text-[13px] text-text-4"
    >
      <Loader2 aria-hidden className="h-4 w-4 motion-safe:animate-spin" />
      <span>{t("loading")}</span>
    </div>
  );
}

function LazyRoute({ children }: { children: ReactNode }) {
  return <Suspense fallback={<RouteLoading />}>{children}</Suspense>;
}

// ---------------------------------------------------------------------------
// AuthGuard — redirects to /login when not authenticated
// ---------------------------------------------------------------------------

function AuthGuard({ children }: { children: ReactNode }) {
  const { isAuthenticated, isLoading } = useAuthStore();
  const { t } = useTranslation("common");

  if (isLoading) {
    return (
      <div
        role="status"
        aria-live="polite"
        className="flex h-screen items-center justify-center gap-2 bg-bg text-[13px] text-text-4"
      >
        <Loader2 aria-hidden className="h-4 w-4 motion-safe:animate-spin" />
        <span>{t("loading")}</span>
      </div>
    );
  }

  if (!isAuthenticated) {
    // 用 `~` 前缀跳到顶层 /login：AuthGuard 可能渲染在 nest 嵌套路由内
    // （/app/projects/:projectName），此时相对路径会被拼到嵌套 base 之后，
    // 必须用绝对路径才能落到真正的 /login。
    // 带上完整原始 URL（取 window.location，nest 内 useLocation 只是相对路径），
    // 登录成功后据此回跳。
    const from = window.location.pathname + window.location.search + window.location.hash;
    return <Redirect to={`~/login?from=${encodeURIComponent(from)}`} />;
  }

  return <>{children}</>;
}

// ---------------------------------------------------------------------------
// Top-level route tree
// ---------------------------------------------------------------------------

export function AppRoutes() {
  return (
    <>
      <ConfigStatusLoader />
      <Switch>
        {/* Login page */}
        <Route path="/login">
          <LazyRoute>
            <LoginPage />
          </LazyRoute>
        </Route>

        {/* Root redirects to projects list */}
        <Route path="/">
          <Redirect to="/app/projects" />
        </Route>

        {/* /app and /app/ also redirect to projects list */}
        <Route path="/app">
          <Redirect to="/app/projects" />
        </Route>

        {/* Projects list */}
        <Route path="/app/projects">
          <AuthGuard>
            <LazyRoute>
              <ProjectsPage />
            </LazyRoute>
          </AuthGuard>
        </Route>

        {/* System settings */}
        <Route path="/app/settings">
          <AuthGuard>
            <LazyRoute>
              <SystemConfigPage />
            </LazyRoute>
          </AuthGuard>
        </Route>

        {/* Asset library */}
        <Route path="/app/assets">
          <AuthGuard>
            <LazyRoute>
              <AssetLibraryPage />
            </LazyRoute>
          </AuthGuard>
        </Route>

        {/* Project settings — full-screen, must be before the nested workspace route */}
        <Route path="/app/projects/:projectName/settings">
          <AuthGuard>
            <LazyRoute>
              <ProjectSettingsPage />
            </LazyRoute>
          </AuthGuard>
        </Route>

        {/* Studio workspace (three-column layout) */}
        <Route path="/app/projects/:projectName" nest>
          <AuthGuard>
            <LazyRoute>
              <StudioWorkspacePage />
            </LazyRoute>
          </AuthGuard>
        </Route>

        {/* 404 */}
        <Route>
          <LazyRoute>
            <NotFoundPage />
          </LazyRoute>
        </Route>
      </Switch>
      <ToastOverlay />
    </>
  );
}
