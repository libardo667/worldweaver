import type { AuthMode } from "./EntryFlow";

type AuthScreenProps = {
  authMode: AuthMode;
  username: string;
  displayName: string;
  email: string;
  password: string;
  showPassword: boolean;
  resetToken: string;
  newPassword: string;
  showNewPassword: boolean;
  resetStatus: string | null;
  authError: string | null;
  joining: boolean;
  onAuthModeChange: (mode: AuthMode) => void;
  onUsernameChange: (value: string) => void;
  onDisplayNameChange: (value: string) => void;
  onEmailChange: (value: string) => void;
  onPasswordChange: (value: string) => void;
  onShowPasswordChange: (value: boolean) => void;
  onResetTokenChange: (value: string) => void;
  onNewPasswordChange: (value: string) => void;
  onShowNewPasswordChange: (value: boolean) => void;
  onSubmit: () => void;
  onRequestResetToken: () => void;
};

export function AuthScreen({
  authMode,
  username,
  displayName,
  email,
  password,
  showPassword,
  resetToken,
  newPassword,
  showNewPassword,
  resetStatus,
  authError,
  joining,
  onAuthModeChange,
  onUsernameChange,
  onDisplayNameChange,
  onEmailChange,
  onPasswordChange,
  onShowPasswordChange,
  onResetTokenChange,
  onNewPasswordChange,
  onShowNewPasswordChange,
  onSubmit,
  onRequestResetToken,
}: AuthScreenProps) {
  const submitDisabled =
    joining ||
    !username.trim() ||
    (authMode === "register" && (!password.trim() || !email.trim())) ||
    (authMode === "login" && !password.trim()) ||
    (authMode === "reset" && (!resetToken.trim() || !newPassword.trim()));

  return (
    <div className="entry-overlay entry-overlay--alert">
      <div className="entry-alert-box">
        <p className="entry-alert-header" style={{ fontSize: "clamp(1.2rem, 3vw, 2rem)", letterSpacing: "0.1em" }}>
          Join as yourself
        </p>
        <p className="entry-alert-text" style={{ maxWidth: "32rem", textAlign: "center" }}>
          Create a persistent identity so the world can remember you when you return. You do not need to decide up front whether you are a mentor or steward. Start by entering, observing, and contributing.
        </p>
        <div className="entry-auth-tabs" style={{ justifyContent: "center" }}>
          <button
            className={`entry-auth-tab${authMode === "register" ? " active" : ""}`}
            onClick={() => onAuthModeChange("register")}
          >
            Register
          </button>
          <button
            className={`entry-auth-tab${authMode === "login" ? " active" : ""}`}
            onClick={() => onAuthModeChange("login")}
          >
            Log in
          </button>
          <button
            className={`entry-auth-tab${authMode === "reset" ? " active" : ""}`}
            onClick={() => onAuthModeChange("reset")}
          >
            Reset password
          </button>
        </div>
        <div className="entry-card-form" style={{ width: "100%", maxWidth: "320px", alignSelf: "center" }}>
          <input
            className="entry-card-input"
            placeholder={authMode === "login" ? "Username or email" : authMode === "reset" ? "Username or email for reset" : "Username"}
            value={username}
            autoComplete={authMode === "reset" ? "username email" : "username"}
            autoFocus
            onChange={(e) => onUsernameChange(e.target.value)}
          />
          {authMode === "register" && (
            <>
              <input
                className="entry-card-input"
                placeholder="Display name (in-world name)"
                value={displayName}
                onChange={(e) => onDisplayNameChange(e.target.value)}
              />
              <input
                className="entry-card-input"
                placeholder="Email"
                type="email"
                autoComplete="email"
                value={email}
                onChange={(e) => onEmailChange(e.target.value)}
              />
            </>
          )}
          {authMode !== "reset" && (
            <>
              <input
                className="entry-card-input"
                placeholder="Password"
                type={showPassword ? "text" : "password"}
                autoComplete={authMode === "register" ? "new-password" : "current-password"}
                value={password}
                onChange={(e) => onPasswordChange(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter") onSubmit(); }}
              />
              <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", fontSize: "0.88rem", opacity: 0.85 }}>
                <input type="checkbox" checked={showPassword} onChange={(e) => onShowPasswordChange(e.target.checked)} />
                Show password
              </label>
            </>
          )}
          {authMode === "reset" && (
            <>
              <button
                className="entry-auth-tab"
                onClick={onRequestResetToken}
                disabled={joining || !username.trim()}
                style={{ alignSelf: "flex-start" }}
              >
                {joining ? "Sending..." : "Email reset token"}
              </button>
              <input
                className="entry-card-input"
                placeholder="Reset token"
                value={resetToken}
                onChange={(e) => onResetTokenChange(e.target.value)}
              />
              <input
                className="entry-card-input"
                placeholder="New password"
                type={showNewPassword ? "text" : "password"}
                autoComplete="new-password"
                value={newPassword}
                onChange={(e) => onNewPasswordChange(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter") onSubmit(); }}
              />
              <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", fontSize: "0.88rem", opacity: 0.85 }}>
                <input type="checkbox" checked={showNewPassword} onChange={(e) => onShowNewPasswordChange(e.target.checked)} />
                Show new password
              </label>
            </>
          )}
        </div>
        {resetStatus && <p className="entry-alert-text" style={{ maxWidth: "320px", textAlign: "center" }}>{resetStatus}</p>}
        {authError && <p className="entry-auth-error">{authError}</p>}
        <button
          className="entry-alert-btn"
          onClick={onSubmit}
          disabled={submitDisabled}
        >
          {joining
            ? "..."
            : authMode === "register"
              ? "REGISTER ->"
              : authMode === "login"
                ? "LOG IN ->"
                : "RESET PASSWORD ->"}
        </button>
        {authMode === "login" && (
          <button
            className="entry-auth-tab"
            onClick={() => onAuthModeChange("reset")}
            style={{ alignSelf: "center", marginTop: "0.5rem" }}
          >
            Forgot your password?
          </button>
        )}
      </div>
    </div>
  );
}
