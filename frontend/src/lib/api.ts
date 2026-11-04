/** Shared API client: base URL, bearer token, error messages and the 401 -> logged out rule. */
export const API_BASE: string = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

const TOKEN_KEY = "jklu_token";

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string | null): void {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    // Blocked storage only means the login won't survive a reload.
  }
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

let onUnauthorized: () => void = () => {};

export function setUnauthorizedHandler(fn: () => void): void {
  onUnauthorized = fn;
}

export function authHeaders(): Record<string, string> {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function detailText(detail: unknown, status: number): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((d) => d?.msg ?? String(d)).join("; ");
  if (detail && typeof detail === "object" && "error" in detail) return String((detail as { error: unknown }).error);
  return `Request failed (HTTP ${status})`;
}

/** Turn a failed response into an ApiError. A 401 on a logged-in call ends the session. */
export async function errorFrom(res: Response): Promise<ApiError> {
  if (res.status === 401 && getToken()) {
    setToken(null);
    onUnauthorized();
    return new ApiError(401, "Your session has expired. Please log in again.");
  }
  const body = await res.json().catch(() => null);
  return new ApiError(res.status, detailText(body?.detail, res.status));
}

const UNREACHABLE = "Can't reach the server. Check that the API is running.";

/** Fetch that reports an unreachable server as an ApiError and leaves aborts alone. */
export async function send(path: string, init: RequestInit): Promise<Response> {
  try {
    return await fetch(`${API_BASE}${path}`, init);
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") throw err;
    throw new ApiError(0, UNREACHABLE);
  }
}

/** JSON request with the auth header. Throws ApiError on any failure. */
export async function api<T>(path: string, options: { method?: string; body?: unknown } = {}): Promise<T> {
  const hasBody = options.body !== undefined;
  const res = await send(path, {
    method: options.method ?? (hasBody ? "POST" : "GET"),
    headers: { ...authHeaders(), ...(hasBody ? { "Content-Type": "application/json" } : {}) },
    body: hasBody ? JSON.stringify(options.body) : undefined,
  });
  if (!res.ok) throw await errorFrom(res);
  return (await res.json()) as T;
}

/** Build a query string, skipping empty values. */
export function query(params: Record<string, string | number | undefined | null>): string {
  const parts = Object.entries(params)
    .filter(([, v]) => v !== undefined && v !== null && v !== "")
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`);
  return parts.length ? `?${parts.join("&")}` : "";
}

export function errorMessage(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}
