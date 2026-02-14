import os
import json
from typing import Optional, List, Any, Dict

import jwt  # PyJWT
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

from supabase import create_client, Client
from openai import OpenAI

APP_TITLE = "Seungbin Brain v1"
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
CHAT_MODEL = os.getenv("CHAT_MODEL", "gpt-4.1")

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

app = FastAPI(title=APP_TITLE)

# Allow your browser UI to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

supabase_admin: Optional[Client] = None
openai_client: Optional[OpenAI] = None

def _ensure_clients():
    global supabase_admin, openai_client
    if not (SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY and SUPABASE_JWT_SECRET and OPENAI_API_KEY):
        raise HTTPException(status_code=500, detail="Server env vars not configured")
    if supabase_admin is None:
        supabase_admin = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    if openai_client is None:
        openai_client = OpenAI(api_key=OPENAI_API_KEY)

def _bearer(request: Request) -> str:
    auth = request.headers.get("authorization") or request.headers.get("Authorization") or ""
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    return auth.split(" ", 1)[1].strip()

def _verify_jwt(token: str) -> Dict[str, Any]:
    try:
        payload = jwt.decode(token, SUPABASE_JWT_SECRET, algorithms=["HS256"], options={"verify_aud": False})
        if "sub" not in payload:
            raise ValueError("No sub")
        return payload
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

def _embed(text: str) -> List[float]:
    _ensure_clients()
    e = openai_client.embeddings.create(model=EMBEDDING_MODEL, input=text).data[0].embedding
    return e

WEB_APP_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Seungbin Brain v1</title>
<style>
  body{font-family:system-ui,-apple-system,Segoe UI,Roboto,Arial;max-width:980px;margin:24px auto;padding:0 16px;}
  .row{display:flex;gap:12px;flex-wrap:wrap;}
  .card{border:1px solid #ddd;border-radius:12px;padding:12px;margin:12px 0;}
  input,textarea,select,button{font:inherit;padding:10px;border-radius:10px;border:1px solid #ccc;}
  textarea{width:100%;min-height:120px;}
  button{cursor:pointer;}
  .muted{color:#666;font-size:13px;}
  pre{white-space:pre-wrap;}
</style>
</head>
<body>
<h2>Seungbin Brain v1</h2>

<div class="card">
  <h3>1) Sign in (Supabase OTP)</h3>
  <div class="row">
    <input id="sb_url" placeholder="SUPABASE_URL" style="flex:1;min-width:280px;">
    <input id="sb_anon" placeholder="SUPABASE_ANON_KEY" style="flex:1;min-width:280px;">
  </div>
  <div class="row">
    <input id="email" placeholder="Email" style="flex:1;min-width:220px;">
    <button onclick="sendOtp()">Send OTP</button>
    <input id="otp" placeholder="OTP code" style="width:140px;">
    <button onclick="verifyOtp()">Verify</button>
  </div>
  <div class="muted">Save URL/Anon in browser localStorage. Token stays in memory.</div>
</div>

<div class="card">
  <h3>2) Add record</h3>
  <div class="row">
    <select id="category">
      <option value="student_management">student_management</option>
      <option value="real_estate">real_estate</option>
      <option value="legal_dispute">legal_dispute</option>
      <option value="health_habits">health_habits</option>
      <option value="life_notes">life_notes</option>
    </select>
    <input id="title" placeholder="Title (optional)" style="flex:1;min-width:260px;">
  </div>
  <textarea id="content" placeholder="Paste note / 상담 / 생각 / 대화 요약 원문"></textarea>
  <div class="row">
    <input id="tags" placeholder="tags comma-separated (optional)" style="flex:1;min-width:260px;">
    <button onclick="addRecord()">Add</button>
  </div>
  <div id="add_out" class="muted"></div>
</div>

<div class="card">
  <h3>3) Ask</h3>
  <div class="row">
    <input id="question" placeholder="Ask your brain..." style="flex:1;min-width:260px;">
    <button onclick="ask()">Ask</button>
  </div>
  <pre id="answer"></pre>
  <div id="sources" class="muted"></div>
