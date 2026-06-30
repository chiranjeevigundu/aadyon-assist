// Tiny API client for the Aadyon Assist FastAPI backend.
// The base URL is user-configurable (your Tailscale host) and persisted on device.
import AsyncStorage from "@react-native-async-storage/async-storage";
import Constants from "expo-constants";

const KEY = "aadyon.apiBase";

const FALLBACK =
  (Constants.expoConfig?.extra as any)?.defaultApiBase || "http://localhost:8000";

let cachedBase: string | null = null;

export async function getApiBase(): Promise<string> {
  if (cachedBase) return cachedBase;
  const stored = await AsyncStorage.getItem(KEY);
  cachedBase = (stored || FALLBACK).replace(/\/+$/, "");
  return cachedBase;
}

export async function setApiBase(base: string): Promise<void> {
  const clean = base.trim().replace(/\/+$/, "");
  cachedBase = clean;
  await AsyncStorage.setItem(KEY, clean);
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
  const url = `${base}${path}`;
  let res: Response;
  try {
    res = await fetch(url, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    });
  } catch (e: any) {
    throw new ApiError(0, `Can't reach ${base}. Check the API URL and that you're on Tailscale.`);
  }
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new ApiError(res.status, body || `HTTP ${res.status}`);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

// ---- Endpoints (read-mostly; write actions stay human-in-the-loop) ----
export const api = {
  health: () => request<{ status: string; db: string }>("/api/health"),
  digitalMe: () => request<DigitalMe>("/api/digital-me"),
  summary: () => request<Summary>("/api/summary"),
  briefing: () => request<{ markdown: string }>("/api/briefing"),
  agencyOrg: () => request<any>("/api/agency/org"),
  agencyHealth: () => request<any>("/api/agency/health"),
  agencyTasks: (status?: string) =>
    request<any[]>(`/api/agency/tasks${status ? `?status=${encodeURIComponent(status)}` : ""}`),
  // Approve/reject exist but are intentionally NOT auto-called — the user acts themselves.
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
