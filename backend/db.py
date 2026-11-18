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
CREATE TABLE IF NOT EXISTS tenant_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

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


def _build_seed_documents(commune_name: str, now: str) -> list[tuple[Any, ...]]:
    """Return 36 substantive commune-level legal & internal documents across VP (10), KT (8), VHXH (8), NNMT (10)."""
    return [
        # =====================================================================
        # PHÒNG VP — VĂN PHÒNG HĐND & UBND (10 văn bản: 8 chính thức + 2 kho_rieng)
        # =====================================================================
        (
            "65/2025/QH15",
            "Luật Tổ chức chính quyền địa phương",
            "Luật",
            "trung_uong",
            "VP",
            "Quốc hội",
            "2025-06-19",
            "con_hieu_luc",
            "Phân định rõ nhiệm vụ, quyền hạn giữa tập thể HĐND cấp xã, tập thể UBND cấp xã và cá nhân Chủ tịch UBND cấp xã.",
            (
                "1. Thẩm quyền tập thể HĐND cấp xã: ban hành Nghị quyết về kế hoạch phát triển kinh tế - xã hội hằng năm, "
                "quyết định dự toán thu - chi và phân bổ ngân sách cấp xã, phê chuẩn quyết toán ngân sách xã, giám sát hoạt động của UBND cùng cấp. "
                "2. Thẩm quyền tập thể UBND cấp xã: thảo luận tập thể và quyết định theo đa số đối với Quy chế làm việc của UBND xã, "
                "kế hoạch phát triển kinh tế - xã hội, dự toán ngân sách trình HĐND xã, các biện pháp quản lý hành chính nhà nước và đề án lớn trên địa bàn "
                "(văn bản ký thay mặt tập thể ghi 'TM. ỦY BAN NHÂN DÂN'). "
                "3. Thẩm quyền cá nhân Chủ tịch UBND cấp xã: lãnh đạo, điều hành công việc của UBND; quyết định xử phạt vi phạm hành chính, "
                "giải quyết khiếu nại lần đầu, giải quyết tố cáo đối với cán bộ công chức thuộc quyền quản lý, quyết định tặng danh hiệu Gia đình văn hóa, "
                "thành lập các tổ kiểm tra/hội đồng tư vấn/hội đồng hòa giải và áp dụng biện pháp bảo vệ trẻ em khẩn cấp "
                "(văn bản ký trực tiếp ghi chức danh 'CHỦ TỊCH', không ghi 'TM. ỦY BAN NHÂN DÂN')."
            ),
            now,
        ),
        (
            "30/2020/NĐ-CP",
            "Nghị định về công tác văn thư",
            "Nghị định",
            "trung_uong",
            "VP",
            "Chính phủ",
            "2020-03-05",
            "con_hieu_luc",
            "Quy định chuẩn thể thức, kỹ thuật trình bày văn bản hành chính (Điều 8–13), Phụ lục I chữ viết tắt ký hiệu, thẩm quyền ký và Nơi nhận.",
            (
                "Điều 8–13 quy định 09 thành phần thể thức văn bản hành chính: (1) Quốc hiệu và Tiêu ngữ; (2) Tên cơ quan, tổ chức ban hành văn bản; "
                "(3) Số, ký hiệu của văn bản; (4) Địa danh và thời gian ban hành văn bản (ngày dưới 10 và tháng 1, 2 ghi thêm số 0 phía trước); "
                "(5) Tên loại và trích yếu nội dung văn bản; (6) Nội dung văn bản; (7) Chức vụ, họ tên và chữ ký của người có thẩm quyền; "
                "(8) Dấu, chữ ký số của cơ quan; (9) Nơi nhận. "
                "Phụ lục I quy định chữ viết tắt tên loại văn bản có tên loại: Quyết định (QĐ-UBND), Kế hoạch (KH-UBND), Báo cáo (BC-UBND), "
                "Thông báo (TB-UBND), Tờ trình (TTr-UBND); riêng Kế hoạch và Báo cáo ghi trực tiếp trích yếu dưới tên loại văn bản, KHÔNG ghi cụm từ 'Về việc'. "
                "Công văn là văn bản hành chính không có tên loại, ký hiệu ghi Số: .../UBND-VP (hoặc mã phòng soạn thảo KT, VHXH, NNMT) và trích yếu ghi 'V/v ...'. "
                "Quy tắc ký: làm việc theo chế độ tập thể ghi 'TM. ỦY BAN NHÂN DÂN / CHỦ TỊCH' (hoặc KT. CHỦ TỊCH / PHÓ CHỦ TỊCH); "
                "thẩm quyền riêng người đứng đầu ghi 'CHỦ TỊCH'. Nơi nhận không liệt kê lại chính chức danh người trực tiếp ký và kết thúc bằng 'Lưu: VT, [Đơn vị soạn thảo].'."
            ),
            now,
        ),
        (
            "60/2014/QH13",
            "Luật Hộ tịch (kèm quy định chi tiết thi hành tại Nghị định 123/2015/NĐ-CP)",
            "Luật",
            "trung_uong",
            "VP",
            "Quốc hội",
            "2014-11-20",
            "con_hieu_luc",
            "Quy định thẩm quyền, trình tự đăng ký khai sinh, kết hôn, khai tử, nhận cha mẹ con và cấp Giấy xác nhận tình trạng hôn nhân tại UBND cấp xã.",
            (
                "UBND cấp xã nơi cư trú của công dân thực hiện đăng ký khai sinh (giải quyết ngay trong ngày tiếp nhận đủ hồ sơ hợp lệ), "
                "đăng ký kết hôn (hai bên nam, nữ phải có mặt trực tiếp ký vào Sổ đăng ký kết hôn và Giấy chứng nhận kết hôn), đăng ký khai tử, "
                "đăng ký nhận cha, mẹ, con không có yếu tố nước ngoài và thay đổi, cải chính hộ tịch cho người chưa đủ 14 tuổi. "
                "Theo Nghị định 123/2015/NĐ-CP, thủ tục cấp Giấy xác nhận tình trạng hôn nhân giải quyết trong thời hạn 03 ngày làm việc kể từ ngày nhận đủ hồ sơ; "
                "trường hợp công dân đã từng cư trú tại nhiều nơi khác nhau cần gửi văn bản xác minh thì thời hạn giải quyết không quá 20 ngày."
            ),
            now,
        ),
        (
            "42/2013/QH13",
            "Luật Tiếp công dân",
            "Luật",
            "trung_uong",
            "VP",
            "Quốc hội",
            "2013-11-25",
            "con_hieu_luc",
            "Quy định trách nhiệm tổ chức tiếp công dân thường xuyên và lịch tiếp công dân định kỳ hằng tuần của Chủ tịch UBND cấp xã.",
            (
                "Điều 15 Luật Tiếp công dân quy định việc tiếp công dân tại cấp xã được thực hiện tại trụ sở UBND cấp xã. "
                "Chủ tịch UBND cấp xã trực tiếp phụ trách công tác tiếp công dân tại địa phương: phân công công chức Văn phòng - Thống kê / Tư pháp thường trực tiếp công dân, "
                "niêm yết công khai nội quy và lịch tiếp công dân; Chủ tịch UBND cấp xã phải trực tiếp tiếp công dân định kỳ ít nhất 01 ngày trong 01 tuần "
                "và tiếp công dân đột xuất trong trường hợp vụ việc gay gắt, phức tạp, có nhiều người tham gia hoặc có nguy cơ ảnh hưởng an ninh, trật tự cơ sở."
            ),
            now,
        ),
        (
            "02/2011/QH13",
            "Luật Khiếu nại",
            "Luật",
            "trung_uong",
            "VP",
            "Quốc hội",
            "2011-11-11",
            "con_hieu_luc",
            "Quy định thẩm quyền Chủ tịch UBND cấp xã giải quyết khiếu nại lần đầu, thời hạn thụ lý 10 ngày và thời hạn giải quyết 30–45 ngày.",
            (
                "Điều 17 Luật Khiếu nại quy định Chủ tịch UBND cấp xã có thẩm quyền giải quyết khiếu nại lần đầu đối với quyết định hành chính, "
                "hành vi hành chính của mình và của người có trách nhiệm do mình quản lý trực tiếp. "
                "Điều 27, Điều 28 quy định thời hạn thụ lý để giải quyết là 10 ngày kể từ ngày nhận được khiếu nại thuộc thẩm quyền; "
                "thời hạn giải quyết khiếu nại lần đầu không quá 30 ngày kể từ ngày thụ lý (đối với vụ việc phức tạp thì không quá 45 ngày; "
                "ở vùng sâu, vùng xa đi lại khó khăn thời hạn không quá 45 ngày, vụ việc phức tạp không quá 60 ngày). "
                "Trước khi ban hành Quyết định giải quyết khiếu nại lần đầu (ký chức danh CHỦ TỊCH), bắt buộc phải tổ chức đối thoại với người khiếu nại và lập biên bản đối thoại."
            ),
            now,
        ),
        (
            "25/2018/QH14",
            "Luật Tố cáo",
            "Luật",
            "trung_uong",
            "VP",
            "Quốc hội",
            "2018-06-12",
            "con_hieu_luc",
            "Quy định thẩm quyền của Chủ tịch UBND cấp xã giải quyết tố cáo hành vi vi phạm pháp luật của cán bộ, công chức cấp xã và bảo vệ người tố cáo.",
            (
                "Điều 13 Luật Tố cáo quy định Chủ tịch UBND cấp xã có thẩm quyền giải quyết tố cáo hành vi vi phạm pháp luật trong việc thực hiện nhiệm vụ, "
                "công vụ của cán bộ, công chức khác do mình quản lý trực tiếp. Thời hạn giải quyết tố cáo không quá 30 ngày kể từ ngày thụ lý tố cáo; "
                "trường hợp vụ việc phức tạp thì có thể gia hạn giải quyết tố cáo một lần nhưng không quá 30 ngày. "
                "UBND và công chức tham mưu phải giữ bí mật tuyệt đối họ tên, địa chỉ, bút tích của người tố cáo theo Chương VI Luật Tố cáo."
            ),
            now,
        ),
        (
            "61/2018/NĐ-CP",
            "Nghị định về thực hiện cơ chế một cửa, một cửa liên thông trong giải quyết thủ tục hành chính (sửa đổi, bổ sung tại Nghị định 107/2021/NĐ-CP)",
            "Nghị định",
            "trung_uong",
            "VP",
            "Chính phủ",
            "2018-04-23",
            "con_hieu_luc",
            "Quy định quy trình tiếp nhận, số hóa hồ sơ, trả kết quả điện tử và tái sử dụng dữ liệu tại Bộ phận Một cửa UBND cấp xã.",
            (
                "Nghị định 61/2018/NĐ-CP và Nghị định 107/2021/NĐ-CP quy định Bộ phận Tiếp nhận và Trả kết quả cấp xã thực hiện kiểm tra tính đầy đủ, "
                "lập Giấy tiếp nhận hồ sơ và hẹn trả kết quả, thực hiện số hóa thành phần hồ sơ và kết quả giải quyết thủ tục hành chính gắn chữ ký số "
                "lưu vào Kho quản lý dữ liệu điện tử của tổ chức, cá nhân; kết nối, khai thác Cơ sở dữ liệu quốc gia về dân cư, không yêu cầu công dân nộp lại "
                "bản sao chứng thực đối với thông tin, giấy tờ đã được xác thực điện tử."
            ),
            now,
        ),
        (
            "23/2015/NĐ-CP",
            "Nghị định về cấp bản sao từ sổ gốc, chứng thực bản sao từ bản chính, chứng thực chữ ký và chứng thực hợp đồng, giao dịch",
            "Nghị định",
            "trung_uong",
            "VP",
            "Chính phủ",
            "2015-02-16",
            "con_hieu_luc",
            "Quy định thẩm quyền và thời hạn chứng thực bản sao, chứng thực chữ ký, chứng thực hợp đồng giao dịch tại UBND cấp xã.",
            (
                "Điều 5 Nghị định 23/2015/NĐ-CP quy định UBND cấp xã có thẩm quyền: chứng thực bản sao từ bản chính các giấy tờ, văn bản do cơ quan có thẩm quyền của Việt Nam cấp bằng tiếng Việt; "
                "chứng thực chữ ký trong các giấy tờ, văn bản (trừ chứng thực chữ ký người dịch thuộc thẩm quyền theo quy định riêng); "
                "chứng thực hợp đồng, giao dịch liên quan đến tài sản là động sản, quyền sử dụng đất, nhà ở và di chúc, văn bản khai nhận/thỏa thuận phân chia di sản. "
                "Chủ tịch, Phó Chủ tịch UBND cấp xã thực hiện ký chứng thực và đóng dấu của UBND cấp xã; thời hạn thực hiện ngay trong ngày tiếp nhận yêu cầu "
                "hoặc trong ngày làm việc tiếp theo nếu tiếp nhận sau 15 giờ."
            ),
            now,
        ),
        (
            "QC-01/2026/UBND-VP",
            f"Quy chế làm việc mẫu của UBND cấp xã và phối hợp liên thông nội bộ ({commune_name})",
            "Quy chế nội bộ",
            "kho_rieng",
            "VP",
            commune_name,
            "2026-09-01",
            "con_hieu_luc",
            "Tài liệu kho riêng Văn phòng HĐND & UBND (mã tham chiếu QC-01/VP-UBND) về chế độ hội họp, trình ký và phối hợp giữa 04 bộ phận.",
            (
                "Quy chế làm việc nội bộ mã QC-01/VP-UBND quy định: các bộ phận chuyên môn (VP, KT, VHXH, NNMT) khi nhận phiếu lấy ý kiến phối hợp liên thông "
                "phải phản hồi bằng văn bản trên hệ thống trong tối đa 02 ngày làm việc; tờ trình kèm dự thảo thuộc thẩm quyền tập thể UBND phải lấy đủ ý kiến thành viên UBND trước khi ban hành."
            ),
            now,
        ),
        (
            "QT-02/2026/UBND-VP",
            f"Quy trình kiểm soát thể thức và thẩm quyền văn bản trước khi trình ký ban hành ({commune_name})",
            "Quy trình nội bộ",
            "kho_rieng",
            "VP",
            commune_name,
            "2026-09-05",
            "con_hieu_luc",
            "Danh mục kiểm tra 05 điểm bắt buộc tại bộ phận Văn thư - Văn phòng trước 15h00 hằng ngày trước khi trình Lãnh đạo UBND ký số.",
            (
                "Mọi dự thảo Quyết định, Kế hoạch, Báo cáo, Tờ trình, Thông báo, Công văn trình Lãnh đạo UBND phải được công chức Văn phòng rà soát: "
                "(1) Đúng ký hiệu Phụ lục I Nghị định 30/2020/NĐ-CP; (2) Không lặp 'Về việc Về việc' và không ghi 'Về việc' trên Báo cáo, Kế hoạch; "
                "(3) Đúng thẩm quyền ký TM. ỦY BAN NHÂN DÂN hay CHỦ TỊCH; (4) Căn cứ pháp lý còn hiệu lực; (5) Đầy đủ Nơi nhận và Lưu: VT."
            ),
            now,
        ),
        # =====================================================================
        # PHÒNG KT — KINH TẾ (8 văn bản: 6 chính thức + 2 kho_rieng)
        # =====================================================================
        (
            "83/2015/QH13",
            "Luật Ngân sách nhà nước (kèm Thông tư 344/2016/TT-BTC quy định quản lý ngân sách xã và các hoạt động tài chính khác của xã, phường, thị trấn)",
            "Luật",
            "trung_uong",
            "KT",
            "Quốc hội & Bộ Tài chính",
            "2015-06-25",
            "con_hieu_luc",
            "Quy định lập dự toán, HĐND xã quyết định phân bổ, chấp hành chi qua Kho bạc Nhà nước và quyết toán, công khai ngân sách cấp xã.",
            (
                "Luật Ngân sách nhà nước số 83/2015/QH13 và Thông tư số 344/2016/TT-BTC của Bộ Tài chính quy định: "
                "UBND cấp xã lập dự toán thu ngân sách nhà nước trên địa bàn, dự toán thu - chi ngân sách xã và phương án phân bổ ngân sách xã trình HĐND cấp xã quyết định trước ngày 31/12 năm trước. "
                "Chủ tịch UBND cấp xã là Chủ tài khoản ngân sách xã (có thể ủy quyền Phó Chủ tịch); công chức Tài chính - Kế toán kiểm soát chứng từ hợp pháp, hợp lệ, "
                "đúng dự toán được giao trước khi lập Giấy rút dự toán gửi Kho bạc Nhà nước; thực hiện công khai dự toán và quyết toán ngân sách xã tại trụ sở UBND và thôn, tổ dân phố."
            ),
            now,
        ),
        (
            "58/2024/QH15",
            "Luật Đầu tư công",
            "Luật",
            "trung_uong",
            "KT",
            "Quốc hội",
            "2024-11-29",
            "con_hieu_luc",
            "Quy định trách nhiệm của UBND cấp xã khi làm chủ đầu tư dự án quy mô nhỏ, nông thôn mới và cơ chế giám sát đầu tư của cộng đồng.",
            (
                "Luật Đầu tư công số 58/2024/QH15 quy định trình tự lập, thẩm định, quyết định chủ trương đầu tư và quyết định đầu tư dự án đầu tư công cấp xã; "
                "khi UBND cấp xã làm chủ đầu tư các dự án cải tạo hạ tầng dân sinh, giao thông ngõ xóm, trường trạm quy mô nhỏ và chương trình mục tiêu quốc gia nông thôn mới, "
                "phải tuân thủ dự toán được duyệt, công khai thông tin dự án tại khu dân cư và tạo điều kiện để Ban Giám sát đầu tư của cộng đồng (do Ủy ban MTTQ Việt Nam cấp xã thành lập) giám sát chất lượng, tiến độ."
            ),
            now,
        ),
        (
            "15/2017/QH14",
            "Luật Quản lý, sử dụng tài sản công (kèm Nghị định 151/2017/NĐ-CP)",
            "Luật",
            "trung_uong",
            "KT",
            "Quốc hội",
            "2017-06-21",
            "con_hieu_luc",
            "Quy định lập hồ sơ, kiểm kê định kỳ hằng năm, bảo dưỡng trụ sở, trang thiết bị và nhà văn hóa thôn, tổ dân phố.",
            (
                "Luật Quản lý, sử dụng tài sản công số 15/2017/QH14 và Nghị định 151/2017/NĐ-CP quy định UBND cấp xã trực tiếp quản lý trụ sở làm việc, máy móc thiết bị, "
                "nhà văn hóa thôn/tổ dân phố, trạm truyền thanh và kết cấu hạ tầng cấp xã; bắt buộc mở sổ theo dõi tài sản công, tính hao mòn và tổ chức kiểm kê thực tế định kỳ chốt số liệu 0h00 ngày 01/01 hằng năm. "
                "Nghiêm cấm tự ý cho thuê mặt bằng trụ sở, nhà văn hóa hoặc thanh lý tài sản công khi chưa có quyết định phê duyệt của cơ quan có thẩm quyền."
            ),
            now,
        ),
        (
            "01/2021/NĐ-CP",
            "Nghị định về đăng ký doanh nghiệp, hộ kinh doanh và phối hợp quản lý chợ dân sinh, tiểu thủ công nghiệp cấp xã",
            "Nghị định",
            "trung_uong",
            "KT",
            "Chính phủ",
            "2021-01-04",
            "con_hieu_luc",
            "Quy định phối hợp hậu kiểm hộ kinh doanh cá thể, sắp xếp trật tự thương mại chợ hạng 3, chợ dân sinh và tiểu thủ công nghiệp tại xã, phường.",
            (
                "Nghị định 01/2021/NĐ-CP và quy định quản lý thương mại cơ sở giao UBND cấp xã phối hợp rà soát tình trạng hoạt động thực tế của hộ kinh doanh cá thể trên địa bàn, "
                "tổ chức quản lý chợ hạng 3 / điểm kinh doanh dân sinh, kiểm tra niêm yết giá, an toàn thực phẩm ngành Công Thương, phòng cháy chữa cháy tại chợ "
                "và khuyến khích phát triển nghề truyền thống, tiểu thủ công nghiệp, sản phẩm OCOP địa phương."
            ),
            now,
        ),
        (
            "38/2019/QH14",
            "Luật Quản lý thuế (quy định về Hội đồng tư vấn thuế xã, phường, thị trấn)",
            "Luật",
            "trung_uong",
            "KT",
            "Quốc hội",
            "2019-06-13",
            "con_hieu_luc",
            "Quy định tổ chức Hội đồng tư vấn thuế cấp xã tư vấn mức thuế khoán hộ kinh doanh và phối hợp thu thuế sử dụng đất phi nông nghiệp.",
            (
                "Điều 28 Luật Quản lý thuế số 38/2019/QH14 quy định Chủ tịch UBND cấp xã phối hợp cơ quan thuế vận hành Hội đồng tư vấn thuế xã, phường, thị trấn "
                "(gồm Lãnh đạo UBND xã, công chức Tài chính - Kế toán, đại diện MTTQ xã, Công an xã, Tổ trưởng dân phố/Trưởng thôn và đại diện hộ kinh doanh) "
                "để tư vấn về doanh thu và mức thuế khoán dự kiến ổn định đầu năm, mức điều chỉnh thuế đối với hộ kinh doanh, cá nhân kinh doanh; "
                "niêm yết công khai thông tin hộ khoán tại trụ sở UBND xã và phối hợp rà soát sổ bộ thu thuế sử dụng đất phi nông nghiệp."
            ),
            now,
        ),
        (
            "85/2019/TT-BTC",
            "Thông tư hướng dẫn về phí và lệ phí thuộc thẩm quyền của HĐND cấp tỉnh và chế độ thu, nộp phí, lệ phí tại Bộ phận Một cửa cấp xã",
            "Thông tư",
            "trung_uong",
            "KT",
            "Bộ Tài chính",
            "2019-11-29",
            "con_hieu_luc",
            "Quy định niêm yết mức thu, xuất biên lai điện tử, miễn lệ phí cho đối tượng chính sách và nộp ngân sách các khoản phí, lệ phí tại cấp xã.",
            (
                "UBND cấp xã thực hiện niêm yết công khai mức thu phí chứng thực, lệ phí hộ tịch tại Bộ phận Một cửa theo Nghị quyết của HĐND cấp tỉnh "
                "và quy định của Bộ Tài chính; thực hiện miễn lệ phí hộ tịch đối với người thuộc gia đình có công với cách mạng, người thuộc hộ nghèo, người khuyết tật "
                "và các trường hợp đăng ký khai sinh, kết hôn, khai tử đúng hạn; xuất biên lai thu phí, lệ phí điện tử và nộp đầy đủ vào Kho bạc Nhà nước theo định kỳ."
            ),
            now,
        ),
        (
            "HD-02/2026/UBND-KT",
            f"Hướng dẫn nội bộ kiểm soát hồ sơ thanh toán, tạm ứng Kho bạc Nhà nước cấp xã ({commune_name})",
            "Hướng dẫn nội bộ",
            "kho_rieng",
            "KT",
            commune_name,
            "2026-09-10",
            "con_hieu_luc",
            "Kho dữ liệu riêng Phòng Kinh tế (mã tham chiếu HD-02/KT-UBND) phục vụ rà soát chứng từ chi thường xuyên và tạm ứng ngân sách xã.",
            (
                "Hướng dẫn nội bộ mã HD-02/KT-UBND quy định hồ sơ đề nghị thanh toán hoặc tạm ứng chi ngân sách xã phải đủ 05 thành phần: "
                "(1) Dự toán/Kế hoạch chi đã được Chủ tịch UBND phê duyệt trong phạm vi dự toán HĐND xã giao; (2) Hợp đồng hoặc bảng báo giá cạnh tranh; "
                "(3) Biên bản nghiệm thu bàn giao khối lượng; (4) Hóa đơn điện tử hợp pháp; (5) Khớp đúng mã nguồn ngân sách, chương, tiểu mục mục lục ngân sách nhà nước."
            ),
            now,
        ),
        (
            "ST-03/2026/UBND-KT",
            f"Sổ tay đối chiếu dự toán - biên bản nghiệm thu công trình dân sinh và duy tu hạ tầng ({commune_name})",
            "Sổ tay nội bộ",
            "kho_rieng",
            "KT",
            commune_name,
            "2026-09-18",
            "con_hieu_luc",
            "Quy trình nội bộ Phòng Kinh tế đối chiếu chéo khối lượng thực tế và chữ ký Ban Giám sát đầu tư cộng đồng trước khi quyết toán.",
            (
                "Trước khi trình Chủ tịch UBND xã ký duyệt hồ sơ quyết toán công trình duy tu đường ngõ xóm, thoát nước, sửa chữa nhà văn hóa thôn, "
                "công chức Kinh tế bắt buộc đối chiếu khớp 100% giữa Bảng tổng hợp dự toán được duyệt, Nhật ký thi công, Biên bản nghiệm thu thực địa "
                "và Biên bản xác nhận của Ban Giám sát đầu tư của cộng đồng."
            ),
            now,
        ),
        # =====================================================================
        # PHÒNG VHXH — VĂN HÓA - XÃ HỘI (8 văn bản: 6 chính thức + 2 kho_rieng)
        # =====================================================================
        (
            "20/2021/NĐ-CP",
            "Nghị định quy định chính sách trợ giúp xã hội đối với đối tượng bảo trợ xã hội (điều chỉnh mức chuẩn tại Nghị định 76/2024/NĐ-CP)",
            "Nghị định",
            "trung_uong",
            "VHXH",
            "Chính phủ",
            "2021-03-15",
            "con_hieu_luc",
            "Quy định đối tượng bảo trợ xã hội, mức chuẩn trợ giúp xã hội 500.000 đồng/tháng (Nghị định 76/2024/NĐ-CP), hệ số và quy trình xét duyệt tại cấp xã.",
            (
                "Nghị định 20/2021/NĐ-CP và Nghị định 76/2024/NĐ-CP quy định mức chuẩn trợ giúp xã hội áp dụng từ ngày 01/7/2024 là 500.000 đồng/tháng "
                "(tăng từ 360.000 đồng/tháng), nhân với hệ số tương ứng từng nhóm đối tượng (trẻ em mồ côi, người khuyết tật nặng/đặc biệt nặng, "
                "người cao tuổi thuộc hộ nghèo không có người phụng dưỡng, người từ đủ 80 tuổi trở lên không có lương hưu/trợ cấp BHXH hằng tháng, người đơn thân nghèo nuôi con) "
                "và hỗ trợ chi phí mai táng tối thiểu bằng 20 lần mức chuẩn. Tại cấp xã: tiếp nhận tờ khai tại Bộ phận Một cửa, rà soát xác minh, "
                "niêm yết công khai kết quả xét duyệt tại trụ sở UBND cấp xã trong 02 ngày làm việc và hoàn thiện hồ sơ trình cấp có thẩm quyền quyết định trợ cấp."
            ),
            now,
        ),
        (
            "02/2020/UBTVQH14",
            "Pháp lệnh Ưu đãi người có công với cách mạng (kèm Nghị định 131/2021/NĐ-CP hướng dẫn thi hành)",
            "Pháp lệnh",
            "trung_uong",
            "VHXH",
            "Ủy ban Thường vụ Quốc hội",
            "2020-12-09",
            "con_hieu_luc",
            "Quy định trách nhiệm của UBND cấp xã trong tiếp nhận, xác nhận hồ sơ người có công, quản lý chi trả trợ cấp và thăm hỏi lễ, Tết.",
            (
                "Pháp lệnh số 02/2020/UBTVQH14 và Nghị định 131/2021/NĐ-CP quy định UBND cấp xã thực hiện tiếp nhận, kiểm tra, niêm yết công khai "
                "và xác nhận hồ sơ đề nghị công nhận, giải quyết chế độ ưu đãi đối với người có công với cách mạng và thân nhân liệt sĩ (thương binh, bệnh binh, "
                "người hoạt động kháng chiến bị nhiễm chất độc hóa học, Bà mẹ Việt Nam anh hùng, trợ cấp thờ cúng liệt sĩ); quản lý chi trả trợ cấp ưu đãi đúng kỳ hạn, "
                "chăm sóc nghĩa trang/nhà bia liệt sĩ và tổ chức rà soát danh sách thăm hỏi, tặng quà nhân dịp Tết Nguyên đán, ngày Thương binh - Liệt sĩ 27/7."
            ),
            now,
        ),
        (
            "110/2018/NĐ-CP",
            "Nghị định quy định về quản lý và tổ chức lễ hội",
            "Nghị định",
            "trung_uong",
            "VHXH",
            "Chính phủ",
            "2018-08-29",
            "con_hieu_luc",
            "Quy định trình tự thông báo, tổ chức lễ hội truyền thống tại xã, phường; bảo đảm an ninh trật tự, văn minh lễ hội và quản lý tiền công đức.",
            (
                "Nghị định 110/2018/NĐ-CP quy định UBND cấp xã chịu trách nhiệm quản lý nhà nước về hoạt động lễ hội trên địa bàn; "
                "thành lập Ban Tổ chức lễ hội đối với lễ hội thuộc thẩm quyền cấp xã, thực hiện thủ tục thông báo/đăng ký tổ chức lễ hội theo phân cấp, "
                "xây dựng phương án bảo đảm an ninh trật tự, phòng chống cháy nổ, an toàn giao thông, vệ sinh an toàn thực phẩm, vệ sinh môi trường; "
                "nghiêm cấm hoạt động mê tín dị đoan, cờ bạc trá hình, ép giá dịch vụ và bảo đảm thu - chi tiền công đức công khai, minh bạch."
            ),
            now,
        ),
        (
            "86/2023/NĐ-CP",
            "Nghị định quy định về khung tiêu chuẩn và trình tự, thủ tục, hồ sơ xét tặng danh hiệu Gia đình văn hóa, Thôn, tổ dân phố văn hóa, Xã, phường, thị trấn tiêu biểu",
            "Nghị định",
            "trung_uong",
            "VHXH",
            "Chính phủ",
            "2023-12-07",
            "con_hieu_luc",
            "Phân định rõ thẩm quyền cá nhân Chủ tịch UBND cấp xã quyết định tặng danh hiệu Gia đình văn hóa hằng năm trên cơ sở bình xét khu dân cư.",
            (
                "Nghị định 86/2023/NĐ-CP quy định trình tự bình xét công khai, dân chủ tại thôn, tổ dân phố đối với các hộ gia đình đăng ký thi đua hằng năm; "
                "Trưởng ban công tác Mặt trận phối hợp Trưởng thôn/Tổ trưởng tổ dân phố tổng hợp biên bản bình xét gửi UBND cấp xã. "
                "Thẩm quyền: cá nhân Chủ tịch UBND cấp xã ban hành Quyết định công nhận và tặng danh hiệu 'Gia đình văn hóa' hằng năm (ký chức danh CHỦ TỊCH, hoàn thành trước 25/11); "
                "UBND cấp xã hoàn thiện hồ sơ trình Chủ tịch UBND cấp trên xét tặng danh hiệu 'Thôn, tổ dân phố văn hóa'."
            ),
            now,
        ),
        (
            "07/2021/NĐ-CP",
            "Nghị định quy định chuẩn nghèo đa chiều giai đoạn 2021–2025 và quy trình rà soát hộ nghèo, hộ cận nghèo tại cấp xã",
            "Nghị định",
            "trung_uong",
            "VHXH",
            "Chính phủ",
            "2021-01-27",
            "con_hieu_luc",
            "Quy định tiêu chí thu nhập, mức độ thiếu hụt dịch vụ xã hội cơ bản và quy trình rà soát, niêm yết công khai hộ nghèo, hộ cận nghèo tại xã.",
            (
                "Nghị định 07/2021/NĐ-CP quy định chuẩn nghèo đa chiều gồm tiêu chí thu nhập và 06 chiều thiếu hụt dịch vụ xã hội cơ bản (việc làm, y tế, giáo dục, "
                "nhà ở, nước sạch và vệ sinh, thông tin). Hằng năm hoặc đột xuất khi công dân có giấy đề nghị, Ban Chỉ đạo rà soát cấp xã tổ chức nhận dạng nhanh, "
                "chấm điểm B1/B2, họp dân bình xét tại thôn/tổ dân phố có sự giám sát của MTTQ, niêm yết công khai kết quả trong 03 ngày làm việc tại nhà văn hóa thôn "
                "và trụ sở UBND xã trước khi Chủ tịch UBND cấp xã ký Quyết định công nhận danh sách hộ nghèo, hộ cận nghèo, hộ thoát nghèo."
            ),
            now,
        ),
        (
            "102/2016/QH13",
            "Luật Trẻ em (kèm Nghị định 56/2017/NĐ-CP quy định bảo vệ trẻ em ba cấp độ tại cơ sở)",
            "Luật",
            "trung_uong",
            "VHXH",
            "Quốc hội",
            "2016-04-05",
            "con_hieu_luc",
            "Quy định trách nhiệm bảo vệ trẻ em cấp độ phòng ngừa, hỗ trợ và thẩm quyền can thiệp khẩn cấp của Chủ tịch UBND cấp xã.",
            (
                "Điều 50, 51, 52 Luật Trẻ em số 102/2016/QH13 và Nghị định 56/2017/NĐ-CP quy định trách nhiệm của UBND và Chủ tịch UBND cấp xã trong bảo vệ trẻ em "
                "theo 03 cấp độ (phòng ngừa, hỗ trợ, can thiệp). Khi tiếp nhận thông tin trẻ em bị xâm hại, bạo lực, bóc lột, bỏ rơi hoặc có nguy cơ mất an toàn nghiêm trọng, "
                "người làm công tác bảo vệ trẻ em cấp xã phối hợp Công an xã và Trạm Y tế xác minh ngay tại hiện trường; Chủ tịch UBND cấp xã có thẩm quyền "
                "ra Quyết định tạm thời cách ly trẻ em khỏi cha, mẹ, người chăm sóc gây tổn hại trong trường hợp khẩn cấp (trong vòng 12 giờ) và phê duyệt Kế hoạch hỗ trợ, can thiệp."
            ),
            now,
        ),
        (
            "ST-01/2026/UBND-VHXH",
            f"Sổ tay nội bộ rà soát danh sách chi trả bảo trợ xã hội không dùng tiền mặt và đối soát biến động nhân khẩu ({commune_name})",
            "Sổ tay nội bộ",
            "kho_rieng",
            "VHXH",
            commune_name,
            "2026-09-12",
            "con_hieu_luc",
            "Kho dữ liệu riêng Phòng Văn hóa - Xã hội hướng dẫn đối soát liên thông Hộ tịch - Bảo trợ xã hội trước ngày 05 hằng tháng.",
            (
                "Định kỳ trước ngày 05 hằng tháng, công chức Văn hóa - Xã hội đối chiếu danh sách chi trả trợ cấp bảo trợ xã hội, người có công qua tài khoản an sinh "
                "với sổ đăng ký khai tử và danh sách chuyển khẩu để kịp thời tham mưu dừng/điều chỉnh trợ cấp, tuyệt đối không để phát sinh chi trùng hoặc chi quá kỳ."
            ),
            now,
        ),
        (
            "QT-02/2026/UBND-VHXH",
            f"Quy trình phối hợp Trường học - Trạm Y tế - Đoàn thể bảo vệ trẻ em và cứu trợ an sinh cơ sở ({commune_name})",
            "Quy trình nội bộ",
            "kho_rieng",
            "VHXH",
            commune_name,
            "2026-09-20",
            "con_hieu_luc",
            "Quy trình nội bộ Phòng Văn hóa - Xã hội phản ứng nhanh trong 02 giờ đối với ca bảo vệ trẻ em và hộ dân gặp thiên tai, hỏa hoạn.",
            (
                "Khi nhận tin báo từ nhà trường, Trạm Y tế xã, Tổng đài 111 hoặc Tổ dân phố về trẻ em bị bạo hành/bỏ rơi hoặc hộ dân gặp hỏa hoạn, tai nạn nặng, "
                "công chức VHXH kích hoạt tổ phối hợp liên ngành xác minh trong 02 giờ, lập biên bản đánh giá nguy cơ và tham mưu Chủ tịch UBND xã quyết định hỗ trợ đột xuất theo Nghị định 20/2021/NĐ-CP."
            ),
            now,
        ),
        # =====================================================================
        # PHÒNG NNMT — NÔNG NGHIỆP VÀ MÔI TRƯỜNG (10 văn bản: 8 chính thức + 2 kho_rieng)
        # =====================================================================
        (
            "31/2024/QH15",
            "Luật Đất đai",
            "Luật",
            "trung_uong",
            "NNMT",
            "Quốc hội",
            "2024-01-18",
            "con_hieu_luc",
            "Quy định tách bạch trách nhiệm UBND cấp xã hòa giải tranh chấp đất đai (Điều 235), xác nhận nguồn gốc & niêm yết 15 ngày (Điều 137, 138) và thẩm quyền cấp GCN (Điều 136).",
            (
                "1. Điều 235 (Hòa giải tranh chấp đất đai tại UBND cấp xã): Khi các bên không tự hòa giải được và gửi đơn đến UBND cấp xã nơi có đất tranh chấp, "
                "Chủ tịch UBND cấp xã thành lập Hội đồng hòa giải tranh chấp đất đai (Chủ tịch hoặc Phó Chủ tịch UBND xã làm Chủ tịch Hội đồng, đại diện Ủy ban MTTQ cấp xã, "
                "công chức làm công tác địa chính và người cư trú lâu năm biết rõ nguồn gốc, quá trình sử dụng đất). Thời hạn thực hiện thủ tục hòa giải tại UBND cấp xã "
                "không quá 30 ngày kể từ ngày nhận được đơn yêu cầu hòa giải; kết quả phải lập thành Biên bản hòa giải thành hoặc hòa giải không thành có chữ ký các bên và xác nhận của UBND cấp xã. "
                "2. Điều 137, Điều 138 (Xác nhận nguồn gốc sử dụng đất khi đăng ký, cấp GCN lần đầu): UBND cấp xã có trách nhiệm kiểm tra thực địa, xác nhận hiện trạng sử dụng đất, "
                "nguồn gốc và thời điểm bắt đầu sử dụng đất ổn định, tình trạng không có tranh chấp đất đai, sự phù hợp với quy hoạch và tổ chức niêm yết công khai kết quả kiểm tra "
                "trong thời hạn 15 ngày liên tục tại trụ sở UBND cấp xã và khu dân cư nơi có đất. "
                "3. Điều 136 (Thẩm quyền cấp Giấy chứng nhận quyền sử dụng đất, quyền sở hữu tài sản gắn liền với đất lần đầu): Thẩm quyền ký cấp Giấy chứng nhận lần đầu cho hộ gia đình, cá nhân "
                "thuộc cơ quan có thẩm quyền theo Luật Đất đai 2024 (cấp trên / cơ quan được phân quyền hợp pháp); UBND cấp xã KHÔNG tự ký cấp sổ đỏ lần đầu vượt thẩm quyền "
                "khi chưa có văn bản phân quyền đặc thù, mà thực hiện thẩm tra, xác nhận nguồn gốc, niêm yết 15 ngày và chuyển hồ sơ liên thông lên cơ quan có thẩm quyền."
            ),
            now,
        ),
        (
            "101/2024/NĐ-CP",
            "Nghị định quy định về điều tra cơ bản đất đai; đăng ký, cấp Giấy chứng nhận quyền sử dụng đất, quyền sở hữu tài sản gắn liền với đất và Hệ thống thông tin đất đai",
            "Nghị định",
            "trung_uong",
            "NNMT",
            "Chính phủ",
            "2024-07-29",
            "con_hieu_luc",
            "Quy định trình tự tiếp nhận hồ sơ đăng ký đất đai, lấy ý kiến khu dân cư và niêm yết công khai 15 ngày tại UBND cấp xã.",
            (
                "Nghị định 101/2024/NĐ-CP quy định chi tiết trình tự UBND cấp xã kiểm tra hồ sơ đăng ký đất đai, cấp Giấy chứng nhận lần đầu: "
                "đối chiếu bản đồ địa chính/mảnh trích đo bản đồ địa chính, lấy ý kiến những người từng cư trú cùng thời điểm bắt đầu sử dụng đất tại khu dân cư, "
                "lập danh sách công khai kết quả kiểm tra tại trụ sở UBND xã và thôn/tổ dân phố trong thời hạn 15 ngày, lập biên bản kết thúc công khai và xác nhận vào Đơn đăng ký đất đai."
            ),
            now,
        ),
        (
            "123/2024/NĐ-CP",
            "Nghị định quy định về xử phạt vi phạm hành chính trong lĩnh vực đất đai",
            "Nghị định",
            "trung_uong",
            "NNMT",
            "Chính phủ",
            "2024-10-04",
            "con_hieu_luc",
            "Quy định xử phạt hành vi lấn đất, chiếm đất, tự ý chuyển mục đích sử dụng đất và giới hạn thẩm quyền xử phạt đến 5.000.000 đồng của Chủ tịch UBND cấp xã.",
            (
                "Nghị định 123/2024/NĐ-CP quy định khung xử phạt đối với hành vi lấn đất, chiếm đất, hủy hoại đất, tự ý chuyển đất trồng lúa/đất nông nghiệp sang đất phi nông nghiệp hoặc đất ở. "
                "Tại cấp xã: công chức Địa chính - Nông nghiệp - Xây dựng và Môi trường đang thi hành công vụ có thẩm quyền lập biên bản vi phạm hành chính ngay khi phát hiện hành vi vi phạm; "
                "cá nhân Chủ tịch UBND cấp xã có thẩm quyền phạt cảnh cáo, phạt tiền tối đa đến 5.000.000 đồng đối với cá nhân (gấp 02 lần đối với tổ chức) "
                "và áp dụng biện pháp khắc phục hậu quả buộc khôi phục lại tình trạng ban đầu của đất trước khi vi phạm. Trường hợp khung phạt tiền hoặc biện pháp xử lý vượt thẩm quyền của Chủ tịch UBND cấp xã, "
                "UBND xã phải củng cố hồ sơ, giữ nguyên hiện trạng và chuyển ngay hồ sơ lên Chủ tịch UBND cấp có thẩm quyền xử phạt theo Luật Xử lý vi phạm hành chính."
            ),
            now,
        ),
        (
            "72/2020/QH14",
            "Luật Bảo vệ môi trường",
            "Luật",
            "trung_uong",
            "NNMT",
            "Quốc hội",
            "2020-11-17",
            "con_hieu_luc",
            "Điều 75, 76, 77 quy định phân loại chất thải rắn sinh hoạt tại nguồn thành 03 nhóm và trách nhiệm giám sát của UBND cấp xã.",
            (
                "Điều 75, Điều 76, Điều 77 Luật Bảo vệ môi trường số 72/2020/QH14 quy định chất thải rắn sinh hoạt phát sinh từ hộ gia đình, cá nhân được phân loại tại nguồn thành 03 nhóm: "
                "(1) Chất thải rắn có khả năng tái sử dụng, tái chế; (2) Chất thải thực phẩm; và (3) Chất thải rắn sinh hoạt khác. "
                "UBND cấp xã có trách nhiệm xây dựng kế hoạch và kiểm tra việc chấp hành pháp luật bảo vệ môi trường của hộ gia đình, cá nhân; "
                "giám sát chất lượng, tần suất thu gom của đơn vị dịch vụ thu gom chất thải rắn sinh hoạt (có quyền từ chối thu gom rác không phân loại theo lộ trình địa phương); "
                "phối hợp Ủy ban MTTQ Việt Nam và các tổ chức chính trị - xã hội cấp xã vận động cộng đồng dân cư phân loại rác tại nguồn."
            ),
            now,
        ),
        (
            "45/2022/NĐ-CP",
            "Nghị định quy định về xử phạt vi phạm hành chính trong lĩnh vực bảo vệ môi trường",
            "Nghị định",
            "trung_uong",
            "NNMT",
            "Chính phủ",
            "2022-07-07",
            "con_hieu_luc",
            "Quy định mức xử phạt đối với hộ gia đình, cá nhân không phân loại chất thải rắn sinh hoạt, vứt rác bừa bãi và thẩm quyền xử phạt của Chủ tịch UBND cấp xã.",
            (
                "Nghị định 45/2022/NĐ-CP (Điều 25, Điều 26) quy định phạt tiền từ 500.000 đồng đến 1.000.000 đồng đối với hành vi hộ gia đình, cá nhân không phân loại chất thải rắn sinh hoạt theo quy định; "
                "xử phạt hành vi vứt, thải, bỏ rác thải sinh hoạt trên vỉa hè, lòng đường, hệ thống thoát nước, ao hồ kênh rạch hoặc đốt chất thải rắn sinh hoạt trái quy định. "
                "Chủ tịch UBND cấp xã có thẩm quyền phạt tiền đến 5.000.000 đồng đối với cá nhân vi phạm và buộc khôi phục lại tình trạng vệ sinh môi trường ban đầu."
            ),
            now,
        ),
        (
            "16/2022/NĐ-CP",
            "Nghị định quy định xử phạt vi phạm hành chính về xây dựng (kèm quy định quản lý trật tự xây dựng tại cơ sở)",
            "Nghị định",
            "trung_uong",
            "NNMT",
            "Chính phủ",
            "2022-01-28",
            "con_hieu_luc",
            "Quy định trách nhiệm của UBND cấp xã kiểm tra trật tự xây dựng, lập biên bản yêu cầu ngừng thi công và chuyển hồ sơ trong 24 giờ nếu vượt thẩm quyền.",
            (
                "Theo Luật Xây dựng sửa đổi và Nghị định 16/2022/NĐ-CP, UBND cấp xã chịu trách nhiệm kiểm tra, phát hiện kịp thời hành vi xây dựng không phép, sai phép, "
                "xây dựng lấn chiếm hành lang bảo vệ công trình hoặc xây dựng trái phép trên đất nông nghiệp. Ngay khi phát hiện vi phạm, công chức chuyên trách phải lập biên bản vi phạm hành chính, "
                "yêu cầu tổ chức, cá nhân ngừng thi công xây dựng công trình ngay; Chủ tịch UBND cấp xã xử phạt trong phạm vi thẩm quyền (phạt tiền tối đa đến 5.000.000 đồng đối với cá nhân) "
                "hoặc lập hồ sơ báo cáo, chuyển người có thẩm quyền cấp trên xử lý trong thời hạn 24 giờ kể từ khi lập biên bản nếu vượt thẩm quyền."
            ),
            now,
        ),
        (
            "318/2022/QĐ-TTg",
            "Quyết định ban hành Bộ tiêu chí quốc gia về xã nông thôn mới và Bộ tiêu chí quốc gia về xã nông thôn mới nâng cao",
            "Quyết định",
            "trung_uong",
            "NNMT",
            "Thủ tướng Chính phủ",
            "2022-03-08",
            "con_hieu_luc",
            "Quy định 19 tiêu chí xã nông thôn mới, nông thôn mới nâng cao và định hướng nông thôn mới kiểu mẫu về hạ tầng, kinh tế nông thôn và môi trường sống.",
            (
                "Quyết định 318/2022/QĐ-TTg quy định 19 tiêu chí đánh giá xã đạt chuẩn nông thôn mới và nông thôn mới nâng cao, trọng tâm là tiêu chí Quy hoạch, Giao thông, Thủy lợi và phòng chống thiên tai, "
                "Tổ chức sản xuất và phát triển kinh tế nông thôn (sản phẩm OCOP, mã số vùng trồng), Môi trường và an toàn thực phẩm (tỷ lệ thu gom, xử lý chất thải rắn sinh hoạt, "
                "tỷ lệ hộ thực hiện phân loại chất thải rắn tại nguồn, cảnh quan môi trường sáng - xanh - sạch - đẹp) và Quốc phòng, an ninh, hành chính công."
            ),
            now,
        ),
        (
            "24/2026/QĐ-UBND",
            "Quyết định ban hành Quy chế phối hợp quản lý đất đai, trật tự xây dựng và bảo vệ môi trường cấp xã, phường",
            "Quyết định",
            "dia_phuong",
            "NNMT",
            "UBND Thành phố",
            "2026-08-15",
            "con_hieu_luc",
            "Quy định cơ chế phối hợp liên thông giữa bộ phận Nông nghiệp - Môi trường với Văn phòng Đăng ký đất đai và các bộ phận chuyên môn trong 02 ngày làm việc.",
            (
                "Các bộ phận chuyên môn trực thuộc UBND xã, phường có trách nhiệm cho ý kiến thẩm định phối hợp nội bộ đối với hồ sơ địa chính, xây dựng, môi trường "
                "trong tối đa 02 ngày làm việc kể từ khi nhận phiếu chuyển điện tử; phối hợp tuần tra định kỳ hằng tuần tại các khu vực đất công, hành lang thoát lũ và điểm giáp ranh."
            ),
            now,
        ),
        (
            "HD-03/2026/UBND-NNMT",
            f"Sổ tay nghiệp vụ hòa giải tranh chấp đất đai và đo đạc xác minh hiện trạng tại thực địa ({commune_name})",
            "Sổ tay nội bộ",
            "kho_rieng",
            "NNMT",
            commune_name,
            "2026-09-15",
            "con_hieu_luc",
            "Kho dữ liệu riêng Phòng Nông nghiệp và Môi trường hướng dẫn quy trình 04 bước xác minh thực địa trước phiên họp Hội đồng hòa giải.",
            (
                "Khi thụ lý đơn hòa giải tranh chấp đất đai hoặc xác nhận nguồn gốc đất, công chức địa chính bắt buộc: (1) Đối chiếu bản đồ địa chính qua các thời kỳ và sổ mục kê; "
                "(2) Kiểm tra thực địa, đo đạc kích thước tứ cận có sự chứng kiến của các hộ giáp ranh; (3) Lập phiếu lấy ý kiến khu dân cư; "
                "(4) Hoàn thành tổ chức họp Hội đồng hòa giải và lập biên bản trong đúng hạn 30 ngày theo Điều 235 Luật Đất đai 2024."
            ),
            now,
        ),
        (
            "QT-04/2026/UBND-NNMT",
            f"Quy trình kiểm tra tuần tra, lập biên bản vi phạm trật tự xây dựng và vệ sinh môi trường cấp xã ({commune_name})",
            "Quy trình nội bộ",
            "kho_rieng",
            "NNMT",
            commune_name,
            "2026-09-22",
            "con_hieu_luc",
            "Quy trình nội bộ Phòng Nông nghiệp và Môi trường xử lý tin báo xây dựng trái phép trên đất nông nghiệp và đổ trộm rác thải trong 04 giờ.",
            (
                "Ngay khi nhận phản ánh tự ý san lấp, xây dựng trên đất nông nghiệp hoặc đổ trộm chất thải rắn, Tổ kiểm tra do công chức NNMT chủ trì phối hợp Công an xã và Tổ trưởng dân phố "
                "có mặt tại hiện trường trong 04 giờ, chụp ảnh tọa độ, lập biên bản yêu cầu đình chỉ hành vi ngay và báo cáo Chủ tịch UBND xã xử lý hoặc chuyển cấp trên trong 24 giờ nếu vượt khung phạt 5.000.000 đồng."
            ),
            now,
        ),
    ]


