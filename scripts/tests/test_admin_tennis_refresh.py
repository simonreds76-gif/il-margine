from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
ROUTE = (ROOT / "src/app/api/admin/tennis-refresh/route.ts").read_text(encoding="utf-8")
ADMIN = (ROOT / "src/app/admin/page.tsx").read_text(encoding="utf-8")


class AdminTennisRefreshTests(unittest.TestCase):
    def test_route_is_admin_local_windows_only(self):
        self.assertIn("await isAdmin()", ROUTE)
        self.assertIn('process.platform !== "win32"', ROUTE)
        self.assertIn('host === "localhost"', ROUTE)

    def test_route_uses_fixed_task_without_shell(self):
        self.assertIn('const AM_TASK = "IlMargine-Daily-AM"', ROUTE)
        self.assertIn('const NIGHT_TASK = "IlMargine-Daily"', ROUTE)
        self.assertIn('execFileAsync(taskExecutable(), ["/Run", "/TN", AM_TASK]', ROUTE)
        self.assertNotIn("shell:", ROUTE)

    def test_admin_wires_manual_control(self):
        self.assertIn('fetch("/api/admin/tennis-refresh", { method: "POST" })', ADMIN)
        self.assertIn("Run fair odds now", ADMIN)
        self.assertIn("Fair odds + Telegram alerts", ADMIN)


if __name__ == "__main__":
    unittest.main()
