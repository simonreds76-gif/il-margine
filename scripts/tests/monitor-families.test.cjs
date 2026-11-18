const { test } = require("node:test");
const assert = require("node:assert/strict");
const { monitorFamilies } = require("../../src/lib/monitor-families.ts");

test("all supplied records occur once, including new IDs and overlapping paper cohorts", () => {
  const rows = [
    ["strict", "Tennis match markets"], ["props", "Tennis props"], ["props-wta", "Tennis props"],
    ["ace-compass-control", "Tennis research"], ["ace-compass-dispersion-all-control", "Ace Compass paper comparison"],
    ["gk-half-reference", "Football research"], ["most-aces-reference-direct-fixed", "Tennis research"],
    ["most-aces-single-count", "Tennis research"], ["new-arm", "New market"],
  ].map(([id, group]) => ({id, group}));
  const families = monitorFamilies(rows);
  assert.deepEqual(families.flatMap(f => f.rows.map(r => r.id)).sort(), rows.map(r => r.id).sort());
  const byId = Object.fromEntries(families.map(f => [f.id, f]));
  assert.equal(byId.compass.rows.length, 2);
  assert.equal(byId["most-aces"].rows.length, 2);
  assert.equal(byId.props.rows.length, 2);
  assert.equal(byId.keepers.rows[0].id, "gk-half-reference");
  assert.equal(byId.other.rows[0].id, "new-arm");
  assert.ok(byId.compass.aliases.includes("group-3"));
});

test("independent panels remain discoverable when the expanded snapshot is missing", () => {
  assert.deepEqual(monitorFamilies([]).map(f => f.id).sort(),
    ["breaks", "goals", "shape", "shots", "sisal", "skyline"]);
});
