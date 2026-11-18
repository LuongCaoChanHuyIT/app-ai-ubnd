import { useEffect, useState } from "react";
import { Link, Outlet, useLocation, useNavigate, useSearchParams } from "react-router";
import {
  BookOpen,
  CheckSquare,
  Copy,
  FileCheck2,
  FileUp,
  History,
  Link2,
  Menu,
  Plus,
  RefreshCw,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  Upload,
} from "lucide-react";
import {
  LEGAL_DISCLAIMER_TEXT,
  type Department,
  type DepartmentId,
  type RbacUser,
} from "~/lib/api";
import { getActiveActorEmail, setActiveActorEmail } from "~/lib/session";
import { Button } from "~/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "~/components/ui/select";
import { Sheet, SheetContent, SheetTrigger } from "~/components/ui/sheet";
import { cn } from "~/lib/utils";

interface NavItemConfig {
  id: string;
  label: string;
  pathname: string;
  tab?: string;
  icon: React.ComponentType<{ className?: string }>;
  group: "core" | "admin";
}

const NAV_ITEMS: NavItemConfig[] = [
  { id: "m01", label: "+ Tư vấn công việc", pathname: "/", icon: Plus, group: "core" },
  {
    id: "m02",
    label: "AI hỗ trợ kiến thức mở rộng",
    pathname: "/kien-thuc-mo-rong",
    icon: Sparkles,
    group: "core",
  },
  {
    id: "m03",
    label: "Soạn thảo & kiểm tra",
    pathname: "/soan-thao-kiem-tra",
    icon: FileCheck2,
    group: "core",
  },
  {
    id: "m04",
    label: "Nguồn văn bản chính thức",
    pathname: "/nguon-van-ban",
    icon: BookOpen,
    group: "core",
  },
  {
    id: "m05",
    label: "Tải & xử lý tài liệu",
    pathname: "/xu-ly-tai-lieu",
    icon: FileUp,
    group: "core",
  },
  {
    id: "m06",
    label: "Điều hành công việc",
    pathname: "/dieu-hanh-cong-viec",
    icon: CheckSquare,
    group: "core",
  },
  {
    id: "m04-req",
    label: "Đề nghị cập nhật văn bản",
    pathname: "/nguon-van-ban",
    tab: "de-nghi",
    icon: RefreshCw,
    group: "admin",
  },
  {
    id: "m07-inst",
    label: "Instruction của phòng",
    pathname: "/quan-tri-he-thong",
    tab: "instruction",
    icon: SlidersHorizontal,
    group: "admin",
  },
  {
    id: "m07-api",
    label: "Cổng API đấu nối",
    pathname: "/quan-tri-he-thong",
    tab: "api",
    icon: Link2,
    group: "admin",
  },
  {
    id: "m07-rbac",
    label: "Phân quyền email",
    pathname: "/quan-tri-he-thong",
    tab: "phan-quyen",
    icon: ShieldCheck,
    group: "admin",
  },
  {
    id: "m07-logs",
    label: "Nhật ký hệ thống",
    pathname: "/quan-tri-he-thong",
    tab: "nhat-ky",
    icon: History,
    group: "admin",
  },
  {
    id: "m07-clone",
    label: "Nhân bản AI",
    pathname: "/quan-tri-he-thong",
    tab: "nhan-ban",
    icon: Copy,
    group: "admin",
  },
];

export interface WorkspaceShellProps {
  departments: Department[];
  users: RbacUser[];
  currentDeptId: DepartmentId;
}

