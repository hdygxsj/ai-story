import { FormEvent, useState } from "react";

import { login, register } from "../../api/auth";

type AuthPageProps = {
  onAuthenticated: (token: string) => void;
};

export function AuthPage({ onAuthenticated }: AuthPageProps) {
  const [email, setEmail] = useState("demo@example.com");
  const [username, setUsername] = useState("demo");
  const [password, setPassword] = useState("secret123");
  const [error, setError] = useState<string | null>(null);

  async function handleLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    try {
      const response = await login(email, password);
      onAuthenticated(response.access_token);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Login failed");
    }
  }

  async function handleRegister() {
    setError(null);
    try {
      await register(email, username, password);
      const response = await login(email, password);
      onAuthenticated(response.access_token);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Registration failed");
    }
  }

  return (
    <section style={{ display: "grid", gap: 12, maxWidth: 420 }}>
      <h2>Sign in</h2>
      <p>Use a local account to keep novel workspaces isolated by user.</p>
      <form onSubmit={handleLogin} style={{ display: "grid", gap: 8 }}>
        <input aria-label="Email" value={email} onChange={(event) => setEmail(event.target.value)} />
        <input
          aria-label="Username"
          value={username}
          onChange={(event) => setUsername(event.target.value)}
        />
        <input
          aria-label="Password"
          type="password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
        />
        <div style={{ display: "flex", gap: 8 }}>
          <button type="submit">Login</button>
          <button type="button" onClick={handleRegister}>
            Register
          </button>
        </div>
      </form>
      {error ? <p role="alert">{error}</p> : null}
    </section>
  );
}
