import os
import sqlite3
import subprocess
import tempfile
import unittest
from pathlib import Path

from backend.db import init_db

REPO_ROOT = Path(__file__).resolve().parents[2]


class DeployArtifactsTests(unittest.TestCase):
    def test_systemd_services_pin_single_worker_prod_env_and_external_db_path(self) -> None:
        be_svc = (REPO_ROOT / "deploy" / "systemd" / "ubnd-ai-backend.service").read_text(encoding="utf-8")
        self.assertIn("--workers 1", be_svc)
        self.assertIn('UBND_ENV=production', be_svc)
        self.assertIn('UBND_DB_PATH=/var/lib/ubnd-ai/ubnd_ai.db', be_svc)

        fe_svc = (REPO_ROOT / "deploy" / "systemd" / "ubnd-ai-frontend.service").read_text(encoding="utf-8")
        self.assertIn("NODE_ENV=production", fe_svc)
        self.assertIn("PORT=3000", fe_svc)
        self.assertIn("API_BASE_URL=http://127.0.0.1:8000", fe_svc)

    def test_nginx_conf_sets_15mb_upload_limit_and_same_origin_proxy_routes(self) -> None:
        nginx_conf = (REPO_ROOT / "deploy" / "nginx" / "ubnd-ai.conf").read_text(encoding="utf-8")
        self.assertIn("client_max_body_size 15M;", nginx_conf)
        self.assertIn("location /api/", nginx_conf)
        self.assertIn("proxy_pass http://127.0.0.1:8000;", nginx_conf)
        self.assertIn("proxy_pass http://127.0.0.1:3000;", nginx_conf)

    def test_backup_sqlite_script_backs_up_root_and_cloned_tenant_databases_online(self) -> None:
        script_path = REPO_ROOT / "deploy" / "scripts" / "backup-sqlite.sh"
        self.assertTrue(script_path.exists(), "backup-sqlite.sh must exist")

        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            tenants_dir = data_dir / "tenants"
            backup_root = Path(tmp) / "backups"
            tenants_dir.mkdir(parents=True, exist_ok=True)

            root_db = data_dir / "ubnd_ai.db"
            tenant_db = tenants_dir / "ubnd-phuong-da-kao.db"
            init_db(root_db, commune_name="UBND xã, phường trung tâm")
            init_db(tenant_db, commune_name="UBND Phường Đa Kao")

            res = subprocess.run(
                ["bash", str(script_path)],
                env={
                    **os.environ,
                    "UBND_DATA_DIR": str(data_dir),
                    "UBND_BACKUP_DIR": str(backup_root),
                    "RETENTION_DAYS": "30",
                },
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(res.returncode, 0, msg=res.stderr)

            dated_dirs = [p for p in backup_root.iterdir() if p.is_dir()]
            self.assertEqual(len(dated_dirs), 1)
            snap_dir = dated_dirs[0]
            self.assertTrue((snap_dir / "ubnd_ai.db").exists())
            self.assertTrue((snap_dir / "tenants" / "ubnd-phuong-da-kao.db").exists())

            with sqlite3.connect(snap_dir / "tenants" / "ubnd-phuong-da-kao.db") as c:
                val = c.execute("SELECT value FROM tenant_meta WHERE key='commune_name'").fetchone()[0]
                self.assertEqual(val, "UBND Phường Đa Kao")


if __name__ == "__main__":
    unittest.main()
