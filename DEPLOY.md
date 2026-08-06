# Redeploying Avenoir to Render and Vercel

Both hosts already exist and both auto-deploy from `main`. The v2 work lives on
`v2-industry-engine`, which neither host watches, so **nothing goes live until
`main` moves.** That is the whole job.

---

## The short version

```bash
cd /Users/mihirsingla/Desktop/avenoir && git checkout main && git merge --ff-only v2-industry-engine && git push origin main
```

Render and Vercel both pick that up automatically. Backend takes ~3 to 5
minutes, frontend ~2. Nothing to click in either dashboard.

---

## The careful version, which is what I would do the night before a meeting

### 1. Tag the working v1 first, so it stays reachable

If tomorrow goes sideways you want a one-command way back to the version you
already demoed.

```bash
git tag v1-demo b65fcb4 && git push origin v1-demo
```

### 2. Push the branch and check it against the real backend

This gives you a Vercel preview URL without touching the live site.

```bash
git push -u origin v2-industry-engine
```

Vercel builds it as a **Preview** deployment and comments the URL on the
commit, or you can find it under Deployments in the Vercel dashboard. Render
ignores the branch entirely, so the preview will talk to your existing
production backend, which is still running v1. Expect the frontend to fail
against it: v1 has no `/showcase`, no `/industries` entity questions, and no
`decision_costs`. That is a real check that you are looking at new code, not a
problem to fix.

If you would rather see the whole thing working end to end before merging, skip
the preview and go straight to step 3. The full stack only agrees with itself
once both sides are on v2.

### 3. Merge and push

```bash
git checkout main && git merge --ff-only v2-industry-engine && git push origin main
```

`--ff-only` is deliberate. `main` is an ancestor of the v2 branch, so this is a
fast-forward with zero conflicts. If git refuses, something has changed on the
remote and you should stop and look rather than forcing it.

### 4. Watch the two builds

**Render** (backend): dashboard → `avenoir-api` → Events. Wait for "Deploy
live". If the build fails, it is almost always a dependency: `requirements.txt`
pins numpy 2.3.5 and scipy 1.16.3, and `PYTHON_VERSION` is pinned to 3.12 in
`render.yaml`. Do not let either float, the whole calibration depends on the
pinned scipy.

**Vercel** (frontend): dashboard → project → Deployments. Wait for Ready.

### 5. Verify, in this order

```bash
curl -s https://YOUR-RENDER-URL.onrender.com/ | head -c 400
```

You want `"status":"ok"` and `"industries":5`. Then:

```bash
curl -s -o /dev/null -w "%{http_code} in %{time_total}s\n" https://YOUR-RENDER-URL.onrender.com/showcase
```

First call takes ~5 seconds because it computes all five industries, then it is
cached for the life of the process and returns in milliseconds. If this 404s,
Render is still serving old code.

Then open the site and check three things:

1. The landing hero shows five industry tabs and a cost slider, not a tariff slider.
2. `/intake` shows "Have the paperwork already? Upload it instead." above the form.
3. A decision card on `/dashboard` has a "change" link next to "our cost estimate".

If all three are there, v2 is live.

---

## The two things that actually bite

**`NEXT_PUBLIC_API_URL` must point at Render.** In Vercel: Settings →
Environment Variables. It should be your Render URL, e.g.
`https://avenoir-api.onrender.com`, with no trailing slash. This is baked in at
**build** time, not read at runtime, so if you change it you must redeploy for
it to take effect. Saving it alone does nothing.

**Render's free tier sleeps.** After ~15 minutes idle the service spins down,
and the next request takes 30 to 60 seconds to wake it. During that window the
site looks broken. Before any demo, load the page a couple of minutes early, or
hit the health endpoint:

```bash
curl -s -o /dev/null -w "awake in %{time_total}s\n" https://YOUR-RENDER-URL.onrender.com/
```

If you want this to stop being a risk, upgrade that one service to Render's
paid Starter tier. It is the single highest-value $7 you can spend on this
project before a sales meeting.

---

## Environment variables, in full

**Render** (`avenoir-api`):

| Key | Value | Notes |
|---|---|---|
| `ANTHROPIC_API_KEY` | your key | Set manually. `render.yaml` marks it `sync:false` so it is never in git. |
| `ANTHROPIC_MODEL` | `claude-sonnet-5` | Already in `render.yaml`. |
| `PYTHON_VERSION` | `3.12` | Already in `render.yaml`. Do not raise it. |

**Vercel** (frontend):

| Key | Value | Notes |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | your Render URL | Build-time. Redeploy after changing. |

No new variables are needed for v2. If `ANTHROPIC_API_KEY` is missing the app
still runs end to end: narratives fall back to deterministic text and document
extraction degrades to filename and keyword matching. The upload panel says so
on screen when that happens.

---

## Rolling back

```bash
git checkout main && git reset --hard v1-demo && git push --force-with-lease origin main
```

Or, faster and without touching git: in Vercel, Deployments → the previous
deployment → Promote to Production. Render has the same under Events → Rollback.
Use the dashboards if you are in a hurry, git if you want it to stay rolled back.
