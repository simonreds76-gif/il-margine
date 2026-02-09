/**
 * Vercel "Ignored Build Step" script.
 * Exit 0 = build, exit 1 = skip build.
 * Use in Vercel: Project Settings → Git → Ignored Build Step:
 *   node scripts/vercel-ignore-main.cjs
 * This ensures the `main` branch never triggers a build (preview or production).
 */
const ref = process.env.VERCEL_GIT_COMMIT_REF || "";
const isMain = ref === "main";
process.exit(isMain ? 1 : 0);
