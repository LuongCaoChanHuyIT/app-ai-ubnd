import type { Route } from "./+types/workspace-layout";
import {
  apiRequest,
  normalizeDepartmentId,
  resolveServerApiBase,
  type Department,
  type RbacUser,
} from "~/lib/api";
import { WorkspaceShell } from "~/components/layout/workspace-shell";

const FALLBACK_DEPARTMENTS: Department[] = [
  {
    id: "VP",
    code: "VP",
    name: "Văn phòng HĐND & UBND",
    scope_summary: "Tổng hợp, văn thư, tư pháp - hộ tịch, tiếp công dân và kiểm soát TTHC",
    instruction: "",
    updated_at: "",
  },
  {
    id: "KT",
    code: "KT",
    name: "Kinh tế",
    scope_summary: "Tài chính - ngân sách xã, kế hoạch đầu tư công, thương mại - dịch vụ",
    instruction: "",
    updated_at: "",
  },
  {
    id: "VHXH",
    code: "VHXH",
    name: "Văn hóa - Xã hội",
    scope_summary: "Chính sách người có công, bảo trợ xã hội, giáo dục, y tế cơ sở",
    instruction: "",
    updated_at: "",
  },
  {
    id: "NNMT",
    code: "NNMT",
    name: "Nông nghiệp và Môi trường",
    scope_summary: "Địa chính - đất đai, trật tự xây dựng, tài nguyên môi trường",
    instruction: "",
    updated_at: "",
  },
];

export async function loader({ request }: Route.LoaderArgs) {
  const url = new URL(request.url);
  const currentDeptId = normalizeDepartmentId(url.searchParams.get("dept"));
  const baseUrl = resolveServerApiBase();

  try {
    const [deptRes, userRes] = await Promise.all([
      apiRequest<{ departments: Department[] }>("/api/departments", { baseUrl }),
      apiRequest<{ users: RbacUser[] }>("/api/m07/users", { baseUrl }),
    ]);
    return {
      departments: deptRes.departments.length ? deptRes.departments : FALLBACK_DEPARTMENTS,
      users: userRes.users,
      currentDeptId,
    };
  } catch {
    return {
      departments: FALLBACK_DEPARTMENTS,
      users: [] as RbacUser[],
      currentDeptId,
    };
  }
}

export default function WorkspaceLayoutRoute({ loaderData }: Route.ComponentProps) {
  return (
    <WorkspaceShell
      departments={loaderData.departments}
      users={loaderData.users}
      currentDeptId={loaderData.currentDeptId}
    />
  );
}

