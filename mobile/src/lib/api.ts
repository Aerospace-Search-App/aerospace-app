import Constants from 'expo-constants';
import { Platform } from 'react-native';

import { storage } from './storage';
import type {
  ChatResponse,
  ClauseItem,
  Conversation,
  ConversationDetail,
  DocumentItem,
  Domain,
  Health,
  Issuer,
  SavedAnswer,
  Project,
  ProjectInput,
  Recommendation,
  SavedItem,
  SourceDetail,
  TokenResponse,
  User,
} from './types';

const API_PORT = 8000;
const SERVER_KEY = 'aerostd.server';

/**
 * API adresi önceliği:
 *  1) Uygulamada Profil → Sunucu adresi ile girilen değer
 *  2) EXPO_PUBLIC_API_URL ortam değişkeni
 *  3) Expo Go'nun bağlandığı bilgisayarın IP'si (hostUri) + :8000  → ek ayar gerekmez
 */
function detectDefaultBaseUrl(): string {
  const env = process.env.EXPO_PUBLIC_API_URL;
  if (env) return env.replace(/\/$/, '');
  if (Platform.OS === 'web' && typeof window !== 'undefined') {
    return `${window.location.protocol}//${window.location.hostname}:${API_PORT}`;
  }
  const hostUri = Constants.expoConfig?.hostUri ?? '';
  const host = hostUri.split(':')[0];
  if (host && !host.includes('exp.direct')) return `http://${host}:${API_PORT}`;
  return `http://localhost:${API_PORT}`;
}

let baseUrl = detectDefaultBaseUrl();
let token: string | null = null;
let onUnauthorized: (() => void) | null = null;

export const api = {
  get baseUrl() {
    return baseUrl;
  },
  defaultBaseUrl: detectDefaultBaseUrl,
  async loadServer() {
    const saved = await storage.get(SERVER_KEY);
    if (saved) baseUrl = saved;
    return baseUrl;
  },
  async setServer(url: string | null) {
    if (url) {
      const clean = url.trim().replace(/\/$/, '');
      baseUrl = /^https?:\/\//.test(clean) ? clean : `http://${clean}`;
      await storage.set(SERVER_KEY, baseUrl);
    } else {
      baseUrl = detectDefaultBaseUrl();
      await storage.remove(SERVER_KEY);
    }
  },
  setToken(t: string | null) {
    token = t;
  },
  setUnauthorizedHandler(fn: (() => void) | null) {
    onUnauthorized = fn;
  },
  absolute(path: string) {
    return path.startsWith('http') ? path : `${baseUrl}${path}`;
  },
};

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(method: string, path: string, body?: unknown, timeoutMs = 60000): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  let res: Response;
  try {
    res = await fetch(`${baseUrl}${path}`, {
      method,
      headers: {
        Accept: 'application/json',
        ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    });
  } catch (e) {
    const aborted = (e as Error)?.name === 'AbortError';
    throw new ApiError(
      0,
      aborted
        ? 'Sunucu zamanında yanıt vermedi. Lütfen tekrar deneyin.'
        : `Sunucuya bağlanılamadı (${baseUrl}). Bilgisayar ile telefon aynı Wi-Fi ağında mı ve backend çalışıyor mu?`,
    );
  } finally {
    clearTimeout(timer);
  }
  if (res.status === 204) return undefined as T;
  let data: any = null;
  try {
    data = await res.json();
  } catch {
    /* gövde yok */
  }
  if (!res.ok) {
    if (res.status === 401 && token) onUnauthorized?.();
    const detail = typeof data?.detail === 'string' ? data.detail : `İstek başarısız (${res.status})`;
    throw new ApiError(res.status, detail);
  }
  return data as T;
}

const get = <T,>(p: string) => request<T>('GET', p);
const post = <T,>(p: string, b?: unknown, t?: number) => request<T>('POST', p, b ?? {}, t);
const put = <T,>(p: string, b: unknown) => request<T>('PUT', p, b);
const patch = <T,>(p: string, b: unknown) => request<T>('PATCH', p, b);
const del = <T,>(p: string) => request<T>('DELETE', p);

