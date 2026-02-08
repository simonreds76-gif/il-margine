# If the site reverts to the old / wrong version

**Do not push new code first.** Recover using the steps below.

---

## Step 1: Restore Production in Vercel (fastest)

1. Go to **Vercel** → your project → **Deployments**.
2. Find the deployment built from commit **6c4057f** (golden).
3. Open that deployment → **Promote to Production**.
4. Check the live site. If it’s correct, stop here.

---

## Step 2: Ensure Vercel is not using the old branch

- **Golden commit (only source of truth):** `6c4057f`.
- The old site came from the **production** branch (commit 93e73da). That branch should be **deleted** on GitHub so it can never deploy again.
- In **Vercel** → **Settings** → **Git** → **Production Branch**: set to **`golden`** (or **`main`** only if you keep main at 6c4057f). **Do not** use **`production`** — that branch is the old version.

---

## Step 3: If the right deployment is gone

1. In the repo:
   ```bash
   git fetch --all --prune
   git checkout main
   git reset --hard 6c4057f
   ```
   Do **not** push to main unless you explicitly want to. Branch from 6c4057f for work; promote in Vercel from a deployment of 6c4057f or your feature branch.

2. In Vercel: deploy from the **golden** branch (or a tag at 6c4057f), then **Promote that deployment to Production**.

---

## For agents

- Golden commit: **6c4057f** only. Do not use 93e73da or the **production** branch.
- Do not push to main unless the user explicitly asks (e.g. to fast-forward after merging a PR).
