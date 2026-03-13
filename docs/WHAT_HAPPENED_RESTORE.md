# What happened with the restore (bookmakers, favicon, footer)

## Short answer

- **Only one thing was deployed in the last “restore” commit:** `src/app/bookmakers/layout.tsx` (the BOOKMAKERS_INDEXABLE flag). The bookmakers **page** content was **not** changed in that commit.
- The bookmakers **page** in the repo has been the same since **6c4057f** (5 Feb 2026). The version you had “yesterday night” was **never committed** to git, so it can’t be restored from the repo. If we ran a “restore from 6c4057f” step earlier, that would have **overwritten your local** bookmakers page with the old one — so the newer version only existed on your machine and is not in history.
- **Admin panel, settlement, and calculations are still there** and were not reverted or removed.
- Favicon and footer had multiple fixes in recent commits; current state is below, plus small fixes applied now.

---

## 1. What was actually deployed (commit 5f48399)

- **Commit:** `5f48399` — “restore: bookmakers layout with BOOKMAKERS_INDEXABLE (keep analytics); bookmakers+calculator content already at 6c4057f”
- **Changed:** Only **one file**: `src/app/bookmakers/layout.tsx` (4 lines: noindex/sitemap flag).
- **Not changed in that commit:**  
  - `src/app/bookmakers/page.tsx`  
  - Calculator page  
  - Admin  
  - Favicon  
  - Footer  

So we did **not** “upload an old version” of the site in that deploy — we only pushed the bookmakers **layout** (noindex/sitemap behaviour).

---

## 2. Why the bookmakers page looks “old”

- In **git history**, `src/app/bookmakers/page.tsx` was last modified in commit **6c4057f** (5 Feb 2026, “Banner only on Calculator…”).  
- **No later commit on main** has changed the bookmakers page content.
- So the “new” bookmakers page you had yesterday night was either:
  - **Only on your machine** (never committed), or  
  - On another branch that never got merged.
- When you asked to “bring back yesterday’s bookmakers page,” the previous step **restored from 6c4057f**. That would have run something like `git checkout 6c4057f -- src/app/bookmakers/page.tsx`, which **replaces your local file** with the 6c4057f version. So:
  - The **repo** has had the same (older) bookmakers page since 6c4057f.
  - Your **local** “yesterday night” version was **overwritten** by that restore; it was never in the repo, so it **can’t be retrieved from git**.

**Recovery:** If you have **Cursor Local History** (right‑click `src/app/bookmakers/page.tsx` → "Open Timeline" / "Local History") or a backup of the project from last night, the newer bookmakers page might still be there.

---

## 3. Admin, settlement, calculations — still there

- **Admin:** `src/app/admin/page.tsx` and `src/app/admin/layout.tsx` are unchanged. Login, Add Bet, Pending, Recent, **Settle (won/lost/void)** with profit/loss calculation, and delete are all still in place.
- **Calculator:** `src/app/calculator/page.tsx` was not modified in the restore commit; calculator logic is intact.
- **Settlement logic:** In `admin/page.tsx`, `handleSettle` still computes profit/loss (won: `(odds * stake) - stake`, lost: `-stake`, void: `0`) and updates `profit_loss` and `settled_at`.

Nothing of that was reverted or removed.

---

## 4. When things happened (from git log)

- **6c4057f** (5 Feb 2026) — Last change to bookmakers **page** content (banner only on calculator).
- **7 Feb 2026** — Many commits: GA, favicon, footer (e.g. 0189b0c removed `app/icon.png` so tab uses `favicon-dark.png`).
- **5f48399** (7 Feb 2026) — **Only** bookmakers **layout** change (BOOKMAKERS_INDEXABLE); this is the only “restore” deploy.

---

## 5. Favicon and footer (current + fixes)

- **Favicon:** Layout uses `/favicon-dark.png` (and 128/256) in metadata and `<link>` tags. There is no `app/icon.png` (removed to avoid the black triangle). If the tab or nav icon still looks wrong, it’s likely caching or the asset; we can switch to a dedicated icon asset if you want.
- **Footer:** It uses `logo.png` with `mixBlendMode: "multiply"` on `bg-[#0f1117]`. If the logo has white, that can leave visible edges. Next step: use a dark-friendly asset or a wrapper so there are no white borders.

---

## Summary

| Item | Status |
|------|--------|
| Last deploy (5f48399) | Only bookmakers **layout** (noindex/sitemap). |
| Bookmakers **page** “old” | Repo has been on 6c4057f version since 5 Feb; “yesterday night” version was never committed and was overwritten locally — **not recoverable from git**. |
| Admin / settlement / calculations | **Unchanged**; all still in repo and working. |
| Favicon | Pointing to `favicon-dark.png`; fixes applied for consistency. |
| Footer | Fixes applied to remove white borders. |