export const endpoints = {
  health: () => get<Health>('/api/health'),
  login: (email: string, password: string) => post<TokenResponse>('/api/auth/login', { email, password }),
  register: (username: string, email: string, password: string, accept_terms: boolean) =>
    post<TokenResponse>('/api/auth/register', { username, email, password, accept_terms }),
  me: () => get<User>('/api/auth/me'),
  updateMe: (body: { username?: string; full_name?: string }) => patch<User>('/api/auth/me', body),
  issuers: () => get<Issuer[]>('/api/meta/issuers'),

  domains: () => get<Domain[]>('/api/meta/domains'),
  documents: (params: { q?: string; category?: string; domain?: string } = {}) => {
    const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v) as [string, string][]).toString();
    return get<DocumentItem[]>(`/api/documents${qs ? `?${qs}` : ''}`);
  },
  document: (id: number) => get<DocumentItem>(`/api/documents/${id}`),
  clauses: (id: number) => get<ClauseItem[]>(`/api/documents/${id}/clauses`),
  source: (chunkId: number) => get<SourceDetail>(`/api/chunks/${chunkId}`),

  chat: (message: string, opts: { conversation_id?: number | null; project_id?: number | null; issuer?: string | null } = {}) =>
    post<ChatResponse>(
      '/api/chat',
      { message, conversation_id: opts.conversation_id ?? null, project_id: opts.project_id ?? null, issuer: opts.issuer ?? null },
      120000,
    ),
  conversations: (params: { project_id?: number; q?: string; starred?: boolean } = {}) => {
    const qs = new URLSearchParams();
    if (params.project_id) qs.set('project_id', String(params.project_id));
    if (params.q) qs.set('q', params.q);
    if (params.starred) qs.set('starred', 'true');
    const s = qs.toString();
    return get<Conversation[]>(`/api/conversations${s ? `?${s}` : ''}`);
  },
  starConversation: (id: number, on: boolean) => request<void>(on ? 'PUT' : 'DELETE', `/api/conversations/${id}/star`),
  saveAnswer: (messageId: number, on: boolean) => request<void>(on ? 'PUT' : 'DELETE', `/api/messages/${messageId}/save`),
  savedAnswers: (q?: string) => get<SavedAnswer[]>(`/api/saved/answers${q ? `?q=${encodeURIComponent(q)}` : ''}`),
  conversation: (id: number) => get<ConversationDetail>(`/api/conversations/${id}`),
  renameConversation: (id: number, title: string) => patch<Conversation>(`/api/conversations/${id}`, { title }),
  deleteConversation: (id: number) => del<void>(`/api/conversations/${id}`),

  projects: () => get<Project[]>('/api/projects'),
  project: (id: number) => get<Project>(`/api/projects/${id}`),
  createProject: (body: ProjectInput) => post<Project>('/api/projects', body),
  updateProject: (id: number, body: ProjectInput) => put<Project>(`/api/projects/${id}`, body),
  deleteProject: (id: number) => del<void>(`/api/projects/${id}`),
  recommendations: (id: number) => get<Recommendation[]>(`/api/projects/${id}/recommendations`),

  saved: (project_id?: number) => get<SavedItem[]>(`/api/saved${project_id ? `?project_id=${project_id}` : ''}`),
  save: (document_id: number, chunk_id?: number | null, project_id?: number | null, note = '') =>
    post<SavedItem>('/api/saved', { document_id, chunk_id: chunk_id ?? null, project_id: project_id ?? null, note }),
  unsave: (document_id: number, chunk_id?: number | null) =>
    del<void>(`/api/saved?document_id=${document_id}${chunk_id ? `&chunk_id=${chunk_id}` : ''}`),
  deleteSaved: (id: number) => del<void>(`/api/saved/${id}`),
};
