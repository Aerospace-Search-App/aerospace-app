export type Role = 'user' | 'admin';
export type Category = 'civil' | 'defense';

export interface User {
  id: number;
  email: string;
  username: string | null;
  full_name: string;
  role: Role;
  organization: string | null;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: 'bearer';
  user: User;
}

export interface DocumentItem {
  id: number;
  code: string;
  title: string;
  issuer: string;
  category: Category;
  domains: string[];
  language: 'en' | 'tr';
  version: string;
  published_on: string;
  summary: string;
  source_url: string;
  page_count: number;
  chunk_count: number;
  embedded_count: number;
  status: string;
  error: string | null;
  created_at: string;
  is_saved: boolean;
}

export interface Citation {
  n: number;
  chunk_id: number;
  document_id: number;
  code: string;
  issuer: string;
  version: string;
  doc_title: string;
  clause_ref: string;
  heading: string;
  page_start: number;
  snippet: string;
}

export interface Message {
  id: number;
  role: 'user' | 'assistant';
  content: string;
  citations: Citation[];
  meta: { mode?: string; latency_ms?: number; model?: string | null; terms?: string[]; sources_scanned?: number } & Record<string, unknown>;
  saved: boolean;
  created_at: string;
  pending?: boolean;
  failed?: boolean;
}

export interface ChatResponse {
  conversation_id: number;
  title: string;
  user_message: Message;
  answer: Message;
}

export interface Conversation {
  id: number;
  title: string;
  project_id: number | null;
  project_name: string | null;
  created_at: string;
  updated_at: string;
  last_message: string | null;
  message_count: number;
  starred: boolean;
  sources: string[];
}

export interface ConversationDetail extends Conversation {
  messages: Message[];
}

export interface Chunk {
  id: number;
  document_id: number;
  ord: number;
  clause_ref: string;
  heading: string;
  heading_path: string;
  part: number;
  page_start: number;
  page_end: number;
  content: string;
}

export interface SourceDetail {
  chunk: Chunk;
  document: DocumentItem;
  prev_id: number | null;
  next_id: number | null;
  is_saved: boolean;
  file_url: string;
  page_image_url: string;
}

export interface ClauseItem {
  id: number;
  ord: number;
  clause_ref: string;
  heading: string;
  page_start: number;
  part: number;
}

export interface Domain {
  key: string;
  label: string;
  icon: string;
  hint: string;
}

export interface Project {
  id: number;
  name: string;
  description: string;
  category: Category | 'both';
  domains: string[];
  created_at: string;
  updated_at: string;
  saved_count: number;
  conversation_count: number;
}

export interface ProjectInput {
  name: string;
  description: string;
  category: Category | 'both';
  domains: string[];
}

export interface Recommendation {
  document: DocumentItem;
  score: number;
  reasons: string[];
  clauses: { chunk_id: number; clause_ref: string; heading: string; page_start: number; snippet: string }[];
}

export interface SavedItem {
  id: number;
  document_id: number;
  chunk_id: number | null;
  project_id: number | null;
  note: string;
  created_at: string;
  code: string;
  doc_title: string;
  issuer: string;
  category: Category;
  clause_ref: string | null;
  heading: string | null;
  page_start: number | null;
  snippet: string | null;
}

export interface Health {
  status: string;
  llm_enabled: boolean;
  documents: number;
}

export interface SavedAnswer {
  message_id: number;
  conversation_id: number;
  question: string;
  snippet: string;
  sources: string[];
  source_count: number;
  saved_at: string;
}

export interface Issuer {
  issuer: string;
  documents: number;
}
