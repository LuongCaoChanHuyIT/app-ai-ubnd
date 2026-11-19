import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


class SplitReposTests(unittest.TestCase):
    def test_split_script_syntax_and_dry_run_and_validation(self) -> None:
        script_path = REPO_ROOT / "deploy" / "scripts" / "split-and-push-repos.sh"
        self.assertTrue(script_path.exists(), "split-and-push-repos.sh must exist")

        syntax = subprocess.run(
            ["bash", "-n", str(script_path)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(syntax.returncode, 0, msg=syntax.stderr)

        bad_repo = subprocess.run(
            ["bash", str(script_path), "--dry-run"],
            env={**os.environ, "FRONTEND_REPO": "bad/repo name"},
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(bad_repo.returncode, 0)

        dry = subprocess.run(
            ["bash", str(script_path), "--dry-run"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(dry.returncode, 0, msg=dry.stderr)
        self.assertIn("LuongCaoChanHuyIT/ubnd-ai-frontend", dry.stdout)
        self.assertIn("LuongCaoChanHuyIT/ubnd-ai-backend", dry.stdout)
        self.assertIn("--private", dry.stdout)
        self.assertIn("main", dry.stdout)
        self.assertIn("app-ai-ubnd", dry.stdout)

    def test_export_only_builds_clean_standalone_repos_and_runs_idempotently(self) -> None:
        script_path = REPO_ROOT / "deploy" / "scripts" / "split-and-push-repos.sh"
        self.assertTrue(script_path.exists(), "split-and-push-repos.sh must exist")

        data_dir = REPO_ROOT / "backend" / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        dummy_db = data_dir / "leak_check_temp.db"
        created_dummy = not dummy_db.exists()
        if created_dummy:
            dummy_db.write_bytes(b"sqlite-test-bytes")

        try:
            with tempfile.TemporaryDirectory() as tmp:
                out_dir = Path(tmp) / "exported"

                first = subprocess.run(
                    ["bash", str(script_path), "--export-only", str(out_dir)],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(first.returncode, 0, msg=first.stderr)

                # Second run must succeed idempotently
                second = subprocess.run(
                    ["bash", str(script_path), "--export-only", str(out_dir)],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(second.returncode, 0, msg=second.stderr)

                be_root = out_dir / "ubnd-ai-backend"
                fe_root = out_dir / "ubnd-ai-frontend"
                self.assertTrue(be_root.is_dir())
                self.assertTrue(fe_root.is_dir())

                # Backend standalone assertions
                self.assertTrue((be_root / "main.py").is_file())
                self.assertTrue((be_root / "requirements.txt").is_file())
                self.assertEqual(
                    (be_root / "requirements.txt").read_text(encoding="utf-8"),
                    (REPO_ROOT / "backend" / "requirements.txt").read_text(encoding="utf-8"),
                )
                be_docker = (be_root / "Dockerfile").read_text(encoding="utf-8")
                self.assertIn("--workers 1", be_docker)
                self.assertIn("UBND_ENV=production", be_docker)
                self.assertIn("UBND_DB_PATH=/var/lib/ubnd-ai/ubnd_ai.db", be_docker)
                self.assertIn("${PORT:-8000}", be_docker)

                self.assertTrue((be_root / ".env.example").is_file())
                self.assertTrue((be_root / "backend" / "main.py").is_file())
                self.assertTrue((be_root / "deploy" / "scripts" / "backup-sqlite.sh").is_file())
                self.assertFalse((be_root / "app").exists())
                self.assertEqual(list(be_root.rglob("*.db")), [])

                # Root `uvicorn main:app` import check inside isolated exported backend
                import_check = subprocess.run(
                    [
                        sys.executable,
                        "-c",
                        "import main; assert main.app.title and callable(main.create_app)",
                    ],
                    cwd=str(be_root),
                    env={
                        **os.environ,
                        "PYTHONPATH": str(be_root),
                        "UBND_DB_PATH": str(Path(tmp) / "isolated_import_check.db"),
                    },
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(import_check.returncode, 0, msg=import_check.stderr)

                # Frontend standalone assertions
                self.assertTrue((fe_root / "package.json").is_file())
                self.assertTrue((fe_root / ".env.example").is_file())
                self.assertTrue((fe_root / "app" / "lib" / "api.ts").is_file())
                fe_docker = (fe_root / "Dockerfile").read_text(encoding="utf-8")
                self.assertIn("ARG VITE_API_BASE_URL", fe_docker)
                self.assertFalse((fe_root / "node_modules").exists())
                self.assertFalse((fe_root / "build").exists())
                self.assertFalse((fe_root / ".react-router").exists())
                self.assertFalse((fe_root / "backend").exists())
                self.assertEqual(list(fe_root.rglob("*.db")), [])
        finally:
            if created_dummy and dummy_db.exists():
                dummy_db.unlink()

    def test_frontend_dockerignore_and_gitignore_exclude_env_secrets_and_git(self) -> None:
        dockerignore = (REPO_ROOT / "app" / ".dockerignore").read_text(encoding="utf-8")
        self.assertIn(".git", dockerignore)
        self.assertIn(".env", dockerignore)
        self.assertIn(".env.*", dockerignore)
        self.assertIn("!.env.example", dockerignore)

        gitignore = (REPO_ROOT / "app" / ".gitignore").read_text(encoding="utf-8")
        self.assertIn(".env.*", gitignore)
        self.assertIn("!.env.example", gitignore)

    def test_split_script_blocks_backup_repo_collision_and_strips_env_and_venv_leaks(self) -> None:
        script_path = REPO_ROOT / "deploy" / "scripts" / "split-and-push-repos.sh"

        for bad_env in (
            {"FRONTEND_REPO": "app-ai-ubnd"},
            {"BACKEND_REPO": "app-ai-ubnd"},
            {"FRONTEND_REPO": "same-repo", "BACKEND_REPO": "same-repo"},
        ):
            res = subprocess.run(
                ["bash", str(script_path), "--dry-run"],
                env={**os.environ, **bad_env},
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(res.returncode, 0, msg=f"Should reject {bad_env}")

        fe_env_local = REPO_ROOT / "app" / ".env.local.leaktest"
        be_env_local = REPO_ROOT / "backend" / ".env.local.leaktest"
        fe_env_local.write_text("VITE_SECRET=leak\n", encoding="utf-8")
        be_env_local.write_text("SECRET=leak\n", encoding="utf-8")
        try:
            with tempfile.TemporaryDirectory() as tmp:
                out_dir = Path(tmp) / "exported"
                res = subprocess.run(
                    ["bash", str(script_path), "--export-only", str(out_dir)],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(res.returncode, 0, msg=res.stderr)
                self.assertFalse((out_dir / "ubnd-ai-frontend" / ".env.local.leaktest").exists())
                self.assertTrue((out_dir / "ubnd-ai-frontend" / ".env.example").is_file())
                self.assertFalse((out_dir / "ubnd-ai-backend" / "backend" / ".env.local.leaktest").exists())
                self.assertTrue((out_dir / "ubnd-ai-backend" / ".env.example").is_file())
        finally:
            fe_env_local.unlink(missing_ok=True)
            be_env_local.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()

