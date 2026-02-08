# Preview shows old site even when Source is 793003e

If the deployment **Source** is commit **793003e** (golden + Speed Insights) but the preview **still shows the old website**, the build is correct but something in Vercel or the URL is wrong. Follow these in order.

---

## 1. Confirm what you’re actually seeing

On the **preview URL** (the one that looks “old”):

- **Right‑click → View Page Source** (or Ctrl+U).
- In the source, search for:
  - **`data-build="golden-793003e"`**  
    - If you **see** it: the HTML is from our build. The “old” look may be cache or a different page.
  - **`Contact`** or **`/contact`** or **`Cookies`** or **`/cookies-policy`** in the footer area.  
    - Golden has **Disclaimer** and **Privacy Policy** only.  
    - If you see **Contact** / **Cookies** links in the footer HTML, that HTML is **not** from 793003e (golden). So the response isn’t from this deployment.

---

## 2. Root Directory (most likely cause)

Vercel can build from a **subfolder** of the repo. If that’s set, you get different code and the “old” site.

1. **Vercel** → your project → **Settings**.
2. Open **General** (or **Build and development**).
3. Find **Root Directory**.
4. It **must be empty** (or `.`). If it shows **any** path (e.g. `app`, `frontend`, `il-margine`), **clear it** and leave it blank.
5. **Save**.
6. Go to **Deployments** → open deployment **793003e** → **⋯ → Redeploy**.
7. **Uncheck** “Use existing build cache”, then redeploy.
8. When the new deployment is ready, open **its** “Visit” URL (from that deployment card, not an old one). Check again.

---

## 3. Use the exact deployment URL

Preview URLs can be branch-based and point to “latest” for that branch. To be sure you’re on 793003e:

1. **Deployments** → find the row where **Source** is **793003e** (and branch `speed-insights-golden`).
2. Click that deployment (or **Visit** on that row).
3. Use **that** URL in the browser. Don’t use an old bookmark or a generic preview link.
4. Hard refresh (Ctrl+Shift+R) or open in **Incognito**.

---

## 4. New Vercel project (bypass old config)

If Root Directory is already empty and you still see the old site on the 793003e deployment URL:

1. **Vercel Dashboard** → **Add New… → Project**.
2. **Import** the **same** Git repo (e.g. `simonreds76-gif/il-margine`).
3. When asked which branch to deploy, choose **speed-insights-golden** (or leave default and change after).
4. **Do not** copy env vars from the old project yet.
5. Deploy. Wait for the build to finish.
6. Open the **new project’s** deployment URL.

- If the **new** project shows the **golden** site: the old project has a wrong setting (Root Directory, env, or something else). You can then move env vars and point the domain to the new project.
- If the **new** project also shows the old site: then either the repo at 793003e isn’t what we think, or there’s another cause (e.g. CDN). In that case, “View Page Source” (step 1) is essential: check for `data-build="golden-793003e"` and Contact/Cookies in the footer.

---

## 5. Summary

- **View Source** → look for `data-build="golden-793003e"` and for Contact/Cookies in the footer.
- **Root Directory** → must be empty; clear it, save, redeploy 793003e without cache, then open that deployment’s Visit URL.
- **URL** → use the “Visit” link from the 793003e deployment row, not an old or generic preview URL.
- **New project** → if it still happens, deploy the same branch in a new Vercel project and compare.
