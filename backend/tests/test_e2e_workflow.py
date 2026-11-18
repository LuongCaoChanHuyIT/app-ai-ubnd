import os
import tempfile
import unittest
from pathlib import Path
from fastapi.testclient import TestClient

from backend.db import init_db
from backend.main import app


class FullSevenModuleWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["UBND_DB_PATH"] = str(Path(self.tmp.name) / "e2e.db")
        init_db()
        self.client = TestClient(app)
        self.owner = {"X-Actor-Email": "tsh.co@tshorg.vn"}

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_end_to_end_seven_module_workflow(self) -> None:
        sid = "e2e-session-01"

        # M05: Upload temporary dossier
        up = self.client.post(
            f"/api/m05/sessions/{sid}/upload",
            files={
                "file": (
                    "ho_so_tthc.txt",
                    "Hồ sơ đăng ký khai sinh quá hạn của công dân Lê Văn D ngày 12/11/2026".encode(),
                    "text/plain",
                )
            },
        )
        self.assertEqual(up.status_code, 200)
        self.assertEqual(len(up.json()["files"]), 1)

        # M05: Summarize and synthesize submission sheet
        proc = self.client.post(
            f"/api/m05/sessions/{sid}/process",
            json={"action": "tong_hop", "department_id": "VP"},
        )
        self.assertEqual(proc.status_code, 200)
        self.assertIn("Lê Văn D", proc.json()["result_markdown"])

        # M01: Consult business regulations using uploaded dossier
        chat = self.client.post(
            "/api/m01/chat",
            json={
                "session_id": sid,
                "department_id": "VP",
                "mode": "tham_dinh",
                "message": "Thẩm định hồ sơ hộ tịch vừa tải lên",
            },
        )
        self.assertEqual(chat.status_code, 200)
        self.assertIn("Lê Văn D", chat.json()["reply"]["content"])

        # M02: Analyze extended options
        ext = self.client.post(
            "/api/m02/analyze",
            json={
                "department_id": "VP",
                "topic": "Rút ngắn thời gian trả kết quả hộ tịch",
                "context": "Đông dân cư",
            },
        )
        self.assertEqual(ext.status_code, 200)
        self.assertEqual(len(ext.json()["options"]), 3)

        # M03: Generate & audit draft
        draft = self.client.post(
            "/api/m03/draft",
            json={
                "department_id": "VP",
                "doc_type": "Công văn",
                "title": "Xác minh tình trạng hộ tịch",
                "key_points": "Phối hợp xác minh nơi cư trú trước đây",
            },
        ).json()["draft_text"]
        audit = self.client.post(
            "/api/m03/audit",
            json={
                "department_id": "VP",
                "doc_type": "Công văn",
                "draft_text": draft,
            },
        )
        self.assertEqual(audit.status_code, 200)
        self.assertEqual(len(audit.json()["criteria"]), 5)

        # M04: Submit official document update request
        req = self.client.post(
            "/api/m04/update-requests",
            json={
                "doc_number": "TT-04/2026/TT-BTP",
                "title": "Thông tư hướng dẫn hộ tịch điện tử",
                "tier": "trung_uong",
                "department_id": "VP",
                "reason": "Bổ sung biểu mẫu mới",
                "requested_by": "tsh.co@tshorg.vn",
            },
        )
        self.assertEqual(req.status_code, 200)

        # M06: Create task & trigger reminder
        task = self.client.post(
            "/api/m06/tasks",
            json={
                "title": "Trả kết quả hộ tịch hồ sơ Lê Văn D",
                "description": "Hoàn tất trước 16h00",
                "department_id": "VP",
                "assignee": "Nguyễn Thị Hộ Tịch",
                "due_date": "2026-11-20",
                "priority": "cao",
                "ref_doc_number": "HS-2026-88",
            },
        )
        self.assertEqual(task.status_code, 200)

        # M07: Update room instruction, clone new ward tenant, check audit logs
        inst = self.client.put(
            "/api/m07/departments/VP/instruction",
            headers=self.owner,
            json={
                "instruction": "Ưu tiên viện dẫn Luật Hộ tịch và Nghị định 30/2020/NĐ-CP."
            },
        )
        self.assertEqual(inst.status_code, 200)
        clone = self.client.post(
            "/api/m07/clone-tenant",
            headers=self.owner,
            json={
                "commune_name": "UBND Phường Hòa Cường",
                "admin_email": "admin@hoacuong.gov.vn",
            },
        )
        self.assertEqual(clone.status_code, 200)
        self.assertEqual(clone.json()["slug"], "ubnd-phuong-hoa-cuong")

        # M01/M05: Wipe ephemeral session memory & confirm zero residual data
        self.client.delete(f"/api/sessions/{sid}")
        after = self.client.get(f"/api/sessions/{sid}").json()
        self.assertEqual(after["files"], [])
        self.assertEqual(after["messages"], [])

        # Confirm subsequent M01 turn after wipe has zero knowledge of Lê Văn D
        post_wipe_chat = self.client.post(
            "/api/m01/chat",
            json={
                "session_id": sid,
                "department_id": "VP",
                "mode": "tham_dinh",
                "message": "Kiểm tra lại hồ sơ hiện tại trong phiên",
            },
        ).json()
        self.assertNotIn("Lê Văn D", post_wipe_chat["reply"]["content"])

        logs = self.client.get("/api/m07/audit-logs", headers=self.owner).json()["logs"]
        self.assertGreaterEqual(len(logs), 6)


if __name__ == "__main__":
    unittest.main()

