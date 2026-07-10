// Tiny API client for the Aadyon Assist FastAPI backend.
// The base URL is user-configurable (your Tailscale host) and persisted on device.
// The app is multi-user now: requests carry a JWT bearer token obtained at login.
import AsyncStorage from "@react-native-async-storage/async-storage";
import Constants from "expo-constants";
import EventSource from "react-native-sse";

const BASE_KEY = "aadyon.apiBase";
const TOKEN_KEY = "aadyon.token";

// Baked in at bundle time from EAS env vars or mobile/.env (gitignored — the
// tailnet hostname never goes in git); app.json keeps a neutral localhost default.
const FALLBACK =
  process.env.EXPO_PUBLIC_API_BASE ||
  (Constants.expoConfig?.extra as any)?.defaultApiBase ||
  "http://localhost:8000";

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
    throw new ApiError(res.status, errorDetail(body) || `HTTP ${res.status}`);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

// FastAPI errors are {"detail": "..."} — show the human part, not raw JSON.
function errorDetail(body: string): string {
  try {
    const d = JSON.parse(body)?.detail;
    if (typeof d === "string") return d;
    if (d) return JSON.stringify(d);
  } catch {}
  return body;
}

function post<T>(path: string, body: any): Promise<T> {
  return request<T>(path, { method: "POST", body: JSON.stringify(body) });
}

export type User = { id: string; email: string; display_name?: string };
export type AuthResult = { token: string; user: User };
export type EmailAccount = {
  id: string;
  email: string;
  provider: string;
  purpose?: string | null;
  auth_type: string;
  imap_host?: string | null;
  imap_port?: number | null;
  status?: string | null;
  last_sync?: string | null;
  last_error?: string | null;
};
export type EmailExtraction = {
  id: string;
  kind?: string | null;
  subject?: string | null;
  sender?: string | null;
  summary?: string | null;
  payload?: Record<string, any> | null;
  account_email?: string | null;
  message_date?: string | null;
};
export type MsDeviceCode = {
  user_code: string;
  verification_uri: string;
  device_code: string;
  interval: number;
  expires_in: number;
};
export type GoogleAuthConfig = { client_id: string; auth_endpoint: string; scope: string };
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

  // Mail integrations (mirrors the web dashboard's accounts page).
  // Accounts are generic CRUD rows; connect/sync/review live under /api/email.
  emailAccounts: () => request<EmailAccount[]>("/api/email_accounts"),
  addEmailAccount: (payload: {
    email: string;
    provider: string;
    purpose?: string | null;
    auth_type: string;
    status: string;
    imap_host?: string | null;
    imap_port?: number | null;
  }) => post<EmailAccount>("/api/email_accounts", payload),
  deleteEmailAccount: (id: string) =>
    request<void>(`/api/email_accounts/${id}`, { method: "DELETE" }),
  emailConnect: (id: string, password: string) =>
    post<{ status: string }>(`/api/email/${id}/connect`, { password }),
  emailDisconnect: (id: string) => post<{ status: string }>(`/api/email/${id}/disconnect`, {}),
  emailSync: (id: string) =>
    post<{ scanned?: number; queued?: number }>(`/api/email/${id}/sync`, {}),
  emailMsStart: (id: string) => post<MsDeviceCode>(`/api/email/${id}/ms/start`, {}),
  emailMsComplete: (id: string, device_code: string) =>
    post<{ status: string }>(`/api/email/${id}/ms/complete`, { device_code }),
  emailGoogleConfig: () => request<GoogleAuthConfig>("/api/email/google/config"),
  emailGoogleComplete: (id: string, code: string, code_verifier: string, redirect_uri: string) =>
    post<{ status: string }>(`/api/email/${id}/google/complete`, { code, code_verifier, redirect_uri }),
  emailExtractions: (status = "pending") =>
    request<EmailExtraction[]>(`/api/email/extractions?status=${encodeURIComponent(status)}`),
  approveExtraction: (id: string) =>
    post<{ applied_as?: string }>(`/api/email/extractions/${id}/approve`, {}),
  dismissExtraction: (id: string) =>
    post<{ status: string }>(`/api/email/extractions/${id}/dismiss`, {}),

  // Assistant (Aadyon Assist) & Documents
  uploadDocument: async (
    uri: string,
    name: string,
    mimeType: string
  ): Promise<{ status: string; document_id: string }> => {
    const base = await getApiBase();
    const token = await getToken();

    const formData = new FormData();
    // @ts-ignore - React Native FormData accepts uri/name/type
    formData.append("file", { uri, name, type: mimeType });

    let res: Response;
    try {
      res = await fetch(`${base}/api/documents`, {
        method: "POST",
        headers: {
          // Do NOT set Content-Type manually here; fetch will automatically
          // set it to multipart/form-data with the correct boundary string.
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: formData,
      });
    } catch (e: any) {
      throw new ApiError(0, e?.message || "Upload failed");
    }

    if (res.status === 401) {
      await clearToken();
      onUnauthorized?.();
      throw new ApiError(401, "Your session expired — please sign in again.");
    }
    if (!res.ok) {
      const text = await res.text().catch(() => "");
      throw new ApiError(res.status, text || `HTTP ${res.status}`);
    }
    return await res.json();
  },

  conversations: () => request<any[]>("/api/assistant/conversations"),
  messages: (cid: string) => request<any[]>(`/api/assistant/conversations/${cid}/messages`),
  chat: (message: string, conversation_id?: string) =>
    post<ChatResult>("/api/assistant/chat", { message, conversation_id }),
  chatStream: async (
    message: string,
    conversation_id: string | undefined,
    onChunk: (chunk: { delta: string }) => void
  ): Promise<ChatResult> => {
    const base = await getApiBase();
    const token = await getToken();
    const url = `${base}/api/assistant/chat/stream`;

    return new Promise<ChatResult>((resolve, reject) => {
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
