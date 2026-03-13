# Full summary: what’s been happening today (for ChatGPT / solution request)

## Project context

- **Site:** il-margine (ilmargine.bet) – Next.js betting tips site.
- **Hosting:** Vercel (connected to GitHub).
- **Repo:** GitHub, single branch `main`. Pushing to `main` triggers a Vercel build; that build is treated as the latest “Production” deployment and can overwrite what’s currently live.

---

## What the “golden” version is

There is **one deployment on Vercel** that shows the **correct** site. The user calls it the “golden” version. When they **manually promote that deployment to Production** in Vercel, the live site (ilmargine.bet) looks right.

**What “correct” means:**
- Branding: “Betting with Mathematical Edge”, banner.png, Contact + Cookies in footer, “Launched 2026”.
- Google Analytics (gtag) in the layout.
- Bookmakers page: noindex, excluded from sitemap when not indexable.
- The user has a specific deployment they like; they said it’s a “redeploy of **88JkoCtqN**” (Vercel deployment ID).

So: **the golden version exists as a Vercel deployment.** The user can see it in Vercel’s deployment list and can promote it to Production. When they do, the live site is correct.

---

## The problem: we “can’t find” the golden one in a way that survives pushes

- **In the repo:** We identified a commit that *should* match the golden deployment: **93e73da** (“chore: trigger Vercel deploy - restore full site (Contact, Cookies, Footer, GA)”). The *source code* at 93e73da has the right layout, GA, footer, etc. So in theory, a build from 93e73da should produce the same site as the golden deployment.
- **In practice:** Every time we (or the user) **push to `main`** – whether we push 93e73da again, or 93e73da plus small changes (e.g. CSP, Coral logo fix, X-Robots-Tag) – Vercel builds that commit and that **new** build ends up as Production (or overwrites it). That **new** build consistently shows the **wrong** (“old” / “shitty”) version: different branding, wrong layout, or wrong content.
- So we “can’t find” the golden version in the sense that **we cannot get a new Vercel build from the repo that looks like the golden deployment.** The golden deployment is an *existing* build in Vercel. We don’t know why building the same (or very similar) code again produces a different, wrong result – possible causes: build cache, environment variables at build time, Node/Next version, or something else in Vercel’s pipeline. We have no access to Vercel build logs or dashboard to confirm.
- **Recovery so far:** The only reliable fix has been: in Vercel, find the golden deployment in the list and **Promote to Production** again. That restores the good site but doesn’t fix the underlying issue (next push will break it again).

---

## Timeline of what happened today (simplified)

1. **Initial state:** User had been fighting “old” vs “good” version for a while. They had a “golden” deployment they liked.
2. **Wrong “golden” commit:** We were told the golden commit was **6c4057f**. We reset `main` to 6c4057f and force-pushed. That did not match the good site – 6c4057f was an older version (different layout, no Contact/Cookies, etc.).
3. **User shared the good deployment URL and HTML:** They pasted HTML from the deployment that looks correct. From that we saw: “Betting with Mathematical Edge”, banner.png, Contact/Cookies footer, favicon-dark, etc. That matched the *code* at a **later** commit, **93e73da**, not 6c4057f.
4. **We aligned repo to 93e73da:** We set `main` to 93e73da and force-pushed. We updated docs so the “golden” commit is 93e73da and the deployment reference is 88JkoCtqN.
5. **Pushes kept breaking Production:** Whenever we (or the user) pushed to `main` – e.g. adding Google Analytics fixes, CSP, Coral logo fallback, X-Robots-Tag – Vercel built that commit and the **new** build became Production (or overwrote it). Each time, the **live site reverted to the “shitty” version.** So: push → new build → Production shows wrong version. The user had to go back to Vercel and **Promote the golden deployment** again to restore the good site. This happened many times (user said ~15 attempts).
6. **Rule: don’t push:** We added Cursor rules and docs saying: do not push to `main`; the user deploys. The idea was to stop triggering new builds so Production would stay on the promoted golden deployment.
7. **User asked to push again:** They said they had the golden version locally and asked to apply analytics fixes and push. We re-applied CSP, X-Robots-Tag, Coral logo fallback, committed, and pushed. **Again** the site reverted to the shitty version. We reverted the push (reset `main` back to 93e73da and force-pushed) and told the user to re-promote the golden deployment.
8. **Attempted fix: stop builds from main:** We added **vercel.json** with `"git": { "deploymentEnabled": { "main": false } }` so that **pushes to `main` should no longer create a Vercel deployment.** That file is in the repo but has **not** been pushed yet (to avoid triggering one more build). So currently: local repo has vercel.json; GitHub main is at 93e73da without vercel.json. If we push vercel.json, that might trigger one last build and overwrite Production again; after that, future pushes to main would not trigger builds.

