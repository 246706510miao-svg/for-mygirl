import { useState } from "react";
import { AdminWorkspace } from "./features/admin/AdminWorkspace";
import { UserWorkspace } from "./features/user/UserWorkspace";
import "./styles.css";

// 这个组件提供用户端和管理员端切换。
export default function App() {
  const [mode, setMode] = useState<"user" | "admin">("user");
  return (
    <>
      <header className="topbar">
        <div>
          <p>For My Girl</p>
          <h1>接口驱动基础前端</h1>
        </div>
        <nav>
          <button className={mode === "user" ? "active" : ""} onClick={() => setMode("user")}>用户端</button>
          <button className={mode === "admin" ? "active" : ""} onClick={() => setMode("admin")}>管理员端</button>
        </nav>
      </header>
      {mode === "user" ? <UserWorkspace /> : <AdminWorkspace />}
    </>
  );
}
