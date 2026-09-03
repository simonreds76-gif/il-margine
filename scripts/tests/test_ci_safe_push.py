from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HELPER = ROOT / "scripts" / "ci-safe-push.sh"
BRANCH = "golden-with-speed-insights"


def run(*args: str, cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=cwd,
        env=env,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )


def configure(repo: Path) -> None:
    run("git", "config", "user.name", "Test Bot", cwd=repo)
    run("git", "config", "user.email", "test@example.com", cwd=repo)


class CiSafePushTests(unittest.TestCase):
    def test_concurrent_push_preserves_dirty_runner_checkout(self) -> None:
        bash = shutil.which("bash")
        if bash is None:
            git_bash = Path(r"C:\Program Files\Git\bin\bash.exe")
            bash = str(git_bash) if git_bash.exists() else None
        if bash is None:
            self.skipTest("bash is unavailable")

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            remote = root / "remote.git"
            seed = root / "seed"
            runner = root / "runner"
            writer = root / "writer"

            run("git", "init", "--bare", str(remote), cwd=root)
            run("git", "init", str(seed), cwd=root)
            configure(seed)
            run("git", "checkout", "-b", BRANCH, cwd=seed)
            (seed / "base.txt").write_text("base\n", encoding="utf-8")
            (seed / "leftover.txt").write_text("clean\n", encoding="utf-8")
            run("git", "add", ".", cwd=seed)
            run("git", "commit", "-m", "base", cwd=seed)
            run("git", "remote", "add", "origin", str(remote), cwd=seed)
            run("git", "push", "-u", "origin", BRANCH, cwd=seed)

            run("git", "clone", "--branch", BRANCH, str(remote), str(runner), cwd=root)
            run("git", "clone", "--branch", BRANCH, str(remote), str(writer), cwd=root)
            configure(runner)
            configure(writer)

            (runner / "evidence.txt").write_text("new evidence\n", encoding="utf-8")
            run("git", "add", "evidence.txt", cwd=runner)
            run("git", "commit", "-m", "evidence", cwd=runner)

            (writer / "concurrent.txt").write_text("other workflow\n", encoding="utf-8")
            run("git", "add", "concurrent.txt", cwd=writer)
            run("git", "commit", "-m", "concurrent writer", cwd=writer)
            run("git", "push", "origin", BRANCH, cwd=writer)

            (runner / "leftover.txt").write_text("must survive\n", encoding="utf-8")
            (runner / "untracked.json").write_text("{}\n", encoding="utf-8")
            helper_copy = runner / "ci-safe-push.sh"
            helper_copy.write_bytes(HELPER.read_bytes())
            env = {**os.environ, "CI_SAFE_PUSH_ATTEMPTS": "1"}
            result = run(bash, str(helper_copy), BRANCH, "origin", cwd=runner, env=env)

            self.assertIn("Safe push completed.", result.stdout)
            self.assertEqual((runner / "leftover.txt").read_text(encoding="utf-8"), "must survive\n")
            self.assertTrue((runner / "untracked.json").exists())
            self.assertEqual(
                run("git", "--git-dir", str(remote), "show", f"{BRANCH}:evidence.txt", cwd=root).stdout,
                "new evidence\n",
            )
            self.assertEqual(
                run("git", "--git-dir", str(remote), "show", f"{BRANCH}:concurrent.txt", cwd=root).stdout,
                "other workflow\n",
            )


if __name__ == "__main__":
    unittest.main()
