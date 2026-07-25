import { useEffect, useState } from "react";
import { createApiClient, getApiBaseUrl, type AuthSession } from "../api";
import {
  clearSessionToken,
  consumeOAuthCallback,
  getSessionToken,
} from "./session";
import "./AccountPanel.css";

const client = createApiClient();

const connectionLabels = {
  gemini_api_key: "Gemini API key",
  claude_oauth_token: "Claude Code OAuth token",
  github_pat: "GitHub fine-grained PAT",
} as const;

type ConnectionKind = keyof typeof connectionLabels;

export function AccountPanel() {
  const [session, setSession] = useState<AuthSession | null>(null);
  const [expanded, setExpanded] = useState(false);
  const [kind, setKind] = useState<ConnectionKind>("gemini_api_key");
  const [secret, setSecret] = useState("");
  const [label, setLabel] = useState("");
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refreshSession = () =>
    client
      .getSession()
      .then(setSession)
      .catch((reason: unknown) => {
        setError(reason instanceof Error ? reason.message : String(reason));
      });

  useEffect(() => {
    consumeOAuthCallback();
    void refreshSession();
  }, []);

  const beginLogin = () => {
    const returnTo = encodeURIComponent(window.location.origin);
    window.location.assign(`${getApiBaseUrl()}/auth/github/login?return_to=${returnTo}`);
  };

  const saveConnection = async () => {
    setNotice(null);
    setError(null);
    try {
      await client.saveConnection(kind, secret, label || connectionLabels[kind]);
      setSecret("");
      setLabel("");
      setNotice(`${connectionLabels[kind]} connected`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    }
  };

  const logout = async () => {
    await client.logout();
    clearSessionToken();
    setSession({ authenticated: false });
    setExpanded(false);
  };

  if (session?.authenticated !== true || !getSessionToken()) {
    return (
      <aside className="account-panel">
        <button type="button" onClick={beginLogin}>
          Sign in with GitHub
        </button>
        {error && <p className="account-panel__error">{error}</p>}
      </aside>
    );
  }

  return (
    <aside className="account-panel">
      <button type="button" onClick={() => setExpanded((value) => !value)}>
        @{session.user.github_login}
      </button>
      {expanded && (
        <div className="account-panel__popover">
          <p>Credentials are encrypted on the server and are never shown again.</p>
          <label>
            <span>Connection</span>
            <select
              value={kind}
              onChange={(event) => setKind(event.target.value as ConnectionKind)}
            >
              {Object.entries(connectionLabels).map(([value, display]) => (
                <option key={value} value={value}>
                  {display}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>Label</span>
            <input value={label} onChange={(event) => setLabel(event.target.value)} />
          </label>
          <label>
            <span>Credential</span>
            <input
              type="password"
              autoComplete="off"
              value={secret}
              onChange={(event) => setSecret(event.target.value)}
            />
          </label>
          <button type="button" disabled={!secret.trim()} onClick={() => void saveConnection()}>
            Save connection
          </button>
          <button type="button" onClick={() => void logout()}>
            Sign out
          </button>
          {notice && <p className="account-panel__notice">{notice}</p>}
          {error && <p className="account-panel__error">{error}</p>}
        </div>
      )}
    </aside>
  );
}
