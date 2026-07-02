// Tiny API client for the Aadyon Assist FastAPI backend.
// The base URL is user-configurable (your Tailscale host) and persisted on device.
// The app is multi-user now: requests carry a JWT bearer token obtained at login.
import AsyncStorage from "@react-native-async-storage/async-storage";
import Constants from "expo-constants";
import EventSource from "react-native-sse";

const BASE_KEY = "aadyon.apiBase";
const TOKEN_KEY = "aadyon.token";

const FALLBACK =
  (Constants.expoConfig?.extra as any)?.defaultApiBase || "http://localhost:8000";

let cachedBase: string | null = null;
let cachedToken: string | null | undefined; // undefined = not loaded yet

// The UI registers a handler so a 401 anywhere kicks the user back to login.
let onUnauthorized: (() => void) | null = null;
export function setUnauthorizedHandler(fn: (() => void) | null) {
  onUnauthorized = fn;
}

export async function getApiBase(): Promise<string> {
  if (cachedBase) return cachedBase;
  const stored = await AsyncStorage.getItem(BASE_KEY);
  const base = (stored || FALLBACK).replace(/\/+$/, "");
  cachedBase = base;
  return base;
}

export async function setApiBase(base: string): Promise<void> {
  const clean = base.trim().replace(/\/+$/, "");
  cachedBase = clean;
  await AsyncStorage.setItem(BASE_KEY, clean);
}

export async function getToken(): Promise<string | null> {
  if (cachedToken !== undefined) return cachedToken ?? null;
  cachedToken = await AsyncStorage.getItem(TOKEN_KEY);
  return cachedToken ?? null;
}

export async function setToken(token: string): Promise<void> {
  cachedToken = token;
  await AsyncStorage.setItem(TOKEN_KEY, token);
}

export async function clearToken(): Promise<void> {
  cachedToken = null;
  await AsyncStorage.removeItem(TOKEN_KEY);
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const base = await getApiBase();
  const token = await getToken();
  const url = `${base}${path}`;
  let res: Response;
  try {
    res = await fetch(url, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(init?.headers || {}),
      },
    });
  } catch (e: any) {
    throw new ApiError(0, `Can't reach ${base}. Check the API URL and that you're on Tailscale.`);
  }
  if (res.status === 401) {
    await clearToken();
    onUnauthorized?.();
    throw new ApiError(401, "Your session expired — please sign in again.");
  }
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new ApiError(res.status, body || `HTTP ${res.status}`);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

function post<T>(path: string, body: any): Promise<T> {
  return request<T>(path, { method: "POST", body: JSON.stringify(body) });
}

export type User = { id: string; email: string; display_name?: string };
export type AuthResult = { token: string; user: User };
export type ChatResult = {
  conversation_id: string;
  reply: string;
  proposals: { id: string; title?: string }[];
  actions: string[];
};

// ---- Endpoints ----
export const api = {
  // Public
  health: () => request<{ status: string; db: string }>("/api/health"),

  // Auth
  signup: (email: string, password: string, display_name?: string) =>
    post<AuthResult>("/api/auth/signup", { email, password, display_name }),
  login: (email: string, password: string) =>
    post<AuthResult>("/api/auth/login", { email, password }),
  me: () => request<User>("/api/auth/me"),

  // Data (all now require a token; the header is added automatically)
  digitalMe: () => request<DigitalMe>("/api/digital-me"),
  summary: () => request<Summary>("/api/summary"),
  briefing: () => request<{ markdown: string }>("/api/briefing"),
  agencyOrg: () => request<any>("/api/agency/org"),
  agencyHealth: () => request<any>("/api/agency/health"),
  agencyTasks: (status?: string) =>
    request<any[]>(`/api/agency/tasks${status ? `?status=${encodeURIComponent(status)}` : ""}`),

  // Assistant (Jarvis)
  conversations: () => request<any[]>("/api/assistant/conversations"),
  messages: (cid: string) => request<any[]>(`/api/assistant/conversations/${cid}/messages`),
  chat: (message: string, conversation_id?: string) =>
    post<ChatResult>("/api/assistant/chat", { message, conversation_id }),
  chatStream: (
    message: string,
    conversation_id: string | undefined,
    onChunk: (chunk: { delta: string }) => void
  ) => {
    return new Promise<ChatResult>(async (resolve, reject) => {
      const base = await getApiBase();
      const token = await getToken();
      const url = `${base}/api/assistant/chat/stream`;

      const es = new EventSource(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ message, conversation_id }),
      });

      es.addEventListener("message", (event) => {
        if (event.data) {
          try {
            const parsed = JSON.parse(event.data);
            if (parsed.error) {
              es.close();
              reject(new ApiError(500, parsed.error));
            } else if (parsed.done) {
              es.close();
              resolve(parsed as ChatResult);
            } else {
              onChunk(parsed);
            }
          } catch (e) {
            console.error("SSE parse error", e);
          }
        }
      });

      es.addEventListener("error", (event: any) => {
        es.close();
        reject(new ApiError(500, event.message || "Stream error"));
      });
    });
  },
};

// ---- Loose types (backend is the source of truth; keep these forgiving) ----
export type Dimension = {
  score: number;
  band?: string;
  label?: string;
  components?: Record<string, any>;
};

export type DigitalMe = {
  as_of: string;
  profile: Record<string, any>;
  life: Record<string, any>;
  income: Record<string, any>;
  overall: { score: number; band?: string };
  dimensions: Record<string, Dimension>;
};

export type Summary = {
  deadlines: any[];
  debts: any[];
  debt_totals: Record<string, any>;
  bills: any[];
  subscriptions: any[];
  shifts: any[];
};
