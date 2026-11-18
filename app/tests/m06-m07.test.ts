import test from "node:test";
import assert from "node:assert/strict";
import {
  ADMIN_TABS,
  formatPriorityLabel,
  formatTaskStatusLabel,
  normalizeAdminTab,
} from "../app/lib/m06-m07-helpers.ts";

test("normalizeAdminTab maps sidebar query params to the 5 Module 07 tabs", () => {
  assert.equal(ADMIN_TABS.length, 5);
  assert.equal(normalizeAdminTab(null), "phan-quyen");
  assert.equal(normalizeAdminTab("instruction"), "instruction");
  assert.equal(normalizeAdminTab("api"), "api");
  assert.equal(normalizeAdminTab("nhat-ky"), "nhat-ky");
  assert.equal(normalizeAdminTab("nhan-ban"), "nhan-ban");
  assert.equal(normalizeAdminTab("unknown"), "phan-quyen");
});

test("formatTaskStatusLabel and formatPriorityLabel render Vietnamese administrative labels", () => {
  assert.equal(formatTaskStatusLabel("dang_thuc_hien"), "Đang thực hiện");
  assert.equal(formatTaskStatusLabel("sap_den_han"), "Sắp đến hạn");
  assert.equal(formatTaskStatusLabel("hoan_thanh"), "Hoàn thành");
  assert.equal(formatPriorityLabel("khan"), "Khẩn");
});

