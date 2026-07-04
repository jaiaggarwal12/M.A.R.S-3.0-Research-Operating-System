# M.A.R.S 4.0 — Web (Next.js)

Premium frontend for the M.A.R.S Research Operating System. Consumes the
existing FastAPI backend.

## Stack
Next.js 14 · TypeScript · Tailwind · Framer Motion · React Flow · Recharts · Lucide

## Local dev
```bash
cd web
npm install
npm run dev      # http://localhost:3000
```

The API URL defaults to the deployed backend. Override with an env var:
```bash
NEXT_PUBLIC_API_URL=https://mars-api-c0kv.onrender.com
```

## Deploy to Vercel (free, no card)
1. Push the repo to GitHub (already done)
2. Go to vercel.com → New Project → import the repo
3. Set **Root Directory** to `web`
4. Add environment variable:
   - `NEXT_PUBLIC_API_URL` = `https://mars-api-c0kv.onrender.com`
5. Deploy

## Pages
- `/` — landing page (hero, live stats, animated pipeline)
- `/dashboard` — command center
- `/dashboard/research` — research command interface + live pipeline + report reader
- `/dashboard/graph` — citation knowledge graph (React Flow)
- `/dashboard/memory` — research memory
- `/dashboard/arena` — hypothesis leaderboard + radar profile
- `/dashboard/warehouse` — experiment packages
- `/dashboard/reports`, `/dashboard/settings`
