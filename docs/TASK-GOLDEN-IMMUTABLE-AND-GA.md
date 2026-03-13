# TASK: Golden immutable + no overwrites + GA working

Follow in order. Do **0–4** first (Vercel + GitHub). Then **5** (GA). Then **6** (vercel.json) only after Production Branch is `production`.

---

## 0) Context

- **Golden Production** = built from commit **6c4057f** on branch `main` (message: “Banner only on Calculator…”).
- Any new build/push has been overwriting it with a wrong version. This task stops that and adds GA safely.

---

## 1) Freeze Production (Vercel UI)

1. Open project **ilmargine** in Vercel.
2. **Settings** → **Git**.
3. Find **Production Branch**.
4. Change from **main** to **production**.
5. **Save**.

**Result:** Pushes to `main` → Preview only. Only pushes to `production` can change Production.

---

## 2) Create `production` branch (GitHub web)

1. Open repo: **github.com/simonreds76-gif/il-margine**.
2. Branch dropdown (says **main**).
3. Type **production** → **Create branch: production from main**.
4. Do **not** push other changes to `production` yet.

---

## 3) Protect `production` (GitHub)

1. **Settings** → **Branches** → **Add branch protection rule**.
2. **Branch name pattern:** `production`.
3. Enable **Require a pull request before merging** (and optionally restrict who can push).
4. Save.

---

## 4) Keep golden live (Vercel)

1. **Vercel** → **Deployments**.
2. Find the **good** deployment (built from **6c4057f**).
3. If it’s not already Production → **Promote to Production**.

After 1–3, pushes to `main` will **not** replace Production.

---

## 5) Google Analytics (env var + safe redeploy)

### 5A) Environment variable (Vercel)

1. **Vercel** → **Settings** → **Environment Variables**.
2. **Add:**
   - **Name:** `NEXT_PUBLIC_GA_MEASUREMENT_ID`  
     (This is the name used in the code: `src/lib/config.ts`.)
   - **Value:** Your GA4 ID, e.g. `G-XXXXXXXXXX` (or `G-YGYZH8K072` if that’s your property).
   - **Environment:** Production (and Preview if you want).
3. **Save.**

### 5B) Safe redeploy (no push)

1. In **Deployments**, open the **golden** deployment (6c4057f).
2. Click **Redeploy** (same commit, but rebuilds with new env vars).
3. When it’s done, open the **redeploy URL** and check:
   - Site still looks like the golden version.
   - GA fires: **Chrome DevTools** → **Network** → filter by `collect` or `gtag`; or use GA **DebugView**.
4. If both good → **Promote to Production** for that redeploy.

This way GA is enabled without pushing new code.

---

## 6) Optional: deploy kill switch for `main` (only after 1–3)

After **Production Branch** is set to **production** in Vercel:

1. In the repo, ensure **vercel.json** at root contains:
   ```json
   {
     "$schema": "https://openapi.vercel.sh/vercel.json",
     "git": {
       "deploymentEnabled": {
         "main": false
       }
     }
   }
   ```
2. Commit to **main** and push.

**Note:** This file already exists locally with that content. Commit and push only after step 1 is done so Production is already frozen.

---

## 7) Report back (proof)

- [ ] Vercel **Production Branch** = **production** (screenshot or text).
- [ ] GitHub: branch **production** exists + protection rule on.
- [ ] GA env var: **NEXT_PUBLIC_GA_MEASUREMENT_ID** set; GA firing (Network/DebugView).
- [ ] Production is still the golden site (6c4057f).

---

## Code reference (GA)

- **Env var:** `NEXT_PUBLIC_GA_MEASUREMENT_ID`
- **Used in:** `src/lib/config.ts` → `GA_MEASUREMENT_ID`
- **Fallback in code:** `G-YGYZH8K072` (if env not set). Prefer setting the env var in Vercel.