def init_db(
    db_path: Path | str | None = None,
    commune_name: str = "UBND xã, phường trung tâm",
    owner_email: str = "tsh.co@tshorg.vn",
) -> None:
    now = utc_now_iso()
    with get_conn(db_path) as conn:
        conn.executescript(SCHEMA_SQL)
        existing_meta = conn.execute(
            "SELECT value FROM tenant_meta WHERE key = 'commune_name'"
        ).fetchone()
        if not existing_meta:
            conn.execute(
                "INSERT INTO tenant_meta(key, value) VALUES ('commune_name', ?)",
                (commune_name.strip(),),
            )

        dept_count = conn.execute("SELECT COUNT(*) AS c FROM departments").fetchone()["c"]
        if dept_count == 0:
            departments = [
                (
                    "VP",
                    "VP",
                    "Văn phòng HĐND & UBND",
                    "Tổng hợp, văn thư, tư pháp - hộ tịch, chứng thực, tiếp công dân, giải quyết khiếu nại - tố cáo và kiểm soát TTHC",
                    f"Tham mưu cho {commune_name} chuẩn thể thức Nghị định 30/2020/NĐ-CP, Luật Tổ chức chính quyền địa phương 65/2025/QH15, Luật Hộ tịch, Nghị định 23/2015/NĐ-CP và Luật Tiếp công dân, Khiếu nại, Tố cáo. Luôn phân định rạch ròi thẩm quyền tập thể UBND và thẩm quyền cá nhân Chủ tịch UBND cấp xã.",
                    now,
                ),
                (
                    "KT",
                    "KT",
                    "Kinh tế",
                    "Tài chính - ngân sách xã, kế hoạch đầu tư công, quản lý tài sản công, chợ dân sinh, hộ kinh doanh và Hội đồng tư vấn thuế",
                    f"Tham mưu cho bộ phận Kinh tế thuộc {commune_name} theo Luật Ngân sách nhà nước 83/2015/QH13, Thông tư 344/2016/TT-BTC, Luật Đầu tư công 58/2024/QH15 và Luật Quản lý, sử dụng tài sản công; kiểm soát chặt dự toán, chứng từ thanh quyết toán và giám sát đầu tư của cộng đồng.",
                    now,
                ),
                (
                    "VHXH",
                    "VHXH",
                    "Văn hóa - Xã hội",
                    "Bảo trợ xã hội, chính sách người có công, giảm nghèo đa chiều, bảo vệ trẻ em, xét tặng Gia đình văn hóa và quản lý lễ hội",
                    f"Tham mưu cho bộ phận Văn hóa - Xã hội thuộc {commune_name} theo Nghị định 20/2021/NĐ-CP, Nghị định 76/2024/NĐ-CP (mức chuẩn 500.000 đồng/tháng), Pháp lệnh Ưu đãi người có công, Nghị định 86/2023/NĐ-CP và Luật Trẻ em; bảo đảm đúng đối tượng, đúng định mức và công khai dân chủ tại khu dân cư.",
                    now,
                ),
                (
                    "NNMT",
                    "NNMT",
                    "Nông nghiệp và Môi trường",
                    "Địa chính - đất đai, hòa giải tranh chấp, trật tự xây dựng, phân loại chất thải rắn tại nguồn và xây dựng nông thôn mới",
                    f"Tham mưu cho bộ phận Nông nghiệp và Môi trường thuộc {commune_name} theo Luật Đất đai 31/2024/QH15 (Điều 235 hòa giải 30 ngày, Điều 137–138 niêm yết 15 ngày, Điều 136 không ký vượt thẩm quyền cấp sổ đỏ), Nghị định 123/2024/NĐ-CP, Luật Bảo vệ môi trường 72/2020/QH14 và Nghị định 16/2022/NĐ-CP.",
                    now,
                ),
            ]
            conn.executemany(
                "INSERT INTO departments(id, code, name, scope_summary, instruction, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                departments,
            )

        doc_count = conn.execute("SELECT COUNT(*) AS c FROM official_documents").fetchone()["c"]
        if doc_count == 0:
            docs = _build_seed_documents(commune_name, now)
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
                    "Tổng hợp báo cáo kết quả cải cách hành chính và số hóa Bộ phận Một cửa tháng 11/2026",
                    "Rà soát tỷ lệ số hóa hồ sơ theo Nghị định 107/2021/NĐ-CP và trình Lãnh đạo UBND ký ban hành.",
                    "VP",
                    "Nguyễn Minh Tuấn",
                    "2026-11-22",
                    "cao",
                    "dang_thuc_hien",
                    70,
                    "61/2018/NĐ-CP",
                    0,
                    now,
                    now,
                ),
                (
                    "Lập dự toán thu - chi ngân sách xã năm 2027 trình kỳ họp HĐND cuối năm",
                    "Tổng hợp đề xuất kinh phí từ các bộ phận chuyên môn theo Thông tư 344/2016/TT-BTC.",
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
                    "Rà soát danh sách chi trả trợ cấp bảo trợ xã hội đợt tháng 11/2026",
                    "Đối chiếu biến động nhân khẩu với dữ liệu hộ tịch theo mức chuẩn 500.000 đồng/tháng.",
                    "VHXH",
                    "Lê Hoàng Nam",
                    "2026-11-20",
                    "trung_binh",
                    "hoan_thanh",
                    100,
                    "20/2021/NĐ-CP",
                    0,
                    now,
                    now,
                ),
                (
                    "Xác minh thực địa và tổ chức hòa giải hồ sơ tranh chấp ranh giới thửa đất số 42",
                    "Lập biên bản xác minh hiện trạng và thông báo lịch họp Hội đồng hòa giải trong hạn 30 ngày.",
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
                ("canbo.nnmt@ubnd.vn", "Phạm Quốc Bảo", "Công chức Địa chính - Môi trường", "officer", "NNMT", 0, 1, now),
            ]
            users = [
                (owner_clean, f"Chủ sở hữu ({commune_name})", "Chủ sở hữu hệ thống", "owner", "VP", 1, 1, now),
            ]
            if owner_clean != "tsh.co@tshorg.vn":
                users.append(
                    ("tsh.co@tshorg.vn", "Quản trị viên Hệ thống (TSH)", "Chủ sở hữu nền tảng", "owner", "VP", 1, 1, now)
                )
            users.extend([u for u in default_officers if u[0].lower() not in {owner_clean, "tsh.co@tshorg.vn"}])
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