</div>

<script>
let accessToken = null;

function lsGet(k){ try{return localStorage.getItem(k)||""}catch(e){return ""} }
function lsSet(k,v){ try{localStorage.setItem(k,v)}catch(e){} }

document.getElementById("sb_url").value = lsGet("SB_SUPABASE_URL");
document.getElementById("sb_anon").value = lsGet("SB_SUPABASE_ANON");

async function loadSupabase(){
  const url = document.getElementById("sb_url").value.trim();
  const anon = document.getElementById("sb_anon").value.trim();
  if(!url||!anon) throw new Error("Set SUPABASE_URL and SUPABASE_ANON_KEY");
  lsSet("SB_SUPABASE_URL", url); lsSet("SB_SUPABASE_ANON", anon);
  const { createClient } = await import("https://cdn.jsdelivr.net/npm/@supabase/supabase-js/+esm");
  return createClient(url, anon);
}

async function sendOtp(){
  const supabase = await loadSupabase();
  const email = document.getElementById("email").value.trim();
  if(!email) return alert("Email required");

  const { error } = await supabase.auth.signInWithOtp({
    email,
    options: { emailRedirectTo: window.location.origin } // ✅ 링크 클릭 후 Render로 돌아오게
  });

  if(error) return alert(error.message);
  alert("Magic link sent to email");
}

async function verifyOtp(){
  const supabase = await loadSupabase();
  const { data, error } = await supabase.auth.getSession();
  if(error) return alert(error.message);

  if(!data.session){
    alert("아직 로그인 세션이 없어요. 메일의 링크를 클릭하고, 이 페이지로 돌아온 다음 다시 눌러주세요.");
    return;
  }
  accessToken = data.session.access_token;
  alert("Signed in");
}
function apiBase(){
  return window.location.origin;
}

async function addRecord(){
  if(!accessToken) return alert("Sign in first");
  const category = document.getElementById("category").value;
  const title = document.getElementById("title").value.trim();
  const content = document.getElementById("content").value.trim();
  const tags = document.getElementById("tags").value.split(",").map(s=>s.trim()).filter(Boolean);
  if(!content) return alert("Content required");

  const res = await fetch(apiBase()+"/api/records", {
    method:"POST",
    headers:{ "Content-Type":"application/json", "Authorization":"Bearer "+accessToken },
    body: JSON.stringify({ category, title, content, tags })
  });
  const out = document.getElementById("add_out");
  const j = await res.json();
  if(!res.ok){ out.textContent = "Error: "+(j.detail||JSON.stringify(j)); return; }
  out.textContent = "Saved record: "+j.record_id+" (chunks: "+j.chunks+")";
}

async function ask(){
  if(!accessToken) return alert("Sign in first");
  const question = document.getElementById("question").value.trim();
  if(!question) return;
  document.getElementById("answer").textContent = "Thinking...";
  document.getElementById("sources").textContent = "";
  const res = await fetch(apiBase()+"/api/ask", {
    method:"POST",
    headers:{ "Content-Type":"application/json", "Authorization":"Bearer "+accessToken },
    body: JSON.stringify({ question, top_k: 8 })
  });
  const j = await res.json();
  if(!res.ok){
    document.getElementById("answer").textContent = "Error: "+(j.detail||JSON.stringify(j));
    return;
  }
  document.getElementById("answer").textContent = j.answer;
  document.getElementById("sources").textContent = "Retrieved chunks: "+j.retrieved;
}
</script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
def home():
    return HTMLResponse(WEB_APP_HTML)

