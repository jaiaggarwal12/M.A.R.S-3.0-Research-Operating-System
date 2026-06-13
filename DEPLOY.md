# M.A.R.S 4.0 — Deployment Guide

## Option A: Render (recommended — free tier, Docker support)

### 1. Neo4j Aura (free cloud graph database)

1. Go to [neo4j.com/cloud/aura-free](https://neo4j.com/cloud/aura-free/)
2. Sign up → Create Free Instance
3. Copy your connection URI (looks like `neo4j+s://xxxxxxxx.databases.neo4j.io`)
4. Copy the auto-generated password (shown once — save it)

### 2. Push to GitHub

```bash
cd mars4
git init
git add .
git commit -m "M.A.R.S 4.0 initial"
git remote add origin https://github.com/YOUR_USERNAME/mars4.git
git push -u origin main
```

> Note: `.env` is in `.gitignore` — your secrets won't be committed.

### 3. Deploy on Render

#### FastAPI backend
1. Go to [render.com](https://render.com) → New → Web Service
2. Connect your GitHub repo
3. Settings:
   - **Name**: `mars-api`
   - **Runtime**: Docker
   - **Docker Command**: `python main.py --serve`
   - **Plan**: Free (or Starter for more RAM)
4. Environment Variables (click "Add from .env" or add manually):
   | Key | Value |
   |-----|-------|
   | `OPENAI_API_KEY` | `sk-proj-...` (your key) |
   | `NEO4J_URI` | `neo4j+s://xxxx.databases.neo4j.io` |
   | `NEO4J_USER` | `neo4j` |
   | `NEO4J_PASSWORD` | your Aura password |
   | `LLM_PROVIDER` | `openai` |
   | `OPENAI_MODEL` | `gpt-4o-mini` |
5. Click **Deploy**
6. Your API will be live at: `https://mars-api.onrender.com`

#### Gradio UI (optional second service)
1. New → Web Service → same repo
2. Settings:
   - **Name**: `mars-ui`
   - **Docker Command**: `python main.py --ui`
3. Same environment variables as above
4. Live at: `https://mars-ui.onrender.com`

---

## Option B: Railway (one-click, faster cold starts)

1. Go to [railway.app](https://railway.app) → New Project → Deploy from GitHub
2. Select repo → Railway auto-detects `railway.toml`
3. Add environment variables in the Railway dashboard (same as above)
4. Done — Railway gives you a public URL immediately

---

## Option C: Local Docker Compose (full stack)

```bash
# Copy env and fill in your OpenAI key
cp .env.example .env
# Edit .env — OPENAI_API_KEY is already set if you used the deploy script

# Build and start everything (Neo4j + API + UI)
docker-compose up --build

# Services:
#   FastAPI:  http://localhost:8000
#   Gradio:   http://localhost:7860
#   Neo4j:    http://localhost:7474  (browser UI)
```

---

## Environment Variables Reference

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | ✅ | Your OpenAI key |
| `NEO4J_URI` | ✅ for graph | Aura URI or `bolt://neo4j:7687` for local |
| `NEO4J_PASSWORD` | ✅ for graph | Aura password |
| `LLM_PROVIDER` | optional | `openai` (default) |
| `OPENAI_MODEL` | optional | `gpt-4o-mini` (default) |
| `MAX_PAPERS_PER_QUERY` | optional | `50` recommended for free tier |
| `AUTO_LOOP_ENABLED` | optional | `false` (keep off for free tier) |

---

## Notes

- **Neo4j is optional** — if connection fails the app falls back to NetworkX in-memory graph (still fully functional, just no persistence)
- **Free tier memory**: Set `MAX_PAPERS_PER_QUERY=50` and `MAX_LOOP_ITERATIONS=3` on free plans
- **Cold starts**: Render free tier sleeps after 15 min inactivity — upgrade to Starter ($7/mo) for always-on
- **Data persistence**: Use Render Disks or mount a volume for `/app/data` to persist FAISS index and memory DB across deploys
