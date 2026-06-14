export type AuthRoute = "login" | "register";

export function authRouteFromPath(pathname: string): AuthRoute {
  const normalized = pathname.replace(/\/+$/, "") || "/";
  if (normalized === "/register") {
    return "register";
  }
  return "login";
}

export function authPathForRoute(route: AuthRoute): string {
  return route === "register" ? "/register" : "/login";
}

export function pushAuthPath(route: AuthRoute) {
  const nextPath = authPathForRoute(route);
  if (window.location.pathname !== nextPath) {
    window.history.pushState(null, "", nextPath);
  }
}
