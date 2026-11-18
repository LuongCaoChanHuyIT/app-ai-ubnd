from __future__ import annotations

import contextlib
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

DEFAULT_DB_PATH = Path(__file__).resolve().parent / "data" / "ubnd_ai.db"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_db_path() -> Path:
    env_path = os.environ.get("UBND_DB_PATH")
    if env_path:
        return Path(env_path).resolve()
    return DEFAULT_DB_PATH


@contextlib.contextmanager
def get_conn(db_path: Path | str | None = None) -> Iterator[sqlite3.Connection]:
    resolved = Path(db_path).resolve() if db_path else get_db_path()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(resolved), timeout=15.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        yield conn
    finally:
        conn.close()


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS departments (
    id TEXT PRIMARY KEY,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    scope_summary TEXT NOT NULL,
    instruction TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS official_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_number TEXT NOT NULL,
    title TEXT NOT NULL,
    doc_type TEXT NOT NULL,
    tier TEXT NOT NULL,
    department_id TEXT NOT NULL,
    issuer TEXT NOT NULL,
    issued_date TEXT NOT NULL,
    status TEXT NOT NULL,
    summary TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS doc_update_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_number TEXT NOT NULL,
    title TEXT NOT NULL,
    tier TEXT NOT NULL,
    department_id TEXT NOT NULL,
    reason TEXT NOT NULL,
    requested_by TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    department_id TEXT NOT NULL,
    assignee TEXT NOT NULL,
    due_date TEXT NOT NULL,
    priority TEXT NOT NULL,
    status TEXT NOT NULL,
    progress INTEGER NOT NULL DEFAULT 0,
    ref_doc_number TEXT NOT NULL DEFAULT '',
    reminder_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users_rbac (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    full_name TEXT NOT NULL,
    position TEXT NOT NULL,
    role TEXT NOT NULL,
    department_id TEXT NOT NULL,
    private_repo_access INTEGER NOT NULL DEFAULT 1,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS api_connectors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    provider TEXT NOT NULL,
    base_url TEXT NOT NULL,
    model_name TEXT NOT NULL,
    api_key TEXT NOT NULL DEFAULT '',
    active INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor_email TEXT NOT NULL,
    department_id TEXT NOT NULL,
    module_code TEXT NOT NULL,
    action TEXT NOT NULL,
    detail TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cloned_tenants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT NOT NULL UNIQUE,
    commune_name TEXT NOT NULL,
    admin_email TEXT NOT NULL,
    db_path TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


def init_db(
    db_path: Path | str | None = None,
    commune_name: str = "UBND Xã/Phường Trung Tâm",
    owner_email: str = "tsh.co@tshorg.vn",
) -> None:
    now = utc_now_iso()
    with get_conn(db_path) as conn:
        conn.executescript(SCHEMA_SQL)

        dept_count = conn.execute("SELECT COUNT(*) AS c FROM departments").fetchone()["c"]
        if dept_count == 0:
            departments = [
                (
                    "VP",
                    "VP",
                    "Văn phòng HĐND & UBND",
                    "Tổng hợp, văn thư, tư pháp - hộ tịch, tiếp công dân và kiểm soát TTHC",
                    f"Tham mưu cho {commune_name} đúng thể thức Nghị định 30/2020/NĐ-CP, Luật Tổ chức chính quyền địa phương, Luật Hộ tịch và Luật Tiếp công dân. Luôn phân biệt rõ thẩm quyền tập thể UBND và thẩm quyền riêng của Chủ tịch UBND cấp xã.",
                    now,
                ),
                (
                    "KT",
                    "KT",
                    "Kinh tế",
                    "Tài chính - ngân sách xã, kế hoạch đầu tư công, thương mại - dịch vụ và hộ kinh doanh",
                    f"Tham mưu cho bộ phận Kinh tế thuộc {commune_name} theo Luật Ngân sách nhà nước, Luật Đầu tư công và các quy định quản lý tài sản công, dự toán thu chi ngân sách cấp xã.",
                    now,
                ),
                (
                    "VHXH",
                    "VHXH",
                    "Văn hóa - Xã hội",
                    "Chính sách người có công, bảo trợ xã hội, giáo dục, y tế cơ sở và thông tin tuyên truyền",
                    f"Tham mưu cho bộ phận Văn hóa - Xã hội thuộc {commune_name} bảo đảm đúng đối tượng, định mức trợ cấp xã hội, chính sách người có công và quy định quản lý lễ hội, văn hóa cơ sở.",
                    now,
                ),
                (
                    "NNMT",
                    "NNMT",
                    "Nông nghiệp và Môi trường",
                    "Địa chính - đất đai, trật tự xây dựng, tài nguyên môi trường và nông thôn mới",
                    f"Tham mưu cho bộ phận Nông nghiệp và Môi trường thuộc {commune_name} theo Luật Đất đai, Luật Bảo vệ môi trường; rà soát kỹ nguồn gốc sử dụng đất, hiện trạng quy hoạch và thẩm quyền hòa giải tranh chấp đất đai tại cấp xã.",
                    now,
                ),
            ]
            conn.executemany(
                "INSERT INTO departments(id, code, name, scope_summary, instruction, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                departments,
            )

        doc_count = conn.execute("SELECT COUNT(*) AS c FROM official_documents").fetchone()["c"]
        if doc_count == 0:
            docs = [
                (
                    "30/2020/NĐ-CP",
                    "Nghị định về công tác văn thư",
                    "Nghị định",
                    "trung_uong",
                    "ALL",
                    "Chính phủ",
                    "2020-03-05",
                    "con_hieu_luc",
                    "Quy định chuẩn thể thức, kỹ thuật trình bày văn bản hành chính, quản lý văn bản đi/đến và lập hồ sơ công việc.",
                    "Điều 8 quy định các thành phần thể thức văn bản hành chính gồm: Quốc hiệu và Tiêu ngữ; Tên cơ quan, tổ chức ban hành văn bản; Số, ký hiệu của văn bản; Địa danh và thời gian ban hành; Tên loại và trích yếu nội dung; Nội dung văn bản; Chức vụ, họ tên và chữ ký của người có thẩm quyền; Dấu, chữ ký số của cơ quan; Nơi nhận.",
                    now,
                ),
                (
                    "399/2026/NĐ-CP",
                    "Nghị định quy định chi tiết phân cấp và chuyển đổi số trong giải quyết thủ tục hành chính cấp cơ sở",
                    "Nghị định",
                    "trung_uong",
                    "ALL",
                    "Chính phủ",
                    "2026-11-02",
                    "moi_cap_nhat",
                    "Quy định chuẩn hóa quy trình tiếp nhận, số hóa hồ sơ và phối hợp liên thông điện tử tại UBND cấp xã, phường.",
                    "UBND cấp xã, phường thực hiện tiếp nhận, số hóa thành phần hồ sơ ngay tại Bộ phận Một cửa; tái sử dụng dữ liệu hộ tịch, dân cư và đất đai đã được xác thực, không yêu cầu công dân nộp lại bản sao giấy tờ đã có trên kho dữ liệu số.",
                    now,
                ),
                (
                    "65/2025/QH15",
                    "Luật Tổ chức chính quyền địa phương (sửa đổi)",
                    "Luật",
                    "trung_uong",
                    "ALL",
                    "Quốc hội",
                    "2025-06-19",
                    "con_hieu_luc",
                    "Quy định nhiệm vụ, quyền hạn của HĐND, UBND và Chủ tịch UBND cấp xã, phường.",
                    "UBND cấp xã thảo luận tập thể và quyết định kế hoạch phát triển kinh tế - xã hội, dự toán ngân sách trình HĐND cùng cấp. Chủ tịch UBND cấp xã lãnh đạo, điều hành công việc của UBND, quyết định xử phạt vi phạm hành chính, giải quyết khiếu nại, tố cáo và ký văn bản theo thẩm quyền cá nhân.",
                    now,
                ),
                (
                    "31/2024/QH15",
                    "Luật Đất đai",
                    "Luật",
                    "trung_uong",
                    "ALL",
                    "Quốc hội",
                    "2024-01-18",
                    "con_hieu_luc",
                    "Quy định trách nhiệm của UBND cấp xã trong xác nhận nguồn gốc sử dụng đất và hòa giải tranh chấp đất đai.",
                    "Điều 235 quy định UBND cấp xã có trách nhiệm tổ chức hòa giải tranh chấp đất đai tại địa phương trong thời hạn không quá 30 ngày kể từ ngày nhận được đơn yêu cầu hòa giải; lập biên bản hòa giải thành hoặc không thành có chữ ký các bên.",
                    now,
                ),
                (
                    "24/2026/QĐ-UBND",
                    "Quyết định ban hành Quy chế phối hợp giải quyết thủ tục hành chính liên thông cấp phường, xã",
                    "Quyết định",
                    "dia_phuong",
                    "ALL",
                    "UBND Thành phố",
                    "2026-08-15",
                    "con_hieu_luc",
                    "Quy định thời hạn phối hợp nội bộ giữa Văn phòng, Kinh tế, Văn hóa - Xã hội và Nông nghiệp - Môi trường.",
                    "Các bộ phận chuyên môn trực thuộc UBND xã, phường có trách nhiệm cho ý kiến thẩm định phối hợp trong tối đa 02 ngày làm việc kể từ khi nhận phiếu chuyển trên hệ thống điều hành.",
                    now,
                ),
                (
                    "QC-01/2026/UBND-VP",
                    f"Quy chế làm việc nội bộ Văn phòng HĐND & UBND ({commune_name})",
                    "Quy chế nội bộ",
                    "kho_rieng",
                    "VP",
                    commune_name,
                    "2026-09-01",
                    "con_hieu_luc",
                    "Tài liệu nội bộ riêng của Văn phòng HĐND & UBND về quy trình duyệt thể thức trước khi trình ký.",
                    "Mọi dự thảo Quyết định, Báo cáo, Kế hoạch trình Lãnh đạo UBND phải qua bước kiểm soát thể thức, căn cứ pháp lý và thẩm quyền tại Văn phòng trước 15h00 hàng ngày.",
                    now,
                ),
                (
                    "HD-02/2026/UBND-KT",
                    f"Hướng dẫn nội bộ rà soát chứng từ dự toán ngân sách xã ({commune_name})",
                    "Hướng dẫn nội bộ",
                    "kho_rieng",
                    "KT",
                    commune_name,
                    "2026-09-10",
                    "con_hieu_luc",
                    "Kho dữ liệu riêng bộ phận Kinh tế phục vụ kiểm tra hồ sơ thanh quyết toán.",
                    "Hồ sơ đề nghị chi thường xuyên phải đối chiếu khớp mã nguồn ngân sách, dự toán đầu năm được HĐND thông qua và biên bản nghiệm thu khối lượng.",
                    now,
                ),
                (
                    "HD-03/2026/UBND-NNMT",
                    f"Sổ tay nội bộ xác minh hiện trạng đất đai & trật tự xây dựng ({commune_name})",
                    "Sổ tay nội bộ",
                    "kho_rieng",
                    "NNMT",
                    commune_name,
                    "2026-09-15",
                    "con_hieu_luc",
                    "Kho dữ liệu riêng bộ phận Nông nghiệp và Môi trường.",
                    "Khi xác nhận nguồn gốc đất, công chức địa chính bắt buộc đối chiếu tờ bản đồ địa chính qua các thời kỳ, sổ mục kê và biên bản lấy ý kiến khu dân cư.",
                    now,
                ),
            ]
            conn.executemany(
                """
                INSERT INTO official_documents(
                    doc_number, title, doc_type, tier, department_id,
                    issuer, issued_date, status, summary, content, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                docs,
            )

        task_count = conn.execute("SELECT COUNT(*) AS c FROM tasks").fetchone()["c"]
        if task_count == 0:
            seed_tasks = [
                (
                    "Tổng hợp báo cáo kết quả cải cách hành chính tháng 11/2026",
                    "Rà soát số liệu hồ sơ đúng hạn tại Bộ phận Một cửa và trình Lãnh đạo UBND ký ban hành.",
                    "VP",
                    "Nguyễn Minh Tuấn",
                    "2026-11-22",
                    "cao",
                    "dang_thuc_hien",
                    70,
                    "399/2026/NĐ-CP",
                    0,
                    now,
                    now,
                ),
                (
                    "Lập dự toán thu - chi ngân sách địa phương năm 2027",
                    "Tổng hợp đề xuất kinh phí từ các bộ phận để trình kỳ họp HĐND cuối năm.",
                    "KT",
                    "Trần Thị Mai",
                    "2026-11-25",
                    "khan",
                    "sap_den_han",
                    45,
                    "HD-02/2026/UBND-KT",
                    1,
                    now,
                    now,
                ),
                (
                    "Rà soát danh sách chi trả trợ cấp bảo trợ xã hội đợt tháng 11",
                    "Đối chiếu biến động nhân khẩu với dữ liệu hộ tịch trước khi trình phê duyệt.",
                    "VHXH",
                    "Lê Hoàng Nam",
                    "2026-11-20",
                    "trung_binh",
                    "hoan_thanh",
                    100,
                    "24/2026/QĐ-UBND",
                    0,
                    now,
                    now,
                ),
                (
                    "Xác minh thực địa và tổ chức hòa giải hồ sơ tranh chấp ranh giới thửa đất số 42",
                    "Lập biên bản xác minh hiện trạng và thông báo lịch hòa giải cho các hộ liền kề.",
                    "NNMT",
                    "Phạm Quốc Bảo",
                    "2026-11-21",
                    "cao",
                    "sap_den_han",
                    60,
                    "31/2024/QH15",
                    1,
                    now,
                    now,
                ),
            ]
            conn.executemany(
                """
                INSERT INTO tasks(
                    title, description, department_id, assignee, due_date,
                    priority, status, progress, ref_doc_number, reminder_count, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                seed_tasks,
            )

        user_count = conn.execute("SELECT COUNT(*) AS c FROM users_rbac").fetchone()["c"]
        if user_count == 0:
            owner_clean = owner_email.strip().lower()
            default_officers = [
                ("canbo.vp@ubnd.vn", "Nguyễn Minh Tuấn", "Công chức Văn phòng - Thống kê", "officer", "VP", 1, 1, now),
                ("canbo.kt@ubnd.vn", "Trần Thị Mai", "Công chức Tài chính - Kế toán", "officer", "KT", 1, 1, now),
                ("canbo.vhxh@ubnd.vn", "Lê Hoàng Nam", "Công chức Văn hóa - Xã hội", "officer", "VHXH", 1, 1, now),
                ("canbo.nnmt@ubnd.vn", "Phạm Quốc Bảo", "Công chức Địa chính - Môi trường", "officer", "NNMT", 1, 1, now),
            ]
            users = [
                (owner_clean, "Quản trị viên Hệ thống (TSH)", "Chủ sở hữu hệ thống", "owner", "VP", 1, 1, now),
                *[u for u in default_officers if u[0].lower() != owner_clean],
            ]
            conn.executemany(
                """
                INSERT INTO users_rbac(
                    email, full_name, position, role, department_id,
                    private_repo_access, active, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                users,
            )

        conn_count = conn.execute("SELECT COUNT(*) AS c FROM api_connectors").fetchone()["c"]
        if conn_count == 0:
            conn.execute(
                """
                INSERT INTO api_connectors(name, provider, base_url, model_name, api_key, active, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "Cổng LLM Nội bộ / OpenAI-Compatible",
                    "openai-compatible",
                    "https://api.openai.com/v1",
                    "gpt-4o-mini",
                    "",
                    0,
                    now,
                ),
            )

        conn.commit()


def can_access_private_docs(
    actor_email: str,
    target_dept_id: str,
    db_path: Path | str | None = None,
) -> bool:
    email = (actor_email or "").strip().lower()
    if not email:
        return False
    with get_conn(db_path) as conn:
        row = conn.execute(
            "SELECT role, department_id, private_repo_access, active FROM users_rbac WHERE lower(email) = ?",
            (email,),
        ).fetchone()
        if not row or not row["active"]:
            return False
        if row["role"] == "owner":
            return True
        return bool(row["private_repo_access"]) and row["department_id"] == target_dept_id


def log_audit(
    actor_email: str,
    department_id: str,
    module_code: str,
    action: str,
    detail: str,
    db_path: Path | str | None = None,
) -> None:
    with get_conn(db_path) as conn:
        conn.execute(
            """
            INSERT INTO audit_logs(actor_email, department_id, module_code, action, detail, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (actor_email, department_id, module_code, action, detail, utc_now_iso()),
        )
        conn.commit()


class EphemeralSessionStore:
    """In-memory session store ensuring session files and chat never touch disk."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sessions: dict[str, dict[str, Any]] = {}

    def get_or_create(self, session_id: str) -> dict[str, Any]:
        with self._lock:
            if session_id not in self._sessions:
                self._sessions[session_id] = {
                    "session_id": session_id,
                    "created_at": utc_now_iso(),
                    "files": [],
                    "messages": [],
                }
            state = self._sessions[session_id]
            return {
                "session_id": state["session_id"],
                "created_at": state["created_at"],
                "files": list(state["files"]),
                "messages": list(state["messages"]),
            }

    def add_file(self, session_id: str, record: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            if session_id not in self._sessions:
                self._sessions[session_id] = {
                    "session_id": session_id,
                    "created_at": utc_now_iso(),
                    "files": [],
                    "messages": [],
                }
            self._sessions[session_id]["files"].append(dict(record))
        return self.get_or_create(session_id)

    def append_message(self, session_id: str, msg: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            if session_id not in self._sessions:
                self._sessions[session_id] = {
                    "session_id": session_id,
                    "created_at": utc_now_iso(),
                    "files": [],
                    "messages": [],
                }
            self._sessions[session_id]["messages"].append(dict(msg))
        return self.get_or_create(session_id)

    def wipe(self, session_id: str) -> bool:
        with self._lock:
            existed = session_id in self._sessions
            self._sessions.pop(session_id, None)
            return existed


SESSION_STORE = EphemeralSessionStore()
