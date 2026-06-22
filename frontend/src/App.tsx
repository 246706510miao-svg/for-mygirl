import { useState } from "react";
import { LoginScreen, type LoginCredentials } from "./app/LoginScreen";
import { MobileWorkspace } from "./app/MobileWorkspace";
import { OpsWorkspace } from "./features/ops/OpsWorkspace";
import { loginWithCredentials, type ClientRole } from "./shared/api/client";
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

  // 这个函数登录并按后端角色进入对应工作区。
  async function submitLogin(credentials: LoginCredentials) {
    setLoggingIn(true);
    setLoginStatus("");
    try {
      const result = await loginWithCredentials(credentials.loginName, credentials.password);
      setRoute(isOpsRole(result.auth.person.role) ? { kind: "ops" } : { kind: "mobile", role: result.role });
    } catch (error) {
      setLoginStatus(error instanceof Error ? error.message : "登录失败");
    } finally {
      setLoggingIn(false);
    }
  }

  if (route.kind === "ops") {
    return <OpsWorkspace />;
  }

  return route.kind === "login" ? (
    <LoginScreen busy={loggingIn} status={loginStatus} onSubmit={submitLogin} />
  ) : (
    <MobileWorkspace role={route.role} />
  );
}
