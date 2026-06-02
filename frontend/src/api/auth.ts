import { apiRequest } from "./http";

export type LoginResponse = {
  access_token: string;
  token_type: "bearer";
};

export function login(loginName: string, password: string) {
  return apiRequest<LoginResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ login: loginName, password }),
  });
}

export function register(email: string, username: string, password: string) {
  return apiRequest<{ id: string; email: string; username: string }>("/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, username, password }),
  });
}
