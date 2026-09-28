import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";

const CONTEXTSTORE_API_URL =
  process.env.CONTEXTSTORE_API_URL ??
  process.env.FASTAPI_BASE_URL ??
  "http://localhost:8000";

const API_KEY = process.env.CONTEXTSTORE_API_KEY;
const ACTIVE_PROJECT_COOKIE = "cs_active_project";

export async function POST(request: NextRequest) {
  const formData = await request.formData();
  const file = formData.get("file");
  const sourcePrefix = formData.get("source_prefix") ?? "chat-import";

  if (!file || !(file instanceof File)) {
    return NextResponse.json(
      { detail: "No file provided" },
      { status: 400 },
    );
  }

  const upstreamForm = new FormData();
  upstreamForm.append("file", file);
  upstreamForm.append("source_prefix", String(sourcePrefix));

  const headers = new Headers();
  if (API_KEY) headers.set("Authorization", `Bearer ${API_KEY}`);
  const active = (await cookies()).get(ACTIVE_PROJECT_COOKIE)?.value;
  if (active) headers.set("X-Project", active);

  const upstream = await fetch(`${CONTEXTSTORE_API_URL}/v1/imports/chats/upload`, {
    method: "POST",
    headers,
    body: upstreamForm,
  });

  const text = await upstream.text();
  if (!text) {
    return new NextResponse(null, { status: upstream.status });
  }

  try {
    const data = JSON.parse(text);
    return NextResponse.json(data, { status: upstream.status });
  } catch {
    return new NextResponse(text, {
      status: upstream.status,
      headers: { "Content-Type": "text/plain" },
    });
  }
}
