# Avenoir

**Risk, priced in dollars. Not "High." Not a color.**

Enterprise risk quantification for mid-market industrial equipment distributors.
Every risk is a seeded, deterministic simulation, reported as an expected value
**with an honest range**, and the cross-domain composite shows how much worse
your risks are *together* than apart. The AI selects models and interprets
results; it never writes the math and never invents a figure.

- `backend/` FastAPI + LangGraph over a validated numpy model library (the numbers)
- `frontend/` Next.js 14 + Tailwind + Recharts (the interface)

---

## Run locally

**Backend** (Python 3.11+):

```bash
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # optional: add your ANTHROPIC_API_KEY for live AI
uvicorn main:app --port 8000
```

Runs at http://localhost:8000. Works without an API key (deterministic fallback
narratives); add the key for live AI interpretation.

**Frontend** (Node 18+):

```bash
cd frontend
npm install
cp .env.example .env.local    # NEXT_PUBLIC_API_URL defaults to localhost:8000
npm run dev
```

Open http://localhost:3000.

Tests: `cd backend && python3 tests/test_models.py` (and `test_composite`,
`test_documents`, `test_graph`).

---

## Deploy (so investors can click around)

Two free services: **Render** for the API, **Vercel** for the site.

### 1. Push to GitHub

```bash
git init && git add -A && git commit -m "Avenoir"
# create an empty repo at github.com/new, then:
git remote add origin https://github.com/<you>/avenoir.git
git branch -M main && git push -u origin main
```

### 2. Backend on Render

1. render.com > **New +** > **Blueprint** > connect the repo. Render reads
   `render.yaml` and provisions the `avenoir-api` service automatically.
2. In the service's **Environment** tab, add `ANTHROPIC_API_KEY` (your key).
3. Deploy. Note the URL, e.g. `https://avenoir-api.onrender.com`.

> Render's free tier sleeps after ~15 min idle, so the first request after a
> nap takes ~30s to wake. For a live investor demo, either hit the URL once to
> warm it, or use a paid instance.

### 3. Frontend on Vercel

1. vercel.com > **Add New** > **Project** > import the repo.
2. Set **Root Directory** to `frontend`.
3. Add env var `NEXT_PUBLIC_API_URL` = your Render URL from step 2.
4. Deploy. You get a public URL like `https://avenoir.vercel.app`.

### 4. Point your QR code at the Vercel URL

A QR code only works if it encodes the **public** Vercel URL (not `localhost`,
which only resolves on your own machine). Regenerate the QR from the deployed
`https://…vercel.app` link and it will work for anyone.

---

## The trust rules (why the numbers are defensible)

1. The LLM never writes simulation code at runtime; validated Python computes every number.
2. Every model is deterministic (seeded); same inputs give byte-identical outputs.
3. Every result carries a central estimate **and** a range, never a bare point estimate.
4. Every result is traceable to its model, version, and seed (see `/methodology`).
5. The AI interprets; it never invents figures.

See `/methodology` on the running site for every model's method, assumptions,
and tracked accuracy, generated live from the API.
