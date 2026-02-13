# Seungbin Brain v1 (Render + Supabase)

## 1) Supabase
- Run schema.sql in SQL Editor
- Enable Email OTP in Authentication settings
- Get:
  - SUPABASE_URL
  - SUPABASE_ANON_KEY (for web UI)
  - SUPABASE_SERVICE_ROLE_KEY (for server)
  - SUPABASE_JWT_SECRET (for server)

## 2) Render
Start command:
uvicorn brain_server:app --host 0.0.0.0 --port 10000

Env vars:
OPENAI_API_KEY
SUPABASE_URL
SUPABASE_SERVICE_ROLE_KEY
SUPABASE_JWT_SECRET
CHAT_MODEL=gpt-4.1
EMBEDDING_MODEL=text-embedding-3-small