def get_commune_name(db_path: Path | str | None = None) -> str:
    with get_conn(db_path) as conn:
        try:
            row = conn.execute(
                "SELECT value FROM tenant_meta WHERE key = 'commune_name'"
            ).fetchone()
            if row and row["value"]:
                return str(row["value"])
        except sqlite3.OperationalError:
            pass
    return "UBND xã, phường trung tâm"


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
    """In-memory session store isolated by (tenant_slug, actor_email, department_id, session_id)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sessions: dict[str, dict[str, Any]] = {}

    @staticmethod
    def _compose_key(
        session_id: str,
        tenant_slug: str = "default",
        actor_email: str = "local",
        department_id: str = "VP",
    ) -> str:
        return (
            f"{(tenant_slug or 'default').strip().lower()}"
            f"::{(actor_email or 'local').strip().lower()}"
            f"::{(department_id or 'VP').strip().upper()}"
            f"::{session_id}"
        )

    def get_or_create(
        self,
        session_id: str,
        *,
        tenant_slug: str = "default",
        actor_email: str = "local",
        department_id: str = "VP",
    ) -> dict[str, Any]:
        key = self._compose_key(session_id, tenant_slug, actor_email, department_id)
        with self._lock:
            if key not in self._sessions:
                self._sessions[key] = {
                    "session_id": session_id,
                    "tenant_slug": tenant_slug,
                    "actor_email": actor_email.lower(),
                    "department_id": department_id.upper(),
                    "created_at": utc_now_iso(),
                    "files": [],
                    "messages": [],
                }
            state = self._sessions[key]
            return {
                "session_id": state["session_id"],
                "tenant_slug": state["tenant_slug"],
                "department_id": state["department_id"],
                "created_at": state["created_at"],
                "files": list(state["files"]),
                "messages": list(state["messages"]),
            }

    def add_file(
        self,
        session_id: str,
        record: dict[str, Any],
        *,
        tenant_slug: str = "default",
        actor_email: str = "local",
        department_id: str = "VP",
    ) -> dict[str, Any]:
        key = self._compose_key(session_id, tenant_slug, actor_email, department_id)
        with self._lock:
            if key not in self._sessions:
                self._sessions[key] = {
                    "session_id": session_id,
                    "tenant_slug": tenant_slug,
                    "actor_email": actor_email.lower(),
                    "department_id": department_id.upper(),
                    "created_at": utc_now_iso(),
                    "files": [],
                    "messages": [],
                }
            self._sessions[key]["files"].append(dict(record))
        return self.get_or_create(
            session_id,
            tenant_slug=tenant_slug,
            actor_email=actor_email,
            department_id=department_id,
        )

    def append_message(
        self,
        session_id: str,
        msg: dict[str, Any],
        *,
        tenant_slug: str = "default",
        actor_email: str = "local",
        department_id: str = "VP",
    ) -> dict[str, Any]:
        key = self._compose_key(session_id, tenant_slug, actor_email, department_id)
        with self._lock:
            if key not in self._sessions:
                self._sessions[key] = {
                    "session_id": session_id,
                    "tenant_slug": tenant_slug,
                    "actor_email": actor_email.lower(),
                    "department_id": department_id.upper(),
                    "created_at": utc_now_iso(),
                    "files": [],
                    "messages": [],
                }
            self._sessions[key]["messages"].append(dict(msg))
        return self.get_or_create(
            session_id,
            tenant_slug=tenant_slug,
            actor_email=actor_email,
            department_id=department_id,
        )

    def wipe(
        self,
        session_id: str,
        *,
        tenant_slug: str = "default",
        actor_email: str = "local",
        department_id: str = "VP",
    ) -> bool:
        key = self._compose_key(session_id, tenant_slug, actor_email, department_id)
        with self._lock:
            existed = key in self._sessions
            self._sessions.pop(key, None)
            return existed


SESSION_STORE = EphemeralSessionStore()
