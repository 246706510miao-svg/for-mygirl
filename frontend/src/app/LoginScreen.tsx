import { FormEvent, useEffect, useState } from "react";
import { motion } from "motion/react";
import { LogIn, RefreshCw } from "lucide-react";
import { MobileAppShell } from "../components/layout/MobileAppShell";
import { Pressable } from "../components/ui/Pressable";
import { useToast } from "../components/ui/useToast";

export interface AuthFormPayload {
  mode: "login" | "register";
  loginName: string;
  displayName: string;
  password: string;
}

interface LoginScreenProps {
  busy: boolean;
  status: string;
  onSubmit: (payload: AuthFormPayload) => Promise<void>;
}

// 这个函数生成本地开发验证码。
function createCaptchaCode() {
  return String(Math.floor(1000 + Math.random() * 9000));
}

// 这个组件承载登录表单和本地验证码校验。
export function LoginScreen({ busy, status, onSubmit }: LoginScreenProps) {
  const toast = useToast();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [loginName, setLoginName] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [captchaCode, setCaptchaCode] = useState(() => createCaptchaCode());
  const [captchaInput, setCaptchaInput] = useState("");
  const [localStatus, setLocalStatus] = useState("");
  const [shakeKey, setShakeKey] = useState(0);

  useEffect(() => {
    if (status) {
      setShakeKey((value) => value + 1);
      toast.error(status);
    }
  }, [status, toast]);

  // 这个函数刷新本地验证码。
  function refreshCaptcha() {
    setCaptchaCode(createCaptchaCode());
    setCaptchaInput("");
    setLocalStatus("");
  }

  // 这个函数校验表单并触发登录。
  async function submitLogin(event: FormEvent) {
    event.preventDefault();
    setLocalStatus("");
    if (captchaInput.trim() !== captchaCode) {
      setLocalStatus("验证码不正确");
      setCaptchaCode(createCaptchaCode());
      setCaptchaInput("");
      setShakeKey((value) => value + 1);
      toast.error("验证码不正确");
      return;
    }
    if (mode === "register" && password !== confirmPassword) {
      setLocalStatus("两次输入的密码不一致");
      setShakeKey((value) => value + 1);
      toast.error("两次输入的密码不一致");
      return;
    }
    await onSubmit({ mode, loginName, displayName, password });
  }

  return (
    <MobileAppShell className="login-shell">
      <section className="login-screen">
        <motion.form
          key={shakeKey}
          className="login-panel"
          onSubmit={submitLogin}
          initial={{ opacity: 0, y: 18 }}
          animate={localStatus || status ? { opacity: 1, y: 0, x: [0, -8, 8, -5, 5, 0] } : { opacity: 1, y: 0, x: 0 }}
          transition={{ duration: 0.32, ease: [0.22, 1, 0.36, 1] }}
        >
        <div className="login-brand">
          <span>For My Girl</span>
          <h1>{mode === "register" ? "Create account" : "Welcome back"}</h1>
        </div>
        <div className="auth-tabs">
          <Pressable className={mode === "login" ? "is-selected" : ""} onClick={() => setMode("login")} disabled={busy}>
            登录
          </Pressable>
          <Pressable className={mode === "register" ? "is-selected" : ""} onClick={() => setMode("register")} disabled={busy}>
            注册
          </Pressable>
        </div>
        <label>
          账号
          <input value={loginName} onChange={(event) => setLoginName(event.target.value)} />
        </label>
        {mode === "register" && (
          <label>
            显示名
            <input value={displayName} onChange={(event) => setDisplayName(event.target.value)} placeholder="页面展示的名字" />
          </label>
        )}
        <label>
          密码
          <input type="password" value={password} onChange={(event) => setPassword(event.target.value)} />
        </label>
        {mode === "register" && (
          <label>
            确认密码
            <input type="password" value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} />
          </label>
        )}
        <label>
          验证码
          <span className="captcha-row">
            <input value={captchaInput} onChange={(event) => setCaptchaInput(event.target.value)} inputMode="numeric" aria-label="验证码" />
            <Pressable className="captcha-button" onClick={refreshCaptcha} aria-label="刷新验证码">
              <span>{captchaCode}</span>
              <RefreshCw size={16} />
            </Pressable>
          </span>
        </label>
        <Pressable className="primary-button" type="submit" disabled={busy}>
          <LogIn size={18} />
          {busy ? "处理中" : mode === "register" ? "注册并进入" : "进入"}
        </Pressable>
        {(localStatus || status) && <p className="form-status">{localStatus || status}</p>}
        </motion.form>
      </section>
    </MobileAppShell>
  );
}
