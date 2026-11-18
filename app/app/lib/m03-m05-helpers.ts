import type { AuditCriterion, DocTier, SessionProcessAction } from "./api.ts";

export const ADMIN_DOC_TYPES = [
  "Công văn",
  "Kế hoạch",
  "Báo cáo",
  "Quyết định",
  "Thông báo",
] as const;

export const SESSION_PROCESS_TABS: readonly {
  id: SessionProcessAction;
  label: string;
  description: string;
}[] = [
  {
    id: "tom_tat",
    label: "Tóm tắt hồ sơ",
    description: "Tóm tắt nội dung cốt lõi của từng tài liệu trong phiên",
  },
  {
    id: "trich_xuat",
    label: "Trích xuất dữ liệu",
    description: "Trích xuất mốc ngày tháng, số liệu định lượng và thông tin chính",
  },
  {
    id: "doi_chieu",
    label: "Đối chiếu mâu thuẫn",
    description: "Phát hiện chênh lệch số liệu, diện tích, ngày tháng giữa các tệp",
  },
  {
    id: "tong_hop",
    label: "Tổng hợp phiếu trình",
    description: "Hình thành phiếu tổng hợp hồ sơ trình Lãnh đạo UBND",
  },
] as const;

export function formatTierLabel(tier: DocTier | string): string {
  if (tier === "trung_uong") return "Văn bản Trung ương";
  if (tier === "dia_phuong") return "Văn bản Địa phương";
  if (tier === "kho_rieng") return "Kho dữ liệu riêng";
  return tier;
}

export function formatAuditStatusLabel(
  status: AuditCriterion["status"],
): string {
  if (status === "dat") return "Đạt chuẩn";
  if (status === "can_ra_soat") return "Cần rà soát";
  return "Không đạt";
}

