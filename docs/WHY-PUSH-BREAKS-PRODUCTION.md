# Why the site reverted (and how to prevent it)

## What was happening

1. The **production** branch on GitHub pointed to commit **93e73da** (old “full” site: Contact, Cookies, Footer, GA, etc.).
2. **Vercel** was set to use **Production Branch = production** (or builds from that branch could be promoted).
3. So whenever that branch was built or promoted, the **old site** (93e73da) went live instead of the golden version (6c4057f).
4. Pushing to **main** or other branches could also trigger builds; depending on Vercel config, the “current” production branch or latest build could overwrite what you wanted.

## Fix (what we did and what you should do)

1. **Golden is the only source of truth:** commit **6c4057f**. All new work branches from it.
2. **`vercel.json`** can disable deployments from `main` so pushes don’t auto-update Production. You promote manually in Vercel.
3. **Remove the old site from the repo:** the **production** branch (93e73da) must be **deleted** on GitHub so nothing can deploy from it:
   - GitHub → repo → **Settings** → **Branches** → find **production** → **Unprotect** (if protected), then delete the branch (or use **Branches** list → delete **production**).
4. **Vercel:** set **Production Branch** to **`golden`** (which points at 6c4057f). Do not use **production**. Optionally delete or ignore old deployments that were built from **production**.
5. From now on: work on feature branches from 6c4057f; open PRs; you merge and **promote in Vercel** when you want the live site to change. No automatic deploy from the old **production** branch.

## Summary

- **Old site** = anything built from the **production** branch (93e73da). Delete that branch on GitHub and stop using it in Vercel.
- **New/golden site** = 6c4057f only. Use branch **golden** (or equivalent) in Vercel as Production Branch and promote deployments built from 6c4057f.
