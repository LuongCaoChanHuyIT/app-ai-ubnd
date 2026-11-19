import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient

from backend.db import init_db
from backend.main import create_app


class ProductionConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "prod_test.db"
        init_db(self.db_path)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_requirements_include_pypdf_and_python_docx_with_portable_versions(self) -> None:
        req_path = Path(__file__).resolve().parents[1] / "requirements.txt"
        content = req_path.read_text(encoding="utf-8")
        self.assertIn("pypdf>=", content)
        self.assertIn("python-docx>=", content)
        self.assertNotIn("0.163.0", content)

    def test_production_env_disables_openapi_docs_but_keeps_health(self) -> None:
        with patch.dict(os.environ, {"UBND_ENV": "production", "UBND_DB_PATH": str(self.db_path)}):
            prod_app = create_app()
            client = TestClient(prod_app)
            self.assertEqual(client.get("/docs").status_code, 404)
            self.assertEqual(client.get("/redoc").status_code, 404)
            self.assertEqual(client.get("/openapi.json").status_code, 404)
            self.assertEqual(client.get("/api/health").status_code, 200)

    def test_custom_allowed_origins_env_configures_cors(self) -> None:
        with patch.dict(
            os.environ,
            {
                "UBND_ENV": "production",
                "UBND_ALLOWED_ORIGINS": "https://ai.ubnd.vn, https://phuongdakao.ubnd.vn",
                "UBND_DB_PATH": str(self.db_path),
            },
        ):
            prod_app = create_app()
            client = TestClient(prod_app)
            res = client.options(
                "/api/health",
                headers={
                    "Origin": "https://ai.ubnd.vn",
                    "Access-Control-Request-Method": "GET",
                },
            )
            self.assertEqual(res.headers.get("access-control-allow-origin"), "https://ai.ubnd.vn")

    def test_cloudflare_access_trust_blocks_spoofed_headers_and_accepts_cf_header(self) -> None:
        with patch.dict(
            os.environ,
            {
                "UBND_ENV": "production",
                "UBND_TRUST_CF_ACCESS": "1",
                "UBND_DB_PATH": str(self.db_path),
            },
        ):
            prod_app = create_app()
            client = TestClient(prod_app)
            # Spoofed X-Actor-Email or Cookie without Cf-Access-Authenticated-User-Email MUST fail 401
            spoof_hdr = client.get(
                "/api/m04/documents",
                headers={"X-Actor-Email": "tsh.co@tshorg.vn"},
            )
            self.assertEqual(spoof_hdr.status_code, 401)

            spoof_cookie = client.get(
                "/api/m04/documents",
                headers={"Cookie": "ubnd_actor_email=tsh.co%40tshorg.vn"},
            )
            self.assertEqual(spoof_cookie.status_code, 401)

            # Valid Cloudflare Access header succeeds 200
            valid_cf = client.get(
                "/api/m04/documents",
                headers={"Cf-Access-Authenticated-User-Email": "tsh.co@tshorg.vn"},
            )
            self.assertEqual(valid_cf.status_code, 200)


if __name__ == "__main__":
    unittest.main()