@app.post("/api/records")
def api_add_record(request: Request, payload: Dict[str, Any]):
    _ensure_clients()
    token = _bearer(request)
    jwt_payload = _verify_jwt(token)
    user_id = jwt_payload["sub"]

    category = payload.get("category")
    content = (payload.get("content") or "").strip()
    title = (payload.get("title") or "").strip() or None
    tags = payload.get("tags") or []

    if not category or not content:
        raise HTTPException(status_code=400, detail="category and content required")

    # Insert record
    rec = {
        "user_id": user_id,
        "category": category,
        "title": title,
        "content": content,
        "tags": tags,
        "source": "manual",
    }
    ins = supabase_admin.table("records").insert(rec).execute()
    if not ins.data:
        raise HTTPException(status_code=500, detail="Failed to insert record")
    record_id = ins.data[0]["id"]

    # Chunking (simple, robust): split by paragraphs then cap length
    chunks: List[str] = []
    parts = [p.strip() for p in content.split("\n\n") if p.strip()]
    for p in parts:
        if len(p) <= 1200:
            chunks.append(p)
        else:
            # split long paragraphs
            for i in range(0, len(p), 1000):
                chunks.append(p[i:i+1000])

    rows = []
    for idx, ch in enumerate(chunks):
        emb = _embed(ch)
        rows.append({
            "record_id": record_id,
            "user_id": user_id,
            "chunk_index": idx,
            "chunk_text": ch,
            "embedding": emb,
        })

    if rows:
        supabase_admin.table("record_chunks").insert(rows).execute()

    supabase_admin.table("audit_logs").insert({
        "user_id": user_id,
        "action": "ADD_RECORD",
        "meta": {"record_id": record_id, "chunks": len(rows), "category": category},
    }).execute()

    return {"record_id": record_id, "chunks": len(rows)}

@app.post("/api/ask")
def api_ask(request: Request, payload: Dict[str, Any]):
    _ensure_clients()
    token = _bearer(request)
    jwt_payload = _verify_jwt(token)
    user_id = jwt_payload["sub"]

    question = (payload.get("question") or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="question required")

    top_k = int(payload.get("top_k") or 8)
    categories = payload.get("categories")  # optional list[str]

    q_emb = _embed(question)

    rpc = supabase_admin.rpc("match_chunks", {
        "in_query_embedding": q_emb,
        "in_user_id": user_id,
        "in_categories": categories,
        "in_match_count": top_k
    }).execute()

    retrieved = rpc.data or []
    context = "\n\n".join([f"[{i+1}] {r['chunk_text']}" for i, r in enumerate(retrieved)])

    system = (
        "You are Seungbin's extended brain. "
        "Use the retrieved context when relevant. "
        "If the context is insufficient, say what is missing and propose next steps."
    )

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": f"Retrieved context:\n{context}\n\nQuestion:\n{question}"}
    ]

    resp = openai_client.chat.completions.create(
        model=CHAT_MODEL,
        messages=messages,
    )

    answer = resp.choices[0].message.content

    supabase_admin.table("audit_logs").insert({
        "user_id": user_id,
        "action": "ASK",
        "meta": {"top_k": top_k, "categories": categories, "retrieved": len(retrieved)},
    }).execute()

    return {"answer": answer, "retrieved": len(retrieved)}
function parseHashToken(){
  const h = window.location.hash || "";
  if(!h.startsWith("#")) return null;
  const params = new URLSearchParams(h.slice(1));
  return {
    access_token: params.get("access_token"),
    refresh_token: params.get("refresh_token"),
    expires_in: params.get("expires_in"),
    token_type: params.get("token_type")
  };
}
(async () => {
  try {
    const supabase = await loadSupabase();

    // ✅ 1) hash에 access_token이 있으면 세션으로 저장
    const ht = parseHashToken();
    if (ht?.access_token && ht?.refresh_token) {
      const { data, error } = await supabase.auth.setSession({
        access_token: ht.access_token,
        refresh_token: ht.refresh_token
      });
      if (error) console.log("setSession error:", error);
      accessToken = (data?.session?.access_token) || ht.access_token;

      // 주소창 정리(선택): 토큰 숨기기
      window.history.replaceState({}, document.title, window.location.pathname);
      return;
    }

    // ✅ 2) 이미 저장된 세션이 있으면 가져오기
    const { data } = await supabase.auth.getSession();
    if (data?.session?.access_token) {
      accessToken = data.session.access_token;
    }
  } catch(e) {
    console.log(e);
  }
})();