export function WorkspaceShell({
  departments,
  users,
  currentDeptId,
}: WorkspaceShellProps) {
  const location = useLocation();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [actorEmail, setActorEmailState] = useState("tsh.co@tshorg.vn");
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    setActorEmailState(getActiveActorEmail());
    const handler = (ev: Event) => {
      const custom = ev as CustomEvent<string>;
      if (custom.detail) {
        setActorEmailState(custom.detail);
      }
    };
    window.addEventListener("ubnd-actor-changed", handler);
    return () => window.removeEventListener("ubnd-actor-changed", handler);
  }, []);

  const currentDept =
    departments.find((d) => d.id === currentDeptId) ??
    departments[0] ?? {
      id: "VP" as DepartmentId,
      code: "VP",
      name: "Văn phòng HĐND & UBND",
      scope_summary: "Tổng hợp, văn thư, tư pháp - hộ tịch, tiếp công dân và kiểm soát TTHC",
      instruction: "",
      updated_at: "",
    };

  const currentUser =
    users.find((u) => u.email.toLowerCase() === actorEmail.toLowerCase()) ?? {
      id: 0,
      email: actorEmail,
      full_name: "Chủ sở hữu hệ thống",
      position: "Quản trị viên",
      role: "owner" as const,
      department_id: currentDeptId,
      private_repo_access: true,
      active: true,
      created_at: "",
    };

  const activeTabParam = searchParams.get("tab") ?? "";

  function buildHref(pathname: string, tab?: string, deptOverride?: DepartmentId) {
    const params = new URLSearchParams();
    params.set("dept", deptOverride ?? currentDeptId);
    if (tab) {
      params.set("tab", tab);
    }
    return `${pathname}?${params.toString()}`;
  }

  function isItemActive(item: NavItemConfig): boolean {
    if (location.pathname !== item.pathname) {
      return false;
    }
    if (item.pathname === "/nguon-van-ban") {
      if (item.tab === "de-nghi") return activeTabParam === "de-nghi";
      return activeTabParam !== "de-nghi";
    }
    if (item.pathname === "/quan-tri-he-thong") {
      const effectiveTab = activeTabParam || "phan-quyen";
      return item.tab === effectiveTab;
    }
    return true;
  }

  function handleDepartmentChange(nextDept: string) {
    const dept = nextDept as DepartmentId;
    const nextParams = new URLSearchParams(searchParams);
    nextParams.set("dept", dept);
    navigate(`${location.pathname}?${nextParams.toString()}`);
  }

  function handleActorSwitch(nextEmail: string) {
    setActiveActorEmail(nextEmail);
    setActorEmailState(nextEmail);
    const matched = users.find((u) => u.email === nextEmail);
    if (matched && matched.role === "officer") {
      handleDepartmentChange(matched.department_id);
    }
  }

  const sidebarContent = (
    <div className="flex h-full w-[268px] flex-col bg-[#0F172A] text-slate-100 select-none">
      {/* Brand Header */}
      <div className="flex items-center gap-3 px-4 pt-4 pb-3 border-b border-slate-800/80">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-blue-600 font-bold text-xs tracking-wide text-white shadow-sm">
          AI
        </div>
        <div className="min-w-0">
          <p className="text-[13px] font-bold tracking-wide text-white truncate">
            TRỢ LÝ CÁN BỘ
          </p>
          <p className="text-[11px] text-slate-400 truncate">
            Tư vấn công việc xã/phường
          </p>
        </div>
      </div>

      {/* Workspace Selector */}
      <div className="px-3.5 pt-3.5 pb-2">
        <p className="px-1 pb-1.5 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
          KHÔNG GIAN LÀM VIỆC
        </p>
        <div className="rounded-lg border border-slate-700/80 bg-[#1E293B] p-2.5 space-y-2">
          <Select value={currentDept.id} onValueChange={handleDepartmentChange}>
            <SelectTrigger
              aria-label="Chọn không gian phòng chuyên môn"
              className="h-8 w-full border-slate-600 bg-[#0F172A] text-xs font-medium text-slate-100 focus:ring-blue-500"
            >
              <SelectValue placeholder="Chọn phòng ban" />
            </SelectTrigger>
            <SelectContent>
              {departments.map((d) => (
                <SelectItem key={d.id} value={d.id} className="text-xs">
                  {d.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <div className="flex items-start gap-2">
            <span className="mt-0.5 inline-flex h-5 shrink-0 items-center rounded bg-blue-600/25 px-1.5 text-[10px] font-bold text-blue-300">
              {currentDept.code}
            </span>
            <p className="text-[11px] leading-snug text-slate-300 line-clamp-2">
              {currentDept.scope_summary}
            </p>
          </div>
        </div>
      </div>

      {/* Navigation Links */}
      <nav className="flex-1 overflow-y-auto px-3 py-2 space-y-1">
        {NAV_ITEMS.filter((i) => i.group === "core").map((item) => {
          const Icon = item.icon;
          const active = isItemActive(item);
          return (
            <Link
              key={item.id}
              to={buildHref(item.pathname, item.tab)}
              onClick={() => setMobileOpen(false)}
              className={cn(
                "flex items-center gap-2.5 rounded-lg px-3 py-2 text-[12.5px] font-medium transition-colors",
                active
                  ? "bg-blue-600 text-white shadow-xs"
                  : "text-slate-300 hover:bg-slate-800/80 hover:text-white",
              )}
            >
              <Icon className="h-4 w-4 shrink-0" />
              <span className="truncate">{item.label}</span>
            </Link>
          );
        })}

        <div className="pt-2.5 pb-1 px-2">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
            Cấu hình & Quản trị
          </p>
        </div>

        {NAV_ITEMS.filter((i) => i.group === "admin").map((item) => {
          const Icon = item.icon;
          const active = isItemActive(item);
          return (
            <Link
              key={item.id}
              to={buildHref(item.pathname, item.tab)}
              onClick={() => setMobileOpen(false)}
              className={cn(
                "flex items-center gap-2.5 rounded-lg px-3 py-1.5 text-[12px] font-medium transition-colors",
                active
                  ? "bg-blue-600/90 text-white"
                  : "text-slate-300 hover:bg-slate-800/70 hover:text-white",
              )}
            >
              <Icon className="h-3.5 w-3.5 shrink-0 opacity-85" />
              <span className="truncate">{item.label}</span>
            </Link>
          );
        })}
      </nav>

      {/* Active Account / Role Switcher Footer */}
      <div className="border-t border-slate-800 p-3 space-y-2 bg-[#0B1220]">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-blue-600 text-xs font-bold text-white">
            {currentUser.email.slice(0, 2).toUpperCase()}
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-xs font-semibold text-slate-100 truncate">
              {currentUser.email}
            </p>
            <p className="text-[11px] text-slate-400 truncate">
              {currentUser.role === "owner"
                ? "Chủ sở hữu · Toàn quyền"
                : `Cán bộ ${currentUser.department_id}`}
            </p>
          </div>
        </div>
        {users.length > 0 && (
          <Select value={currentUser.email} onValueChange={handleActorSwitch}>
            <SelectTrigger
              aria-label="Chuyển tài khoản kiểm thử phân quyền"
              className="h-7 w-full border-slate-700 bg-slate-900 text-[11px] text-slate-300"
            >
              <SelectValue placeholder="Đổi vai trò" />
            </SelectTrigger>
            <SelectContent>
              {users.map((u) => (
                <SelectItem key={u.email} value={u.email} className="text-xs">
                  {u.email} ({u.role === "owner" ? "Chủ sở hữu" : u.department_id})
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}
      </div>
    </div>
  );

  return (
    <div className="flex min-h-screen w-full bg-[#F1F5F9] text-slate-900">
      {/* Desktop Fixed Sidebar */}
      <aside className="hidden lg:block w-[268px] shrink-0 sticky top-0 h-screen">
        {sidebarContent}
      </aside>

      {/* Main Content Column */}
      <div className="flex min-w-0 flex-1 flex-col">
        {/* Top Header */}
        <header className="sticky top-0 z-20 flex h-[68px] items-center justify-between gap-4 border-b border-slate-200 bg-white px-4 lg:px-7">
          <div className="flex items-center gap-3 min-w-0">
            <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
              <SheetTrigger asChild>
                <Button variant="outline" size="icon" className="lg:hidden shrink-0">
                  <Menu className="h-4 w-4" />
                </Button>
              </SheetTrigger>
              <SheetContent side="left" className="p-0 w-[268px] border-r-0">
                {sidebarContent}
              </SheetContent>
            </Sheet>

            <div className="min-w-0">
              <p className="text-[10.5px] font-semibold uppercase tracking-wider text-slate-400">
                UBND CẤP XÃ · HỆ THỐNG NỘI BỘ
              </p>
              <h1 className="text-base lg:text-lg font-bold text-slate-900 truncate">
                {currentDept.name}
              </h1>
            </div>
          </div>

          <div className="flex items-center gap-2.5 shrink-0">
            <Button
              variant="outline"
              size="sm"
              className="hidden sm:inline-flex gap-1.5 border-slate-300 text-slate-700"
              onClick={() => navigate(buildHref("/xu-ly-tai-lieu"))}
            >
              <Upload className="h-3.5 w-3.5" />
              Tải tài liệu tham khảo
            </Button>
            <Button
              size="sm"
              className="bg-blue-600 hover:bg-blue-700 text-white gap-1.5"
              onClick={() => navigate(buildHref("/soan-thao-kiem-tra"))}
            >
              <Plus className="h-3.5 w-3.5" />
              Kiểm tra văn bản
            </Button>
          </div>
        </header>

        {/* Active Module Workspace */}
        <main className="flex-1 p-4 lg:p-6">
          <Outlet />
        </main>

        {/* Verbatim Legal Accountability Footer */}
        <footer className="border-t border-slate-200 bg-white/90 px-4 lg:px-7 py-2.5 text-center text-xs text-slate-600">
          <span className="font-semibold text-slate-800">Nguyên tắc sử dụng: </span>
          {LEGAL_DISCLAIMER_TEXT}
        </footer>
      </div>
    </div>
  );
}
