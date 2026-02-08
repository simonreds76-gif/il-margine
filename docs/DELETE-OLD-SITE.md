# Delete the old site (one-time cleanup)

The **old version** of the site comes from the **production** branch (commit 93e73da). To make sure it can never deploy again:

---

## 1. GitHub: delete the `production` branch

The **production** branch is protected, so only you can remove it:

1. Open your repo on **GitHub**.
2. Go to **Settings** → **Branches** (or **Branches** in the repo, then the branch list).
3. Find **production** in the list (or under **Branch protection rules**).
4. If there is a **protection rule** for `production`: edit it and **unprotect** / remove the rule (or allow deletion).
5. Then delete the branch:
   - Either: **Branches** → find **production** → trash icon (Delete).
   - Or from the command line (after unprotecting):
     ```bash
     git push origin --delete production
     ```

After this, the **production** branch no longer exists and nothing can deploy from it.

---

## 2. Vercel: stop using `production` and use golden

1. **Vercel** → your project → **Settings** → **Git**.
2. Set **Production Branch** to **`golden`** (not `main`, not `production`).  
   The **golden** branch points at commit **6c4057f**, which is the only source of truth.
3. (Optional) In **Deployments**, you can delete or ignore old deployments that were built from the **production** branch so you don’t accidentally promote them.

---

## 3. Done

- **Golden** = 6c4057f. All new work branches from this.
- **production** branch = removed; old site cannot come back from Git.
- **Vercel** = uses **golden** (6c4057f); you promote when you want the live site to change.
