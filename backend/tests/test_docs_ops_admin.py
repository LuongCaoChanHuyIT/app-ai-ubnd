import os
import tempfile
import unittest
from pathlib import Path
from fastapi.testclient import TestClient

from backend.db import init_db
from backend.main import app


class DocsOpsAdminTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.tmp.name)
        os.environ["UBND_DB_PATH"] = str(self.base_dir / "main.db")
        init_db()
        self.client = TestClient(app, headers={"X-Actor-Email": "tsh.co@tshorg.vn"})

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_private_documents_enforce_department_isolation_in_m04_and_m01(self) -> None:
        create_res = self.client.post(
            "/api/m04/documents",
            json={
                "doc_number": "NB-VP-99/2026",
                "title": "Sổ tay nội bộ mật Văn phòng",
                "doc_type": "Quy chế",
                "tier": "kho_rieng",
                "department_id": "VP",
                "issuer": "Văn phòng UBND",
                "issued_date": "2026-10-01",
                "summary": "Tài liệu riêng VP",
                "content": "Quy trình đặc thù KHO_RIENG_VP_SECRET chỉ cán bộ VP được xem",
            },
        )
        self.assertEqual(create_res.status_code, 200)

        kt_docs = self.client.get(
            "/api/m04/documents", params={"department_id": "KT"}
        ).json()["documents"]
        vp_docs = self.client.get(
            "/api/m04/documents", params={"department_id": "VP"}
        ).json()["documents"]
        self.assertFalse(any(d["doc_number"] == "NB-VP-99/2026" for d in kt_docs))
        self.assertTrue(any(d["doc_number"] == "NB-VP-99/2026" for d in vp_docs))

        # Also verify M01 RAG for KT never cites NB-VP-99/2026
        kt_chat = self.client.post(
            "/api/m01/chat",
            json={
                "session_id": "s-iso-kt",
                "department_id": "KT",
                "mode": "nghiep_vu",
                "message": "KHO_RIENG_VP_SECRET NB-VP-99/2026",
            },
        ).json()
        cited_numbers = [c["doc_number"] for c in kt_chat["reply"]["citations"]]
        self.assertNotIn("NB-VP-99/2026", cited_numbers)

    def test_upload_rejects_unsupported_and_oversized_and_processes_discrepancies(self) -> None:
        bad = self.client.post(
            "/api/m05/sessions/s-up/upload",
            files={"file": ("virus.exe", b"MZ123", "application/octet-stream")},
        )
        self.assertEqual(bad.status_code, 400)

        oversized = self.client.post(
            "/api/m05/sessions/s-up/upload",
            files={"file": ("big.txt", b"x" * (10 * 1024 * 1024 + 10), "text/plain")},
        )
        self.assertEqual(oversized.status_code, 413)

        up1 = self.client.post(
            "/api/m05/sessions/s-up/upload",
            params={"department_id": "NNMT"},
            files={
                "file": (
                    "don_de_nghi.txt",
                    "Chủ hộ: Nguyễn Văn A. Diện tích: 120 m2. Ngày: 10/10/2026".encode(),
                    "text/plain",
                )
            },
        )
        self.assertEqual(up1.status_code, 200)
        up2 = self.client.post(
            "/api/m05/sessions/s-up/upload",
            params={"department_id": "NNMT"},
            files={
                "file": (
                    "bien_ban.txt",
                    "Chủ hộ: Nguyễn Văn A. Diện tích: 145 m2. Ngày: 15/10/2026".encode(),
                    "text/plain",
                )
            },
        )
        self.assertEqual(up2.status_code, 200)

        proc = self.client.post(
            "/api/m05/sessions/s-up/process",
            json={"action": "doi_chieu", "department_id": "NNMT"},
        )
        self.assertEqual(proc.status_code, 200)
        self.assertIn("120", proc.json()["result_markdown"] + str(proc.json()["highlights"]))

    def test_m06_task_lifecycle_and_reminder(self) -> None:
        created = self.client.post(
            "/api/m06/tasks",
            json={
                "title": "Báo cáo thu chi ngân sách tháng 11",
                "description": "Tổng hợp biểu mẫu trình Chủ tịch UBND",
                "department_id": "KT",
                "assignee": "Trần Thị B",
                "due_date": "2026-11-25",
                "priority": "cao",
                "ref_doc_number": "CV-112/UBND",
            },
        )
        self.assertEqual(created.status_code, 200)
        tid = created.json()["id"]
        patched = self.client.patch(
            f"/api/m06/tasks/{tid}",
            json={"progress": 65, "status": "dang_thuc_hien", "remind": True},
        )
        self.assertEqual(patched.status_code, 200)
        self.assertEqual(patched.json()["reminder_count"], 1)

    def test_admin_masks_api_keys_and_blocks_non_owner_mutations(self) -> None:
        owner_headers = {"X-Actor-Email": "tsh.co@tshorg.vn"}
        connectors = self.client.get(
            "/api/m07/api-connectors", headers=owner_headers
        ).json()["connectors"]
        cid = connectors[0]["id"]
        put_res = self.client.put(
            f"/api/m07/api-connectors/{cid}",
            headers=owner_headers,
            json={
                "name": "OpenAI Gateway",
                "provider": "openai",
                "base_url": "https://api.openai.com/v1",
                "model_name": "gpt-4o-mini",
                "api_key": "sk-super-secret-1234",
                "active": False,
            },
        )
        self.assertEqual(put_res.status_code, 200)

        connector_after = self.client.get(
            "/api/m07/api-connectors", headers=owner_headers
        ).json()["connectors"][0]
        self.assertNotIn("api_key", connector_after)
        self.assertNotIn("super-secret", connector_after["api_key_masked"])
        self.assertIn("***", connector_after["api_key_masked"])
        self.assertTrue(connector_after["api_key_masked"].endswith("1234"))

        non_owner = {"X-Actor-Email": "canbo.kt@ubnd.vn"}
        self.assertEqual(
            self.client.post(
                "/api/m07/users",
                headers=non_owner,
                json={
                    "email": "new@ubnd.vn",
                    "full_name": "Lê C",
                    "position": "Công chức",
                    "role": "officer",
                    "department_id": "KT",
                    "private_repo_access": True,
                },
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.put(
                "/api/m07/departments/KT/instruction",
                headers=non_owner,
                json={"instruction": "Thay đổi trái phép"},
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.put(
                f"/api/m07/api-connectors/{cid}",
                headers=non_owner,
                json={
                    "name": "Hack",
                    "provider": "openai",
                    "base_url": "https://api.openai.com/v1",
                    "model_name": "gpt-4o-mini",
                    "api_key": "sk-x",
                    "active": True,
                },
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(
                "/api/m07/clone-tenant",
                headers=non_owner,
                json={"commune_name": "UBND Xã X", "admin_email": "x@gov.vn"},
            ).status_code,
            403,
        )

    def test_clone_tenant_sanitizes_slug_and_prevents_overwrite(self) -> None:
        owner_headers = {"X-Actor-Email": "tsh.co@tshorg.vn"}
        res1 = self.client.post(
            "/api/m07/clone-tenant",
            headers=owner_headers,
            json={
                "commune_name": "../UBND Phường Bến Nghé",
                "admin_email": "admin.bennghe@tphcm.gov.vn",
            },
        )
        self.assertEqual(res1.status_code, 200)
        self.assertEqual(res1.json()["slug"], "ubnd-phuong-ben-nghe")
        self.assertEqual(res1.json()["storage_label"], "isolated-tenant://ubnd-phuong-ben-nghe")
        self.assertTrue((self.base_dir / "tenants" / "ubnd-phuong-ben-nghe.db").exists())

        dup = self.client.post(
            "/api/m07/clone-tenant",
            headers=owner_headers,
            json={
                "commune_name": "UBND Phường Bến Nghé",
                "admin_email": "admin2@tphcm.gov.vn",
            },
        )
        self.assertEqual(dup.status_code, 409)


if __name__ == "__main__":
    unittest.main()

