import os
import tempfile
import unittest
from pathlib import Path

from backend.db import SESSION_STORE, get_conn, init_db, log_audit


class DbAndSessionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "test_ubnd.db"
        os.environ["UBND_DB_PATH"] = str(self.db_path)
        init_db(self.db_path)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_init_db_seeds_four_departments_docs_tasks_and_owner(self) -> None:
        with get_conn(self.db_path) as conn:
            depts = [
                r["id"]
                for r in conn.execute("SELECT id FROM departments ORDER BY id").fetchall()
            ]
            self.assertEqual(sorted(depts), ["KT", "NNMT", "VHXH", "VP"])
            owner = conn.execute(
                "SELECT role FROM users_rbac WHERE email = ?",
                ("tsh.co@tshorg.vn",),
            ).fetchone()
            self.assertEqual(owner["role"], "owner")
            doc_count = conn.execute(
                "SELECT COUNT(*) AS c FROM official_documents"
            ).fetchone()["c"]
            self.assertGreaterEqual(doc_count, 6)

    def test_wipe_session_purges_messages_and_files(self) -> None:
        sid = "sess-review-focus-1"
        SESSION_STORE.add_file(
            sid,
            {
                "file_id": "f1",
                "filename": "ho_so.txt",
                "size_bytes": 12,
                "ext": ".txt",
                "extracted_text": "Nội dung mật trong phiên",
                "parse_note": "ok",
                "uploaded_at": "2026-11-18T00:00:00Z",
            },
        )
        SESSION_STORE.append_message(
            sid,
            {
                "role": "user",
                "mode": "nghiep_vu",
                "content": "Tóm tắt hồ sơ",
                "citations": [],
                "created_at": "2026-11-18T00:00:00Z",
            },
        )
        self.assertTrue(SESSION_STORE.wipe(sid))
        fresh = SESSION_STORE.get_or_create(sid)
        self.assertEqual(fresh["files"], [])
        self.assertEqual(fresh["messages"], [])

    def test_log_audit_persists_entry(self) -> None:
        log_audit(
            "tsh.co@tshorg.vn",
            "VP",
            "M01",
            "WIPE_SESSION",
            "Đã xóa bộ nhớ phiên",
            self.db_path,
        )
        with get_conn(self.db_path) as conn:
            row = conn.execute(
                "SELECT action, module_code FROM audit_logs ORDER BY id DESC LIMIT 1"
            ).fetchone()
            self.assertEqual(row["action"], "WIPE_SESSION")
            self.assertEqual(row["module_code"], "M01")


if __name__ == "__main__":
    unittest.main()

