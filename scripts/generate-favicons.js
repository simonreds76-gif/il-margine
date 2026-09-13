// Preserve the supplied artwork including white detail. Generate every size consistently.
import('./build-site-brand-assets.mjs').catch(error => {
  console.error(error);
  process.exitCode = 1;
});