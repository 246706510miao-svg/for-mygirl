import { useEffect, useState } from "react";
import { LoginScreen, type AuthFormPayload } from "./app/LoginScreen";
import { MobileWorkspace } from "./app/MobileWorkspace";
import { OpsWorkspace } from "./features/ops/OpsWorkspace";
import { loginWithCredentials, logoutCurrentSession, registerWithCredentials, restoreSession, type ClientRole } from "./shared/api/client";
import type { Role } from "./shared/types/api";
import "./styles.css";

type AppRoute = { kind: "login" } | { kind: "mobile"; role: ClientRole } | { kind: "ops" };

// 这个函数判断登录人是否进入后台运维端。
function isOpsRole(role: Role) {
  return role === "OPS_ADMIN" || role === "ADMIN";
}

// 这个组件只负责登录分流和应用壳。
export default function App() {
  const [route, setRoute] = useState<AppRoute>({ kind: "login" });
  const [loginStatus, setLoginStatus] = useState("");
  const [loggingIn, setLoggingIn] = useState(false);
  const [booting, setBooting] = useState(true);

  useEffect(() => {
    let ignored = false;

    async function bootstrap() {
      const restored = await restoreSession();
      if (!ignored && restored) {
        setRoute(restored.role === "ops" ? { kind: "ops" } : { kind: "mobile", role: restored.role });
      }
      if (!ignored) {
        setBooting(false);
      }
    }

    void bootstrap();
    return () => {
      ignored = true;
    };
  }, []);

  // 这个函数登录并按后端角色进入对应工作区。
  async function submitAuth(payload: AuthFormPayload) {
    setLoggingIn(true);
    setLoginStatus("");
    try {
      const result = payload.mode === "register"
        ? await registerWithCredentials(payload.loginName, payload.displayName, payload.password)
        : await loginWithCredentials(payload.loginName, payload.password);
      setRoute(isOpsRole(result.auth.person.role) ? { kind: "ops" } : { kind: "mobile", role: result.role });
    } catch (error) {
      setLoginStatus(error instanceof Error ? error.message : payload.mode === "register" ? "注册失败" : "登录失败");
    } finally {
      setLoggingIn(false);
    }
  }

  async function logout() {
    await logoutCurrentSession();
    setRoute({ kind: "login" });
  }

  if (booting) {
    return <LoginScreen busy status="" onSubmit={submitAuth} />;
  }

  if (route.kind === "ops") {
    return <OpsWorkspace onLogout={() => void logout()} />;
  }

  return route.kind === "login" ? (
    <LoginScreen busy={loggingIn} status={loginStatus} onSubmit={submitAuth} />
  ) : (
    <MobileWorkspace role={route.role} onLogout={() => void logout()} />
  );
}
