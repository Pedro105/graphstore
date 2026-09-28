// Chat import API client - calls the Next.js route handler which forwards
// to FastAPI's POST /v1/imports/chats.

import { postJson } from "@/lib/api/live-client";

export interface ImportedConversation {
  title: string;
  messages_imported: number;
  messages_skipped: number;
  total_entities: number;
  total_relations: number;
}

export interface ChatImportResult {
  import_id: string;
  source_format: string;
  conversations_imported: number;
  total_messages: number;
  total_entities: number;
  total_relations: number;
  conversations: ImportedConversation[];
  errors: string[];
}

export interface ImportChatsInput {
  content: string;
  source_prefix?: string;
}

export async function importChats(input: ImportChatsInput): Promise<ChatImportResult> {
  return postJson<ChatImportResult>("/api/imports/chats", input);
}

export async function uploadChatsFile(
  file: File,
  sourcePrefix = "chat-import",
): Promise<ChatImportResult> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("source_prefix", sourcePrefix);

  const res = await fetch("/api/imports/chats/upload", {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: "Upload failed" }));
    throw new Error(detail.detail || `Upload failed (${res.status})`);
  }

  return res.json() as Promise<ChatImportResult>;
}
