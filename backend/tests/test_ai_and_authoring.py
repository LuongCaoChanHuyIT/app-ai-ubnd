import io
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from fastapi.testclient import TestClient

from backend.db import init_db
from backend.main import app
from backend.services.doc_parser import parse_uploaded_bytes


def make_docx_bytes(text: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(
            "word/document.xml",
            f'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:body></w:document>',
        )
    return buf.getvalue()


class AiAndAuthoringTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["UBND_DB_PATH"] = str(Path(self.tmp.name) / "test.db")
        init_db()
        self.client = TestClient(app, headers={"X-Actor-Email": "tsh.co@tshorg.vn"})

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_doc_parser_extracts_docx_and_handles_corrupt_pdf_gracefully(self) -> None:
        text, note = parse_uploaded_bytes(
            "to_trinh.docx",
            make_docx_bytes("Đề nghị xác nhận hộ tịch"),
        )
        self.assertIn("Đề nghị xác nhận hộ tịch", text)
        self.assertEqual(note, "Đã trích xuất văn bản DOCX")

        pdf_text, pdf_note = parse_uploaded_bytes(
            "scan.pdf",
            b"%PDF-1.4 binary scan without text",
        )
        self.assertTrue(len(pdf_note) > 0)
        self.assertIsInstance(pdf_text, str)

        with self.assertRaises(ValueError):
            parse_uploaded_bytes("malware.exe", b"MZ")

        with self.assertRaises(ValueError):
            parse_uploaded_bytes("oversized.txt", b"a" * (10 * 1024 * 1024 + 1))

    def test_m01_chat_modes_and_session_wipe(self) -> None:
        res = self.client.post(
            "/api/m01/chat",
            json={
                "session_id": "s-m01",
                "department_id": "VP",
                "mode": "nghiep_vu",
                "message": "Quy định thể thức văn bản hành chính theo Nghị định 30",
            },
        )
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertGreaterEqual(len(body["reply"]["citations"]), 1)

        del_res = self.client.delete("/api/sessions/s-m01")
        self.assertEqual(del_res.status_code, 200)
        state = self.client.get("/api/sessions/s-m01").json()
        self.assertEqual(state["messages"], [])
        self.assertEqual(state["files"], [])

    def test_m02_extended_returns_three_options(self) -> None:
        res = self.client.post(
            "/api/m02/analyze",
            json={
                "department_id": "VP",
                "topic": "Nâng cao tỷ lệ hồ sơ trực tuyến tại Bộ phận Một cửa",
                "context": "Phường đông dân cư",
            },
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.json()["options"]), 3)

    def test_m03_draft_and_five_criteria_audit(self) -> None:
        draft_res = self.client.post(
            "/api/m03/draft",
            json={
                "department_id": "VP",
                "doc_type": "Kế hoạch",
                "title": "Triển khai chuyển đổi số quý IV/2026",
                "key_points": "Rà soát TTHC; Tập huấn cán bộ; Tuyên truyền khu dân cư",
            },
        )
        self.assertEqual(draft_res.status_code, 200)
        draft_text = draft_res.json()["draft_text"]
        self.assertIn("CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM", draft_text)

        audit_res = self.client.post(
            "/api/m03/audit",
            json={
                "department_id": "VP",
                "doc_type": "Quyết định",
                "draft_text": draft_text,
            },
        )
        self.assertEqual(audit_res.status_code, 200)
        self.assertEqual(len(audit_res.json()["criteria"]), 5)


if __name__ == "__main__":
    unittest.main()

