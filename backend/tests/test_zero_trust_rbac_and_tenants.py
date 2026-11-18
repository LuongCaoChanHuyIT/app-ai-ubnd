import os
import tempfile
import unittest
from pathlib import Path
from fastapi.testclient import TestClient

from backend.db import init_db
from backend.main import app


class ZeroTrustRbacAndTenantTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "root_ubnd.db"
        os.environ["UBND_DB_PATH"] = str(self.db_path)
        init_db(self.db_path, commune_name="UBND Phường Tân Chính")
        self.client = TestClient(app)
        self.owner = {"X-Actor-Email": "tsh.co@tshorg.vn"}
        self.vp_officer = {"X-Actor-Email": "canbo.vp@ubnd.vn"}
        self.kt_officer = {"X-Actor-Email": "canbo.kt@ubnd.vn"}
        self.vhxh_officer = {"X-Actor-Email": "canbo.vhxh@ubnd.vn"}
        self.nnmt_officer = {"X-Actor-Email": "canbo.nnmt@ubnd.vn"}

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_unauthenticated_requests_rejected_with_401_across_all_modules(self) -> None:
        # Zero-Trust: no silent fallback to tsh.co@tshorg.vn when header & cookie are absent
        self.assertEqual(self.client.get("/api/m04/documents").status_code, 401)
        self.assertEqual(
            self.client.post(
                "/api/m01/chat",
                json={"session_id": "s1", "department_id": "VP", "mode": "nghiep_vu", "message": "Hỏi"},
            ).status_code,
            401,
        )
        self.assertEqual(self.client.get("/api/m06/tasks").status_code, 401)
        self.assertEqual(self.client.get("/api/m07/audit-logs").status_code, 401)
        self.assertEqual(self.client.get("/api/m07/api-connectors").status_code, 401)
        self.assertEqual(self.client.get("/api/m07/tenants").status_code, 401)

    def test_cookie_auth_works_identically_to_header_for_ssr_loaders(self) -> None:
        cookie_hdr = {"Cookie": "ubnd_actor_email=canbo.kt%40ubnd.vn"}
        res = self.client.get(
            "/api/m04/documents",
            params={"department_id": "KT"},
            headers=cookie_hdr,
        )
        self.assertEqual(res.status_code, 200)
        docs = res.json()["documents"]
        self.assertTrue(any(d["tier"] == "kho_rieng" and d["department_id"] == "KT" for d in docs))
        self.assertFalse(any(d["tier"] == "kho_rieng" and d["department_id"] != "KT" for d in docs))
        # Cookie-authenticated KT officer must also be blocked (403) from VP
        self.assertEqual(
            self.client.get(
                "/api/m04/documents",
                params={"department_id": "VP"},
                headers=cookie_hdr,
            ).status_code,
            403,
        )

    def test_officer_strictly_locked_to_assigned_department_across_m01_to_m07(self) -> None:
        # KT officer blocked from M01/M02/M03/M04/M05 in VP
        self.assertEqual(
            self.client.post(
                "/api/m01/chat",
                headers=self.kt_officer,
                json={"session_id": "s1", "department_id": "VP", "mode": "nghiep_vu", "message": "Test"},
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(
                "/api/m02/analyze",
                headers=self.kt_officer,
                json={"department_id": "VP", "topic": "Chủ đề thử nghiệm", "context": ""},
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(
                "/api/m03/draft",
                headers=self.kt_officer,
                json={"department_id": "VP", "doc_type": "Công văn", "title": "Báo cáo", "key_points": "Ý 1"},
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.get(
                "/api/m04/documents",
                params={"department_id": "VP"},
                headers=self.kt_officer,
            ).status_code,
            403,
        )

        # KT officer blocked from creating or reminding VP tasks in M06
        vp_tasks = self.client.get(
            "/api/m06/tasks", params={"department_id": "VP"}, headers=self.owner
        ).json()["tasks"]
        vp_task_id = vp_tasks[0]["id"]
        self.assertEqual(
            self.client.patch(
                f"/api/m06/tasks/{vp_task_id}",
                headers=self.kt_officer,
                json={"remind": True},
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(
                "/api/m06/tasks",
                headers=self.kt_officer,
                json={
                    "title": "Giao việc trái phòng",
                    "description": "",
                    "department_id": "VP",
                    "assignee": "Ai đó",
                    "due_date": "2026-11-30",
                    "priority": "cao",
                },
            ).status_code,
            403,
        )

        # Officer completely blocked (403) from M07 admin read & write endpoints
        for m07_path in ("/api/m07/users", "/api/m07/api-connectors", "/api/m07/audit-logs", "/api/m07/tenants"):
            self.assertEqual(
                self.client.get(m07_path, headers=self.kt_officer).status_code,
                403,
                f"Expected 403 for officer on {m07_path}",
            )

    def test_composite_session_isolation_prevents_bleed_across_departments_and_users(self) -> None:
        shared_sid = "browser-tab-session-01"
        # Owner uploads confidential file in VP
        up_vp = self.client.post(
            f"/api/m05/sessions/{shared_sid}/upload",
            params={"department_id": "VP"},
            headers=self.owner,
            files={"file": ("mat_vp.txt", "Tài liệu riêng phiên VP".encode(), "text/plain")},
        )
        self.assertEqual(up_vp.status_code, 200)
        self.assertEqual(len(up_vp.json()["files"]), 1)

        # Same owner switching to KT with SAME session_id sees 0 files from VP!
        kt_session = self.client.get(
            f"/api/sessions/{shared_sid}",
            params={"department_id": "KT"},
            headers=self.owner,
        ).json()
        self.assertEqual(kt_session["files"], [])

        # VP officer with SAME session_id in VP also sees 0 files from Owner's session!
        officer_session = self.client.get(
            f"/api/sessions/{shared_sid}",
            params={"department_id": "VP"},
            headers=self.vp_officer,
        ).json()
        self.assertEqual(officer_session["files"], [])

    def test_multi_tenant_active_switching_isolates_commune_databases_and_hides_os_paths(self) -> None:
        clone_res = self.client.post(
            "/api/m07/clone-tenant",
            headers=self.owner,
            json={
                "commune_name": "UBND Phường Hòa Thuận Đông",
                "admin_email": "admin@hoathuandong.gov.vn",
            },
        )
        self.assertEqual(clone_res.status_code, 200)
        cloned = clone_res.json()
        self.assertEqual(cloned["slug"], "ubnd-phuong-hoa-thuan-dong")
        # Must not leak absolute host OS directory path
        self.assertNotIn(self.tmp.name, cloned.get("storage_label", ""))
        self.assertNotIn("db_path", cloned)

        # Create a task inside the cloned tenant using X-Tenant-Slug
        tenant_headers = {
            "X-Actor-Email": "tsh.co@tshorg.vn",
            "X-Tenant-Slug": "ubnd-phuong-hoa-thuan-dong",
        }
        t_create = self.client.post(
            "/api/m06/tasks",
            headers=tenant_headers,
            json={
                "title": "Nhiệm vụ riêng của Phường Hòa Thuận Đông",
                "description": "Chỉ tồn tại trên DB Hòa Thuận Đông",
                "department_id": "VP",
                "assignee": "Võ Văn Kiệt",
                "due_date": "2026-12-05",
                "priority": "khan",
            },
        )
        self.assertEqual(t_create.status_code, 200)

        # Verify task exists in cloned tenant but NOT in root default tenant!
        cloned_tasks = self.client.get("/api/m06/tasks", headers=tenant_headers).json()["tasks"]
        root_tasks = self.client.get("/api/m06/tasks", headers=self.owner).json()["tasks"]
        self.assertTrue(any("Hòa Thuận Đông" in t["title"] for t in cloned_tasks))
        self.assertFalse(any("Hòa Thuận Đông" in t["title"] for t in root_tasks))

        # Verify bootstrap reports active commune name dynamically
        boot_cloned = self.client.get("/api/bootstrap", headers=tenant_headers).json()
        self.assertEqual(boot_cloned["commune_name"], "UBND Phường Hòa Thuận Đông")
        boot_root = self.client.get("/api/bootstrap").json()
        self.assertEqual(boot_root["commune_name"], "UBND Phường Tân Chính")

    def test_nnmt_officer_seeded_without_private_repo_access_and_owner_can_toggle(self) -> None:
        # Out-of-the-box Zero-Trust demo: canbo.nnmt@ubnd.vn has private_repo_access = False
        nnmt_private = self.client.get(
            "/api/m04/documents",
            params={"department_id": "NNMT", "tier": "kho_rieng"},
            headers=self.nnmt_officer,
        ).json()["documents"]
        self.assertEqual(nnmt_private, [])

        # Owner can toggle private_repo_access via PATCH /api/m07/users/{user_id}
        users = self.client.get("/api/m07/users", headers=self.owner).json()["users"]
        nnmt_user = next(u for u in users if u["email"] == "canbo.nnmt@ubnd.vn")
        self.assertFalse(nnmt_user["private_repo_access"])

        patch_on = self.client.patch(
            f"/api/m07/users/{nnmt_user['id']}",
            headers=self.owner,
            json={"private_repo_access": True},
        )
        self.assertEqual(patch_on.status_code, 200)
        self.assertTrue(patch_on.json()["private_repo_access"])

        nnmt_private_after = self.client.get(
            "/api/m04/documents",
            params={"department_id": "NNMT", "tier": "kho_rieng"},
            headers=self.nnmt_officer,
        ).json()["documents"]
        self.assertGreaterEqual(len(nnmt_private_after), 2)


if __name__ == "__main__":
    unittest.main()
