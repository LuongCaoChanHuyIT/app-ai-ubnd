import os
import tempfile
import unittest
from pathlib import Path
from fastapi.testclient import TestClient

from backend.db import init_db
from backend.main import app


class SecurityAndReviewFixesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["UBND_DB_PATH"] = str(Path(self.tmp.name) / "fixes.db")
        init_db()
        self.client = TestClient(app)
        self.owner = {"X-Actor-Email": "tsh.co@tshorg.vn"}
        self.kt_officer = {"X-Actor-Email": "canbo.kt@ubnd.vn"}

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_cross_department_officer_cannot_read_or_write_other_dept_private_docs(self) -> None:
        # KT officer attempting to read VP documents is strictly blocked with 403
        res = self.client.get(
            "/api/m04/documents",
            params={"department_id": "VP"},
            headers=self.kt_officer,
        )
        self.assertEqual(res.status_code, 403)

        # Unknown caller is also rejected with 403
        anon_res = self.client.get(
            "/api/m04/documents",
            params={"department_id": "VP"},
            headers={"X-Actor-Email": "stranger@example.com"},
        )
        self.assertEqual(anon_res.status_code, 403)

        # KT officer attempting to create a kho_rieng doc inside VP must get 403
        forbid_write = self.client.post(
            "/api/m04/documents",
            headers=self.kt_officer,
            json={
                "doc_number": "FAKE-VP-01",
                "title": "Tài liệu giả mạo vào VP",
                "doc_type": "Quy chế",
                "tier": "kho_rieng",
                "department_id": "VP",
                "issuer": "KT",
                "issued_date": "2026-11-18",
                "summary": "x",
                "content": "Nội dung giả mạo",
            },
        )
        self.assertEqual(forbid_write.status_code, 403)

        # KT officer IS allowed to add kho_rieng to their own department KT
        allow_own = self.client.post(
            "/api/m04/documents",
            headers=self.kt_officer,
            json={
                "doc_number": "NB-KT-2026",
                "title": "Biểu mẫu nội bộ Kinh tế",
                "doc_type": "Hướng dẫn",
                "tier": "kho_rieng",
                "department_id": "KT",
                "issuer": "Phòng Kinh tế",
                "issued_date": "2026-11-18",
                "summary": "Biểu mẫu KT",
                "content": "Nội dung hướng dẫn nội bộ của bộ phận Kinh tế",
            },
        )
        self.assertEqual(allow_own.status_code, 200)

    def test_headerless_m07_mutations_fail_with_401_and_short_secrets_are_masked(self) -> None:
        # Headerless POST /api/m07/users must fail 401 (Zero-Trust: no default owner!)
        no_header = self.client.post(
            "/api/m07/users",
            json={
                "email": "unauth@ubnd.vn",
                "full_name": "Không Phép",
                "position": "Công chức",
                "role": "officer",
                "department_id": "VP",
                "private_repo_access": True,
            },
        )
        self.assertEqual(no_header.status_code, 401)

        # 7-character secret must never leak plaintext prefix+suffix
        cid = self.client.get("/api/m07/api-connectors", headers=self.owner).json()["connectors"][0]["id"]
        self.client.put(
            f"/api/m07/api-connectors/{cid}",
            headers=self.owner,
            json={
                "name": "Short Key Test",
                "provider": "openai",
                "base_url": "https://api.openai.com/v1",
                "model_name": "gpt-4o-mini",
                "api_key": "abcdefg",
                "active": False,
            },
        )
        masked = self.client.get("/api/m07/api-connectors", headers=self.owner).json()["connectors"][0][
            "api_key_masked"
        ]
        self.assertEqual(masked, "***")

    def test_m04_unmatched_query_returns_empty_and_quyet_dinh_draft_has_dieu_1(self) -> None:
        empty_search = self.client.get(
            "/api/m04/documents",
            params={"department_id": "VP", "q": "TU_KHOA_KHONG_HE_TON_TAI_99999"},
            headers=self.owner,
        ).json()
        self.assertEqual(empty_search["documents"], [])

        qd = self.client.post(
            "/api/m03/draft",
            headers=self.owner,
            json={
                "department_id": "KT",
                "doc_type": "Quyết định",
                "title": "Thành lập Tổ rà soát dự toán ngân sách năm 2027",
                "key_points": "Thành lập Tổ công tác; Quy định nhiệm vụ của Tổ; Hiệu lực thi hành",
            },
        ).json()["draft_text"]
        self.assertIn("Điều 1.", qd)
        audit = self.client.post(
            "/api/m03/audit",
            headers=self.owner,
            json={
                "department_id": "KT",
                "doc_type": "Quyết định",
                "draft_text": qd,
            },
        ).json()
        tham_quyen = next(c for c in audit["criteria"] if c["id"] == "tham_quyen")
        self.assertEqual(tham_quyen["status"], "dat")


if __name__ == "__main__":
    unittest.main()
