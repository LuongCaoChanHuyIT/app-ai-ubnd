import os
import re
import tempfile
import unittest
from pathlib import Path
from fastapi.testclient import TestClient

from backend.db import get_conn, init_db
from backend.main import app


class CommuneDomainAndNd30Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.tmp.name)
        self.db_path = self.base_dir / "commune_phase2.db"
        os.environ["UBND_DB_PATH"] = str(self.db_path)
        init_db(self.db_path, commune_name="UBND xã, phường trung tâm")
        self.owner = {"X-Actor-Email": "tsh.co@tshorg.vn"}
        self.vp_officer = {"X-Actor-Email": "canbo.vp@ubnd.vn"}
        self.kt_officer = {"X-Actor-Email": "canbo.kt@ubnd.vn"}
        self.vhxh_officer = {"X-Actor-Email": "canbo.vhxh@ubnd.vn"}
        self.nnmt_officer = {"X-Actor-Email": "canbo.nnmt@ubnd.vn"}
        self.client = TestClient(app, headers=self.owner)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_01_seed_db_contains_34_to_36_substantive_docs_across_four_departments(self) -> None:
        with get_conn(self.db_path) as conn:
            total = conn.execute("SELECT COUNT(*) AS c FROM official_documents").fetchone()["c"]
            self.assertGreaterEqual(total, 34)
            self.assertLessEqual(total, 36)

            dept_counts = {
                row["department_id"]: row["c"]
                for row in conn.execute(
                    "SELECT department_id, COUNT(*) AS c FROM official_documents GROUP BY department_id"
                ).fetchall()
            }
            self.assertGreaterEqual(dept_counts.get("VP", 0), 9)
            self.assertGreaterEqual(dept_counts.get("KT", 0), 8)
            self.assertGreaterEqual(dept_counts.get("VHXH", 0), 8)
            self.assertGreaterEqual(dept_counts.get("NNMT", 0), 9)

            priv_counts = {
                row["department_id"]: row["c"]
                for row in conn.execute(
                    "SELECT department_id, COUNT(*) AS c FROM official_documents WHERE tier = 'kho_rieng' GROUP BY department_id"
                ).fetchall()
            }
            for dept_code in ("VP", "KT", "VHXH", "NNMT"):
                self.assertGreaterEqual(
                    priv_counts.get(dept_code, 0),
                    2,
                    f"Expected >= 2 kho_rieng docs for {dept_code}",
                )

    def test_02_seed_db_contains_core_legal_codes_and_land_law_articles(self) -> None:
        with get_conn(self.db_path) as conn:
            rows = conn.execute("SELECT doc_number, title, content FROM official_documents").fetchall()
        all_numbers_and_text = " ".join(f"{r['doc_number']} {r['title']} {r['content']}" for r in rows)
        expected_codes = [
            "65/2025/QH15",
            "30/2020/NĐ-CP",
            "60/2014/QH13",
            "42/2013/QH13",
            "02/2011/QH13",
            "25/2018/QH14",
            "61/2018/NĐ-CP",
            "107/2021/NĐ-CP",
            "23/2015/NĐ-CP",
            "83/2015/QH13",
            "344/2016/TT-BTC",
            "58/2024/QH15",
            "15/2017/QH14",
            "01/2021/NĐ-CP",
            "38/2019/QH14",
            "20/2021/NĐ-CP",
            "76/2024/NĐ-CP",
            "02/2020/UBTVQH14",
            "110/2018/NĐ-CP",
            "86/2023/NĐ-CP",
            "07/2021/NĐ-CP",
            "102/2016/QH13",
            "31/2024/QH15",
            "101/2024/NĐ-CP",
            "123/2024/NĐ-CP",
            "72/2020/QH14",
            "45/2022/NĐ-CP",
            "16/2022/NĐ-CP",
            "318/2022/QĐ-TTg",
        ]
        for code in expected_codes:
            self.assertIn(code, all_numbers_and_text, f"Missing legal code {code}")

        land_doc = next(r for r in rows if r["doc_number"] == "31/2024/QH15")
        self.assertIn("Điều 235", land_doc["content"])
        self.assertIn("30 ngày", land_doc["content"])
        self.assertIn("Điều 137", land_doc["content"])
        self.assertIn("Điều 138", land_doc["content"])
        self.assertIn("15 ngày", land_doc["content"])
        self.assertIn("Điều 136", land_doc["content"])

    def test_03_smart_search_waste_sorting_cites_env_laws_never_land_law(self) -> None:
        res = self.client.post(
            "/api/m01/chat",
            headers=self.nnmt_officer,
            json={
                "session_id": "s-waste-01",
                "department_id": "NNMT",
                "mode": "nghiep_vu",
                "message": "Hướng dẫn phân loại rác thải sinh hoạt tại nguồn và xử lý hộ dân vứt rác bừa bãi tại xã",
            },
        )
        self.assertEqual(res.status_code, 200)
        body = res.json()["reply"]
        cited_nums = [c["doc_number"] for c in body["citations"]]
        self.assertIn("72/2020/QH14", cited_nums)
        self.assertIn("45/2022/NĐ-CP", cited_nums)
        self.assertNotIn("31/2024/QH15", cited_nums)
        self.assertNotIn("Luật Đất đai", body["content"])

    def test_04_smart_search_threshold_rejects_nonsense_and_off_topic_queries(self) -> None:
        res = self.client.post(
            "/api/m01/chat",
            headers=self.vp_officer,
            json={
                "session_id": "s-nonsense-01",
                "department_id": "VP",
                "mode": "nghiep_vu",
                "message": "Thủ tục cấp phép phóng tàu vũ trụ du hành sao Hỏa zyx987654",
            },
        )
        self.assertEqual(res.status_code, 200)
        reply = res.json()["reply"]
        self.assertEqual(reply["citations"], [])
        self.assertIn("Mô-đun 04", reply["content"])

    def test_05_smart_search_strictly_isolates_kho_rieng_by_dept_and_rbac(self) -> None:
        vhxh_docs = self.client.get(
            "/api/m04/documents",
            params={"department_id": "VHXH", "tier": "kho_rieng"},
            headers=self.vhxh_officer,
        ).json()["documents"]
        self.assertGreaterEqual(len(vhxh_docs), 2)
        self.assertTrue(all(d["department_id"] == "VHXH" for d in vhxh_docs))

        # Revoke private_repo_access for a new VHXH officer and verify kho_rieng is hidden
        self.client.post(
            "/api/m07/users",
            headers=self.owner,
            json={
                "email": "thuviec.vhxh@ubnd.vn",
                "full_name": "Thực Tập VHXH",
                "position": "Công chức tập sự",
                "role": "officer",
                "department_id": "VHXH",
                "private_repo_access": False,
            },
        )
        restricted_docs = self.client.get(
            "/api/m04/documents",
            params={"department_id": "VHXH", "tier": "kho_rieng"},
            headers={"X-Actor-Email": "thuviec.vhxh@ubnd.vn"},
        ).json()["documents"]
        self.assertEqual(restricted_docs, [])

    def test_06_m01_nghiep_vu_multi_clause_land_dispute_encroachment_and_red_book(self) -> None:
        res = self.client.post(
            "/api/m01/chat",
            headers=self.nnmt_officer,
            json={
                "session_id": "s-land-multi",
                "department_id": "NNMT",
                "mode": "nghiep_vu",
                "message": (
                    "Hai hộ dân tranh chấp ranh giới đất nông nghiệp, đồng thời một bên tự ý lấn chiếm đất "
                    "và hỏi UBND xã có tự ký cấp sổ đỏ lần đầu luôn được không?"
                ),
            },
        )
        self.assertEqual(res.status_code, 200)
        reply = res.json()["reply"]
        cited_nums = [c["doc_number"] for c in reply["citations"]]
        self.assertIn("31/2024/QH15", cited_nums)
        self.assertIn("123/2024/NĐ-CP", cited_nums)
        content = reply["content"]
        self.assertIn("Phân định thẩm quyền", content)
        self.assertIn("30 ngày", content)
        self.assertIn("15 ngày", content)
        self.assertIn("5.000.000", content)
        self.assertTrue(
            "không tự" in content.lower() or "vượt thẩm quyền" in content.lower()
        )

    def test_07_m01_nghiep_vu_vhxh_social_protection_and_cultural_family_authority(self) -> None:
        res = self.client.post(
            "/api/m01/chat",
            headers=self.vhxh_officer,
            json={
                "session_id": "s-vhxh-01",
                "department_id": "VHXH",
                "mode": "nghiep_vu",
                "message": "Tư vấn mức chuẩn trợ giúp xã hội cho đối tượng bảo trợ xã hội và thẩm quyền xét tặng danh hiệu Gia đình văn hóa",
            },
        )
        self.assertEqual(res.status_code, 200)
        reply = res.json()["reply"]
        cited_nums = [c["doc_number"] for c in reply["citations"]]
        self.assertIn("20/2021/NĐ-CP", cited_nums)
        self.assertIn("86/2023/NĐ-CP", cited_nums)
        self.assertIn("500.000", reply["content"])
        self.assertIn("Chủ tịch UBND", reply["content"])

    def test_08_m01_tham_dinh_builds_deep_review_matrix_with_session_files(self) -> None:
        sid = "s-audit-kt"
        self.client.post(
            f"/api/m05/sessions/{sid}/upload",
            params={"department_id": "KT"},
            headers=self.kt_officer,
            files={
                "file": (
                    "du_toan_sua_chua.txt",
                    "Dự toán sửa chữa nhà văn hóa Thôn 2. Kinh phí: 85.000.000 đồng. Ngày lập: 05/11/2026.".encode(),
                    "text/plain",
                )
            },
        )
        res = self.client.post(
            "/api/m01/chat",
            headers=self.kt_officer,
            json={
                "session_id": sid,
                "department_id": "KT",
                "mode": "tham_dinh",
                "message": "Thẩm định hồ sơ thanh toán sửa chữa nhà văn hóa thôn từ nguồn ngân sách xã",
            },
        )
        self.assertEqual(res.status_code, 200)
        content = res.json()["reply"]["content"]
        self.assertIn("|", content)
        self.assertIn("30/2020/NĐ-CP", content)
        self.assertIn("85.000.000", content)

    def test_09_m01_soan_thao_uses_active_commune_name_and_nd30_symbol(self) -> None:
        clone = self.client.post(
            "/api/m07/clone-tenant",
            headers=self.owner,
            json={
                "commune_name": "Phường Bến Nghé",
                "admin_email": "admin@bennghe.gov.vn",
            },
        ).json()
        tenant_headers = {
            "X-Actor-Email": "tsh.co@tshorg.vn",
            "X-Tenant-Slug": clone["slug"],
        }
        res = self.client.post(
            "/api/m01/chat",
            headers=tenant_headers,
            json={
                "session_id": "s-draft-bn",
                "department_id": "VP",
                "mode": "soan_thao",
                "message": "Soạn Thông báo lịch tiếp công dân định kỳ của Chủ tịch UBND phường",
            },
        )
        self.assertEqual(res.status_code, 200)
        content = res.json()["reply"]["content"]
        self.assertIn("PHƯỜNG BẾN NGHÉ", content)
        self.assertIn("Bến Nghé, ngày", content)
        self.assertIn("TB-UBND", content)

    def test_10_m02_analyze_classifies_environment_vs_land_vs_budget_themes(self) -> None:
        env_res = self.client.post(
            "/api/m02/analyze",
            headers=self.nnmt_officer,
            json={
                "department_id": "NNMT",
                "topic": "Triển khai phân loại chất thải rắn sinh hoạt tại nguồn ở các tổ dân phố",
                "context": "Lượng rác thực phẩm chiếm 60%, thiếu điểm tập kết",
            },
        ).json()
        kt_res = self.client.post(
            "/api/m02/analyze",
            headers=self.kt_officer,
            json={
                "department_id": "KT",
                "topic": "Sắp xếp trật tự hộ kinh doanh tại chợ dân sinh và chống thất thu thuế",
                "context": "Chợ hạng 3 có 120 hộ tiểu thương",
            },
        ).json()
        self.assertEqual(len(env_res["options"]), 3)
        self.assertEqual(len(kt_res["options"]), 3)
        env_blob = str(env_res["options"])
        kt_blob = str(kt_res["options"])
        self.assertNotEqual(env_res["options"][0]["title"], kt_res["options"][0]["title"])
        self.assertTrue("Mặt trận" in env_blob or "MTTQ" in env_blob)
        self.assertIn("Bước 1", env_blob)
        self.assertIn("thẩm quyền", env_blob.lower())
        self.assertTrue("hộ kinh doanh" in kt_blob.lower() or "tiểu thương" in kt_blob.lower())

    def test_11_m03_draft_uses_dynamic_tenant_commune_name_and_clean_place_name(self) -> None:
        # Default tenant ("UBND xã, phường trung tâm")
        default_draft = self.client.post(
            "/api/m03/draft",
            headers=self.owner,
            json={
                "department_id": "VP",
                "doc_type": "Thông báo",
                "title": "Lịch tiếp công dân định kỳ tháng 12/2026",
                "key_points": "Niêm yết lịch tiếp công dân tại trụ sở UBND",
            },
        ).json()["draft_text"]
        self.assertIn("ỦY BAN NHÂN DÂN", default_draft)
        self.assertIn("XÃ, PHƯỜNG TRUNG TÂM", default_draft)

        # Cloned tenant ("Phường Bến Nghé")
        clone = self.client.post(
            "/api/m07/clone-tenant",
            headers=self.owner,
            json={
                "commune_name": "Phường Bến Nghé",
                "admin_email": "vp@bennghe.gov.vn",
            },
        ).json()
        bn_draft = self.client.post(
            "/api/m03/draft",
            headers={
                "X-Actor-Email": "tsh.co@tshorg.vn",
                "X-Tenant-Slug": clone["slug"],
            },
            json={
                "department_id": "VP",
                "doc_type": "Thông báo",
                "title": "Lịch tiếp công dân định kỳ tháng 12/2026",
                "key_points": "Chủ tịch UBND tiếp công dân vào thứ Năm hằng tuần",
            },
        ).json()["draft_text"]
        self.assertIn("ỦY BAN NHÂN DÂN", bn_draft)
        self.assertIn("PHƯỜNG BẾN NGHÉ", bn_draft)
        self.assertIn("Bến Nghé, ngày", bn_draft)

    def test_12_m03_draft_enforces_appendix_i_symbols_for_all_six_doc_types(self) -> None:
        expected_symbols = [
            ("VP", "Quyết định", "Số: .../QĐ-UBND"),
            ("VP", "Kế hoạch", "Số: .../KH-UBND"),
            ("KT", "Báo cáo", "Số: .../BC-UBND"),
            ("VHXH", "Thông báo", "Số: .../TB-UBND"),
            ("KT", "Tờ trình", "Số: .../TTr-UBND"),
            ("NNMT", "Công văn", "Số: .../UBND-NNMT"),
        ]
        for dept_id, doc_type, expected_sym in expected_symbols:
            draft_text = self.client.post(
                "/api/m03/draft",
                headers=self.owner,
                json={
                    "department_id": dept_id,
                    "doc_type": doc_type,
                    "title": "Triển khai nhiệm vụ trọng tâm cuối năm 2026",
                    "key_points": "Rà soát tiến độ; Báo cáo kết quả",
                },
            ).json()["draft_text"]
            self.assertIn(expected_sym, draft_text, f"Wrong symbol for {doc_type}")
            if doc_type == "Công văn":
                self.assertNotIn("\nCÔNG VĂN\n", draft_text)
                self.assertIn("Kính gửi:", draft_text)

    def test_13_m03_draft_strips_duplicate_ve_viec_and_omits_ve_viec_on_ke_hoach_bao_cao(self) -> None:
        messy_title = "Về việc V/v Về việc triển khai phân loại rác thải sinh hoạt năm 2026"

        qd_text = self.client.post(
            "/api/m03/draft",
            headers=self.owner,
            json={"department_id": "NNMT", "doc_type": "Quyết định", "title": messy_title, "key_points": "Điều khoản 1"},
        ).json()["draft_text"]
        self.assertIsNone(re.search(r"về việc\s+(về việc|v/v)", qd_text, re.IGNORECASE))
        self.assertIn("Về việc ", qd_text)

        cv_text = self.client.post(
            "/api/m03/draft",
            headers=self.owner,
            json={"department_id": "NNMT", "doc_type": "Công văn", "title": messy_title, "key_points": "Nội dung 1"},
        ).json()["draft_text"]
        self.assertIsNone(re.search(r"v/v\s+(về việc|v/v)", cv_text, re.IGNORECASE))
        self.assertIn("V/v ", cv_text)

        for no_prefix_type in ("Kế hoạch", "Báo cáo"):
            txt = self.client.post(
                "/api/m03/draft",
                headers=self.owner,
                json={"department_id": "NNMT", "doc_type": no_prefix_type, "title": messy_title, "key_points": "Mục 1"},
            ).json()["draft_text"]
            lines = [ln.strip() for ln in txt.splitlines() if ln.strip()]
            idx = lines.index(no_prefix_type.upper())
            subject_line = lines[idx + 1]
            self.assertFalse(subject_line.lower().startswith("về việc"))
            self.assertFalse(subject_line.lower().startswith("v/v"))

    def test_14_m03_draft_formats_legal_bases_with_authentic_vietnamese_grammar(self) -> None:
        qd_text = self.client.post(
            "/api/m03/draft",
            headers=self.owner,
            json={
                "department_id": "NNMT",
                "doc_type": "Quyết định",
                "title": "Thành lập Hội đồng hòa giải tranh chấp đất đai thửa số 42",
                "key_points": "Thành lập Hội đồng hòa giải; Tổ chức họp hòa giải trong 30 ngày",
            },
        ).json()["draft_text"]
        self.assertNotIn("về Luật", qd_text)
        self.assertNotIn("về Nghị định", qd_text)
        self.assertIn("Căn cứ Luật Tổ chức chính quyền địa phương", qd_text)
        self.assertIn("Căn cứ Luật Đất đai số 31/2024/QH15", qd_text)
        self.assertIn("Theo đề nghị của Công chức phụ trách", qd_text)

    def test_15_m03_draft_authority_mode_separates_ubnd_collective_vs_chu_tich_individual(self) -> None:
        # 1. Explicit ubnd collective mode
        ubnd_qd = self.client.post(
            "/api/m03/draft",
            headers=self.owner,
            json={
                "department_id": "VP",
                "doc_type": "Quyết định",
                "title": "Ban hành Quy chế làm việc của UBND năm 2026",
                "key_points": "Ban hành kèm theo Quyết định này Quy chế làm việc",
                "authority_mode": "ubnd",
            },
        ).json()["draft_text"]
        self.assertIn("TM. ỦY BAN NHÂN DÂN", ubnd_qd)
        self.assertNotIn("CHỦ TỊCH ỦY BAN NHÂN DÂN", ubnd_qd)

        # 2. Explicit chu_tich mode
        ct_qd = self.client.post(
            "/api/m03/draft",
            headers=self.owner,
            json={
                "department_id": "NNMT",
                "doc_type": "Quyết định",
                "title": "Xử phạt vi phạm hành chính trong lĩnh vực bảo vệ môi trường",
                "key_points": "Xử phạt vi phạm hành chính đối với cá nhân vứt rác thải sai quy định",
                "authority_mode": "chu_tich",
            },
        ).json()["draft_text"]
        self.assertIn("CHỦ TỊCH ỦY BAN NHÂN DÂN", ct_qd)
        self.assertNotIn("TM. ỦY BAN NHÂN DÂN", ct_qd)

        # 3. Auto mode recognizing Chairman personal authority (Gia đình văn hóa)
        auto_ct = self.client.post(
            "/api/m03/draft",
            headers=self.owner,
            json={
                "department_id": "VHXH",
                "doc_type": "Quyết định",
                "title": "Về việc tặng danh hiệu Gia đình văn hóa năm 2026",
                "key_points": "Công nhận và tặng danh hiệu Gia đình văn hóa cho 420 hộ gia đình",
                "authority_mode": "auto",
            },
        ).json()["draft_text"]
        self.assertIn("CHỦ TỊCH ỦY BAN NHÂN DÂN", auto_ct)
        self.assertNotIn("TM. ỦY BAN NHÂN DÂN", auto_ct)
        self.assertNotIn("- Chủ tịch, các PCT", auto_ct)
        self.assertIn("- Lưu: VT, VHXH.", auto_ct)

    def test_16_m03_audit_penalizes_duplicate_ve_viec_and_wrong_ke_hoach_prefix(self) -> None:
        bad_bc = (
            "ỦY BAN NHÂN DÂN PHƯỜNG X          CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM\n"
            "                                      Độc lập - Tự do - Hạnh phúc\n"
            "Số: 15/BC-UBND\n"
            "                                      Phường X, ngày 18 tháng 11 năm 2026\n\n"
            "BÁO CÁO\n"
            "Về việc Về việc kết quả cải cách hành chính quý IV năm 2026\n\n"
            "Căn cứ Nghị định số 30/2020/NĐ-CP ngày 05 tháng 3 năm 2020 của Chính phủ về công tác văn thư;\n"
            "1. Đã tiếp nhận 450 hồ sơ đúng hạn.\n\n"
            "Nơi nhận:                              TM. ỦY BAN NHÂN DÂN\n"
            "- UBND cấp trên (để b/c);               CHỦ TỊCH\n"
            "- Lưu: VT, VP."
        )
        audit = self.client.post(
            "/api/m03/audit",
            headers=self.owner,
            json={"department_id": "VP", "doc_type": "Báo cáo", "draft_text": bad_bc},
        ).json()
        self.assertLess(audit["score"], 88)
        self.assertIn("issues", audit)
        self.assertGreaterEqual(len(audit["issues"]), 1)
        bo_cuc = next(c for c in audit["criteria"] if c["id"] == "bo_cuc")
        self.assertIn(bo_cuc["status"], {"khong_dat", "can_ra_soat"})

    def test_17_m03_audit_penalizes_symbol_mismatch_and_missing_luu_vt(self) -> None:
        bad_symbol_qd = (
            "ỦY BAN NHÂN DÂN PHƯỜNG X          CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM\n"
            "                                      Độc lập - Tự do - Hạnh phúc\n"
            "Số: 09/BC-UBND\n"
            "                                      Phường X, ngày 18 tháng 11 năm 2026\n\n"
            "QUYẾT ĐỊNH\n"
            "Về việc ban hành nội quy tiếp công dân\n\n"
            "ỦY BAN NHÂN DÂN PHƯỜNG X\n"
            "Căn cứ Luật Tiếp công dân số 42/2013/QH13;\n"
            "QUYẾT ĐỊNH:\n"
            "Điều 1. Ban hành Nội quy tiếp công dân tại trụ sở UBND.\n"
            "Điều 2. Văn phòng HĐND & UBND chịu trách nhiệm thi hành Quyết định này.\n\n"
            "Nơi nhận:                              TM. ỦY BAN NHÂN DÂN\n"
            "- Như Điều 2;                           CHỦ TỊCH"
        )
        audit = self.client.post(
            "/api/m03/audit",
            headers=self.owner,
            json={"department_id": "VP", "doc_type": "Quyết định", "draft_text": bad_symbol_qd},
        ).json()
        issues_blob = str(audit.get("issues", []))
        self.assertIn("QĐ-UBND", issues_blob)
        self.assertIn("Lưu: VT", issues_blob)
        self.assertLess(audit["score"], 85)

    def test_18_m03_audit_flags_expired_land_law_2013_and_awkward_can_cu(self) -> None:
        expired_draft = (
            "ỦY BAN NHÂN DÂN XÃ A               CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM\n"
            "                                      Độc lập - Tự do - Hạnh phúc\n"
            "Số: 22/QĐ-UBND\n"
            "                                      Hòa Tiến, ngày 18 tháng 11 năm 2026\n\n"
            "QUYẾT ĐỊNH\n"
            "Về việc thành lập Hội đồng hòa giải tranh chấp đất đai\n\n"
            "CHỦ TỊCH ỦY BAN NHÂN DÂN XÃ A\n"
            "Căn cứ Luật Đất đai số 45/2013/QH13;\n"
            "Căn cứ Luật số 31/2024/QH15 về Luật Đất đai 2024;\n"
            "QUYẾT ĐỊNH:\n"
            "Điều 1. Thành lập Hội đồng hòa giải tranh chấp đất đai.\n"
            "Điều 2. Quyết định có hiệu lực kể từ ngày ký; các ông bà có tên chịu trách nhiệm thi hành.\n\n"
            "Nơi nhận:                              CHỦ TỊCH\n"
            "- Như Điều 2;\n"
            "- Lưu: VT, NNMT."
        )
        audit = self.client.post(
            "/api/m03/audit",
            headers=self.owner,
            json={"department_id": "NNMT", "doc_type": "Quyết định", "draft_text": expired_draft},
        ).json()
        can_cu = next(c for c in audit["criteria"] if c["id"] == "can_cu")
        self.assertEqual(can_cu["status"], "khong_dat")
        issues_blob = str(audit["issues"])
        self.assertIn("45/2013/QH13", issues_blob)
        self.assertIn("31/2024/QH15", issues_blob)

    def test_19_m03_audit_catches_authority_signature_contradiction(self) -> None:
        contradict_qd = (
            "ỦY BAN NHÂN DÂN PHƯỜNG Y          CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM\n"
            "                                      Độc lập - Tự do - Hạnh phúc\n"
            "Số: 30/QĐ-UBND\n"
            "                                      Phường Y, ngày 18 tháng 11 năm 2026\n\n"
            "QUYẾT ĐỊNH\n"
            "Về việc xử phạt vi phạm hành chính về bảo vệ môi trường\n\n"
            "CHỦ TỊCH ỦY BAN NHÂN DÂN PHƯỜNG Y\n"
            "Căn cứ Nghị định số 45/2022/NĐ-CP ngày 07 tháng 7 năm 2022 của Chính phủ;\n"
            "QUYẾT ĐỊNH:\n"
            "Điều 1. Xử phạt hành chính ông Trần Văn B số tiền 1.500.000 đồng.\n"
            "Điều 2. Ông Trần Văn B chịu trách nhiệm thi hành Quyết định này.\n\n"
            "Nơi nhận:                              TM. ỦY BAN NHÂN DÂN\n"
            "- Như Điều 2;                           CHỦ TỊCH\n"
            "- Lưu: VT, NNMT."
        )
        audit = self.client.post(
            "/api/m03/audit",
            headers=self.owner,
            json={"department_id": "NNMT", "doc_type": "Quyết định", "draft_text": contradict_qd},
        ).json()
        tham_quyen = next(c for c in audit["criteria"] if c["id"] == "tham_quyen")
        self.assertEqual(tham_quyen["status"], "khong_dat")
        self.assertLess(audit["score"], 85)

    def test_20_m03_audit_flags_unfilled_placeholders_and_colloquial_slang(self) -> None:
        sloppy_cv = (
            "ỦY BAN NHÂN DÂN PHƯỜNG Z          CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM\n"
            "                                      Độc lập - Tự do - Hạnh phúc\n"
            "Số: .../UBND-KT\n"
            "V/v đôn đốc nộp báo cáo tài chính\n"
            "                                      Phường Z, ngày 18 tháng 11 năm 2026\n\n"
            "Kính gửi: Các đơn vị trực thuộc,\n\n"
            "Hiện nay tiến độ báo cáo [điền tên đơn vị] ko đạt yêu cầu, vì vậy nên là đề nghị anh em "
            "làm gấp cho dc ok thanks.\n\n"
            "Nơi nhận:                              TM. ỦY BAN NHÂN DÂN\n"
            "- Như trên;                             CHỦ TỊCH\n"
            "- Lưu: VT, KT."
        )
        audit = self.client.post(
            "/api/m03/audit",
            headers=self.owner,
            json={"department_id": "KT", "doc_type": "Công văn", "draft_text": sloppy_cv},
        ).json()
        logic = next(c for c in audit["criteria"] if c["id"] == "logic")
        van_phong = next(c for c in audit["criteria"] if c["id"] == "van_phong")
        self.assertIn(logic["status"], {"can_ra_soat", "khong_dat"})
        self.assertEqual(van_phong["status"], "khong_dat")
        self.assertIn("ko", van_phong["detail"])
        self.assertIn("thanks", van_phong["detail"])

    def test_21_m05_doi_chieu_extracts_structured_entities_and_flags_mismatches_vs_matches(self) -> None:
        sid = "s-diff-structured-01"
        doc1 = (
            "ĐƠN ĐỀ NGHỊ XÁC NHẬN NGUỒN GỐC ĐẤT\n"
            "Chủ hộ: Nguyễn Văn Minh\n"
            "Số CCCD: 048085001234\n"
            "Thửa đất số: 42, Tờ bản đồ số: 08\n"
            "Diện tích: 120 m2\n"
            "Kinh phí trích đo: 3.500.000 đồng\n"
            "Ngày lập: 10/10/2026\n"
            "Địa chỉ: Tổ dân phố 3"
        )
        doc2 = (
            "BIÊN BẢN KIỂM TRA THỰC ĐỊA\n"
            "Chủ hộ: Nguyễn Văn Minh\n"
            "Số CCCD: 048085001299\n"
            "Thửa đất số: 42, Tờ bản đồ số: 08\n"
            "Diện tích: 145 m2\n"
            "Kinh phí trích đo: 4.200.000 đồng\n"
            "Ngày lập: 15/10/2026\n"
            "Địa chỉ: Tổ dân phố 3"
        )
        self.client.post(
            f"/api/m05/sessions/{sid}/upload",
            params={"department_id": "NNMT"},
            headers=self.nnmt_officer,
            files={"file": ("don_de_nghi.txt", doc1.encode(), "text/plain")},
        )
        self.client.post(
            f"/api/m05/sessions/{sid}/upload",
            params={"department_id": "NNMT"},
            headers=self.nnmt_officer,
            files={"file": ("bien_ban_thuc_dia.txt", doc2.encode(), "text/plain")},
        )
        proc = self.client.post(
            f"/api/m05/sessions/{sid}/process",
            headers=self.nnmt_officer,
            json={"action": "doi_chieu", "department_id": "NNMT"},
        ).json()
        md = proc["result_markdown"]
        self.assertIn("|", md)
        self.assertIn("[KHỚP]", md)
        self.assertIn("[SAI LỆCH - CẦN XÁC MINH]", md)
        self.assertIn("Nguyễn Văn Minh", md)
        self.assertIn("048085001234", md)
        self.assertIn("048085001299", md)
        self.assertIn("120", md)
        self.assertIn("145", md)

    def test_22_m05_warns_on_non_ocr_scanned_pdf_across_session_actions(self) -> None:
        sid = "s-scan-warn-01"
        self.client.post(
            f"/api/m05/sessions/{sid}/upload",
            params={"department_id": "VP"},
            headers=self.vp_officer,
            files={"file": ("so_ho_tich_scan.pdf", b"%PDF-1.4 binary image scan", "application/pdf")},
        )
        for act in ("tom_tat", "trich_xuat", "doi_chieu", "tong_hop"):
            res = self.client.post(
                f"/api/m05/sessions/{sid}/process",
                headers=self.vp_officer,
                json={"action": act, "department_id": "VP"},
            ).json()
            self.assertIn("OCR", res["result_markdown"], f"Missing OCR warning in {act}")
            self.assertIn("Cảnh báo", res["result_markdown"], f"Missing explicit warning banner in {act}")

    def test_23_anti_hallucination_rejects_pho_bo_truyen_thong_false_positive(self) -> None:
        res = self.client.post(
            "/api/m01/chat",
            headers=self.vp_officer,
            json={
                "session_id": "s-pho-bo-trap",
                "department_id": "VP",
                "mode": "nghiep_vu",
                "message": "Cách nấu phở bò truyền thống",
            },
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["reply"]["citations"], [])

    def test_24_cong_van_auto_authority_uses_tm_ubnd_and_audit_catches_missing_tm_on_collective_docs(self) -> None:
        cv = self.client.post(
            "/api/m03/draft",
            headers=self.vhxh_officer,
            json={
                "department_id": "VHXH",
                "doc_type": "Công văn",
                "title": "Rà soát hộ nghèo cuối năm 2026",
                "key_points": "Rà soát hộ nghèo và hộ cận nghèo tại các thôn",
                "authority_mode": "auto",
            },
        ).json()
        self.assertIn("TM. ỦY BAN NHÂN DÂN", cv["draft_text"])
        self.assertIn("Kính gửi: Các bộ phận chuyên môn trực thuộc UBND\n", cv["draft_text"])

        # Tamper collective Công văn to remove TM. ỦY BAN NHÂN DÂN -> audit MUST flag error
        tampered_cv = cv["draft_text"].replace("TM. ỦY BAN NHÂN DÂN\n                                 CHỦ TỊCH", "CHỦ TỊCH")
        audit_cv = self.client.post(
            "/api/m03/audit",
            headers=self.vhxh_officer,
            json={
                "department_id": "VHXH",
                "doc_type": "Công văn",
                "draft_text": tampered_cv,
            },
        ).json()
        codes = [i["code"] for i in audit_cv["issues"]]
        self.assertIn("MISSING_TM_ON_COLLECTIVE_DOC", codes)

    def test_25_nd30_appendix_i_final_legal_basis_ends_with_period_and_tenant_label_hides_db_ext(self) -> None:
        qd = self.client.post(
            "/api/m03/draft",
            headers=self.owner,
            json={
                "department_id": "VP",
                "doc_type": "Quyết định",
                "title": "Ban hành quy chế phối hợp",
                "key_points": "Phân công đầu mối",
            },
        ).json()["draft_text"]
        self.assertIn("Theo đề nghị của Công chức phụ trách bộ phận Văn phòng HĐND & UBND.\n", qd)

        kh = self.client.post(
            "/api/m03/draft",
            headers=self.owner,
            json={
                "department_id": "VP",
                "doc_type": "Kế hoạch",
                "title": "Cải cách hành chính năm 2026",
                "key_points": "Số hóa hồ sơ",
            },
        ).json()["draft_text"]
        basis_lines = [ln.strip() for ln in kh.splitlines() if ln.strip().startswith("Căn cứ ")]
        self.assertGreaterEqual(len(basis_lines), 1)
        self.assertTrue(basis_lines[-1].endswith("."), f"Last basis line must end with '.': {basis_lines[-1]}")

        cloned = self.client.post(
            "/api/m07/clone-tenant",
            headers=self.owner,
            json={"commune_name": "Phường Kiểm Định 25", "admin_email": "ad@kd25.gov.vn"},
        ).json()
        self.assertNotIn(".db", cloned["storage_label"])
        self.assertTrue(cloned["storage_label"].startswith("isolated-tenant://"))

    def test_26_m05_eight_field_custom_diff_and_malicious_edge_files_matrix(self) -> None:
        sid = "s-campaign4-matrix"
        # 1. Forbidden executable extensions (.exe, .sh, .bat) -> HTTP 400 with Vietnamese detail
        for bad_name in ("virus.exe", "attack.sh", "script.bat"):
            r_bad = self.client.post(
                f"/api/m05/sessions/{sid}/upload",
                params={"department_id": "NNMT"},
                headers=self.owner,
                files={"file": (bad_name, b"#!/bin/sh\necho bad", "application/octet-stream")},
            )
            self.assertEqual(r_bad.status_code, 400, f"Expected 400 for {bad_name}")
            self.assertIn("không được hỗ trợ", r_bad.json()["detail"])

        # 2. Oversized >10MB file -> HTTP 413
        r_big = self.client.post(
            f"/api/m05/sessions/{sid}/upload",
            params={"department_id": "NNMT"},
            headers=self.owner,
            files={"file": ("oversized.txt", b"A" * (10 * 1024 * 1024 + 2048), "text/plain")},
        )
        self.assertEqual(r_big.status_code, 413)

        # 3. 0-byte empty PDF and scanned image PDF without OCR layer -> HTTP 200, graceful warning, 0 HTTP 500
        r_empty_pdf = self.client.post(
            f"/api/m05/sessions/{sid}-pdf/upload",
            params={"department_id": "NNMT"},
            headers=self.owner,
            files={"file": ("empty_0byte.pdf", b"", "application/pdf")},
        )
        self.assertEqual(r_empty_pdf.status_code, 200)
        r_scan_pdf = self.client.post(
            f"/api/m05/sessions/{sid}-pdf/upload",
            params={"department_id": "NNMT"},
            headers=self.owner,
            files={"file": ("scan_no_ocr.pdf", b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF", "application/pdf")},
        )
        self.assertEqual(r_scan_pdf.status_code, 200)
        proc_pdf = self.client.post(
            f"/api/m05/sessions/{sid}-pdf/process",
            headers=self.owner,
            json={"action": "tom_tat", "department_id": "NNMT"},
        )
        self.assertEqual(proc_pdf.status_code, 200)
        self.assertIn("OCR", proc_pdf.json()["result_markdown"])

        # 4. Custom 2 .txt files conflicting across ALL 8 structured administrative fields
        file_a = (
            "Chủ hộ: Phạm Văn Hùng. Số CCCD: 036088001122. Địa chỉ: Thôn Đông Lạc. "
            "Tờ bản đồ số: 12 — Thửa đất số: 108. Diện tích: 215 m2. "
            "Số tiền: 45.000.000 đồng. Ngày lập: 02/11/2026."
        )
        file_b = (
            "Chủ hộ: Phạm Văn Hưng. Số CCCD: 036088001199. Địa chỉ: Thôn Tây Lạc. "
            "Tờ bản đồ số: 14 — Thửa đất số: 109. Diện tích: 240 m2. "
            "Số tiền: 52.000.000 đồng. Ngày lập: 09/11/2026."
        )
        self.client.post(
            f"/api/m05/sessions/{sid}/upload",
            params={"department_id": "NNMT"},
            headers=self.owner,
            files={"file": ("qa_8fields_a.txt", file_a.encode(), "text/plain")},
        )
        self.client.post(
            f"/api/m05/sessions/{sid}/upload",
            params={"department_id": "NNMT"},
            headers=self.owner,
            files={"file": ("qa_8fields_b.txt", file_b.encode(), "text/plain")},
        )
        diff_8 = self.client.post(
            f"/api/m05/sessions/{sid}/process",
            headers=self.owner,
            json={"action": "doi_chieu", "department_id": "NNMT"},
        ).json()
        self.assertEqual(len(diff_8["highlights"]), 8)
        self.assertIn("8 trường thông tin `[SAI LỆCH - CẦN XÁC MINH]`", diff_8["result_markdown"])


if __name__ == "__main__":
    unittest.main()