---

## Current state

- **GitHub `main`:** At commit **93e73da**. No vercel.json on GitHub.
- **Local repo:** 93e73da plus **uncommitted** files: `vercel.json`, `docs/` (including WHY-PUSH-BREAKS-PRODUCTION.md, RECOVERY-IF-SITE-REVERTS.md, site-stats-snapshot.md, GOLDEN-DEPLOY.md, this summary), and other untracked files.
- **Vercel:** The user has to **manually promote** the golden deployment (e.g. 88JkoCtqN or the one that shows the correct site) to Production whenever it gets overwritten. The “latest” deployment on Vercel (from the last push) is the one that shows the wrong version; the **golden** one is an older deployment in the list that they have to find and promote.
- **Google Analytics:** The code at 93e73da includes GA (gtag in layout, GoogleAnalytics component). The user said analytics show 0 users; possible reasons: the *live* site might be serving a build that didn’t have the GA env var set, or the build that’s live is from an older commit that doesn’t include GA. So even though the “golden” deployment looks right visually, GA might not be firing on it, or the live site might not be the golden one at the moment.
- **Stats (bets, ROI, etc.):** The site shows “baseline” (in code) + database. We have a **site-stats-snapshot.md** with the combined numbers the user wants. The AI has no access to the database; only the repo and that snapshot.

---

## What we need from you (ChatGPT)

We need a **clear, step-by-step solution** that either:

**A) A newbie (non-technical user) can follow**  
- Using only: Vercel dashboard, GitHub website, and maybe one or two simple commands (e.g. run a script or a single git command) if necessary.  
- Goal: So that (1) the live site stays on the golden version and doesn’t revert when someone pushes to `main`, and (2) they can update the live site in a controlled way when they want (e.g. after testing a preview).

**B) Or instructions to give to the AI agent (Cursor)**  
- So the agent can execute the steps (edits, git, config) without pushing in a way that overwrites Production with a bad build.  
- And so that in the future, “push to main” does not change what’s live; only an explicit action (e.g. promote a specific deployment, or deploy from a different branch) updates Production.

**Constraints:**
- We cannot rely on “just push the right code” – every push so far has resulted in a build that shows the wrong version. So the solution must either stop automatic Production updates from `main`, or use a different branch/workflow so that Production only updates when the user (or agent) explicitly deploys a known-good build.
- The user can see and promote the golden deployment in Vercel; we need to preserve that and avoid overwriting it.
- The repo is on GitHub; Vercel is connected to that repo. We have added `vercel.json` with `deploymentEnabled: { "main": false }` locally but not pushed it yet.

Please provide:
1. **Explanation** of why a new build from the same/similar code might show a different (wrong) version (e.g. cache, env, build order), in 1–2 short paragraphs.
2. **Step-by-step instructions** (for the newbie or for the agent) to make the live site stable and to control when Production updates, including:
   - What to do in Vercel (e.g. promote golden deployment now; change Production branch; any other settings).
   - Whether and how to use the existing `vercel.json` (push it or not; any change to it).
   - How to deploy or update the site in the future without triggering the “wrong” build (e.g. only promote specific deployments, or use a “production” branch and how to update it).
3. **How to get Google Analytics working** on the live site without causing the wrong version to appear (e.g. ensure the golden deployment was built with the right env var, or how to add GA in a way that doesn’t rely on a new build from main overwriting Production).

Thank you.
