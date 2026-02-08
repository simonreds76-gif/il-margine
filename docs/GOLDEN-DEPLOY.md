# Golden production (single source of truth)

**Golden commit:** `6c4057f`  
**Message:** "Banner only on Calculator, at bottom of page; remove from all other pages"

**Rules:**
- All work branches from this commit. Do not use any other commit or branch as “production” source.
- In **Vercel** → **Settings** → **Git** → **Production Branch**: use **`golden`** (or a branch that points at 6c4057f). **Do not** use the **`production`** branch — it points at the old site (93e73da) and must be removed.
- To realign local main to golden (do not push unless user asks):
  ```bash
  git fetch --all --prune
  git checkout main
  git reset --hard 6c4057f
  ```
- To deploy the golden site: in Vercel, promote a deployment that was built from **6c4057f** (e.g. from the **golden** branch).
