import type { TaskItem, TaskStatus } from "./api.ts";

export type AdminTabId =
  | "phan-quyen"
  | "instruction"
  | "api"
  | "nhat-ky"
  | "nhan-ban";

export const ADMIN_TABS: readonly { id: AdminTabId; label: string }[] = [
  { id: "phan-quyen", label: "Phân quyền email" },
  { id: "instruction", label: "Instruction của phòng" },
  { id: "api", label: "Cổng API đấu nối" },
  { id: "nhat-ky", label: "Nhật ký hệ thống" },
  { id: "nhan-ban", label: "Nhân bản AI" },
] as const;

export function normalizeAdminTab(raw: string | null | undefined): AdminTabId {
  if (
    raw === "instruction" ||
    raw === "api" ||
    raw === "nhat-ky" ||
    raw === "nhan-ban"
  ) {
    return raw;
  }
  return "phan-quyen";
}

export function formatTaskStatusLabel(status: TaskStatus): string {
  switch (status) {
    case "cho_xu_ly":
      return "Chờ xử lý";
    case "dang_thuc_hien":
      return "Đang thực hiện";
    case "sap_den_han":
      return "Sắp đến hạn";
    case "hoan_thanh":
      return "Hoàn thành";
  }
}

export function formatPriorityLabel(priority: TaskItem["priority"]): string {
  switch (priority) {
    case "thap":
      return "Thấp";
    case "trung_binh":
      return "Trung bình";
    case "cao":
      return "Cao";
    case "khan":
      return "Khẩn";
  }
}

