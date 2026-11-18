import test from "node:test";
import assert from "node:assert/strict";
import {
  ADMIN_DOC_TYPES,
  SESSION_PROCESS_TABS,
  formatAuditStatusLabel,
  formatTierLabel,
} from "../app/lib/m03-m05-helpers.ts";

test("ADMIN_DOC_TYPES covers all 5 standard commune administrative document types", () => {
  assert.deepEqual(ADMIN_DOC_TYPES, [
    "Công văn",
    "Kế hoạch",
    "Báo cáo",
    "Quyết định",
    "Thông báo",
  ]);
});

test("formatTierLabel and formatAuditStatusLabel map backend codes to Vietnamese labels", () => {
  assert.equal(formatTierLabel("trung_uong"), "Văn bản Trung ương");
  assert.equal(formatTierLabel("dia_phuong"), "Văn bản Địa phương");
  assert.equal(formatTierLabel("kho_rieng"), "Kho dữ liệu riêng");
  assert.equal(formatAuditStatusLabel("dat"), "Đạt chuẩn");
  assert.equal(formatAuditStatusLabel("can_ra_soat"), "Cần rà soát");
  assert.equal(formatAuditStatusLabel("khong_dat"), "Không đạt");
  assert.equal(SESSION_PROCESS_TABS.length, 4);
});

