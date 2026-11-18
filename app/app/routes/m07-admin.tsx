import { useEffect, useState } from "react";
import { useRevalidator, useSearchParams } from "react-router";
import {
  AlertTriangle,
  CheckCircle2,
  Copy,
  History,
  KeyRound,
  Plus,
  RefreshCw,
  Save,
  ShieldCheck,
  SlidersHorizontal,
  Trash2,
} from "lucide-react";
import type { Route } from "./+types/m07-admin";
import {
  apiRequest,
  normalizeDepartmentId,
  resolveServerApiBase,
  type ApiConnector,
  type AuditLogEntry,
  type ClonedTenant,
  type Department,
  type DepartmentId,
  type RbacUser,
} from "~/lib/api";
import { ADMIN_TABS, normalizeAdminTab, type AdminTabId } from "~/lib/m06-m07-helpers";
import { getActiveActorEmail } from "~/lib/session";
import { Alert, AlertDescription } from "~/components/ui/alert";
import { Badge } from "~/components/ui/badge";
import { Button } from "~/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "~/components/ui/card";
import { Input } from "~/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "~/components/ui/select";
import { Switch } from "~/components/ui/switch";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "~/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "~/components/ui/tabs";
import { Textarea } from "~/components/ui/textarea";

export function meta({ }: Route.MetaArgs) {
  return [{ title: "Mô-đun 07 · Phân quyền & Quản trị hệ thống — UBND Xã, Phường" }];
}

export async function loader({ request }: Route.LoaderArgs) {
  const url = new URL(request.url);
  const deptId = normalizeDepartmentId(url.searchParams.get("dept"));
  const baseUrl = resolveServerApiBase();

  try {
    const [deptRes, userRes, connRes, logRes, tenantRes] = await Promise.all([
      apiRequest<{ departments: Department[] }>("/api/departments", { baseUrl }),
      apiRequest<{ users: RbacUser[] }>("/api/m07/users", { baseUrl }),
      apiRequest<{ connectors: ApiConnector[] }>("/api/m07/api-connectors", {
        baseUrl,
      }),
      apiRequest<{ logs: AuditLogEntry[] }>("/api/m07/audit-logs?limit=40", {
        baseUrl,
      }),
      apiRequest<{ tenants: ClonedTenant[] }>("/api/m07/tenants", { baseUrl }),
    ]);
    return {
      deptId,
      departments: deptRes.departments,
      users: userRes.users,
      connectors: connRes.connectors,
      logs: logRes.logs,
      tenants: tenantRes.tenants,
    };
  } catch {
    return {
      deptId,
      departments: [] as Department[],
      users: [] as RbacUser[],
      connectors: [] as ApiConnector[],
      logs: [] as AuditLogEntry[],
      tenants: [] as ClonedTenant[],
    };
  }
}

export default function Module07AdminRoute({ loaderData }: Route.ComponentProps) {
  const [searchParams, setSearchParams] = useSearchParams();
  const revalidator = useRevalidator();

  const deptId = normalizeDepartmentId(
    searchParams.get("dept") ?? loaderData.deptId,
  );
  const activeTab = normalizeAdminTab(searchParams.get("tab"));

  const [banner, setBanner] = useState<{
    tone: "ok" | "err";
    text: string;
  } | null>(null);
  const [busy, setBusy] = useState(false);

  // RBAC form state
  const [newEmail, setNewEmail] = useState("");
  const [newName, setNewName] = useState("");
  const [newPosition, setNewPosition] = useState("Công chức chuyên môn");
  const [newUserDept, setNewUserDept] = useState<DepartmentId>(deptId);
  const [newPrivateAccess, setNewPrivateAccess] = useState(true);

  // Instruction editor state
  const [instDeptId, setInstDeptId] = useState<DepartmentId>(deptId);
  const matchedDept = loaderData.departments.find((d) => d.id === instDeptId);
  const [instText, setInstText] = useState(matchedDept?.instruction ?? "");

  useEffect(() => {
    setInstDeptId(deptId);
  }, [deptId]);

  useEffect(() => {
    const d = loaderData.departments.find((item) => item.id === instDeptId);
    if (d) setInstText(d.instruction);
  }, [instDeptId, loaderData.departments]);

  // API Connector state
  const firstConnector = loaderData.connectors[0];
  const [connName, setConnName] = useState(
    firstConnector?.name ?? "Cổng LLM Nội bộ / OpenAI-Compatible",
  );
  const [connUrl, setConnUrl] = useState(
    firstConnector?.base_url ?? "https://api.openai.com/v1",
  );
  const [connModel, setConnModel] = useState(
    firstConnector?.model_name ?? "gpt-4o-mini",
  );
  const [connKey, setConnKey] = useState("");
  const [connActive, setConnActive] = useState(firstConnector?.active ?? false);

  // Clone Tenant state
  const [communeName, setCommuneName] = useState("UBND Phường Hòa Xuân");
  const [communeAdmin, setCommuneAdmin] = useState("admin.hoaxuan@ubnd.gov.vn");

  function handleTabChange(next: string) {
    const tab = normalizeAdminTab(next);
    const params = new URLSearchParams(searchParams);
    params.set("dept", deptId);
    params.set("tab", tab);
    setSearchParams(params);
    setBanner(null);
  }

  async function handleAddUser(ev: React.FormEvent) {
    ev.preventDefault();
    if (!newEmail.trim() || !newName.trim()) return;
    setBusy(true);
    setBanner(null);
    try {
      await apiRequest("/api/m07/users", {
        method: "POST",
        actorEmail: getActiveActorEmail(),
        body: {
          email: newEmail.trim(),
          full_name: newName.trim(),
          position: newPosition.trim(),
          role: "officer",
          department_id: newUserDept,
          private_repo_access: newPrivateAccess,
        },
      });
      setNewEmail("");
      setNewName("");
      setBanner({
        tone: "ok",
        text: "Đã phân quyền tài khoản cán bộ mới thành công.",
      });
      revalidator.revalidate();
    } catch (err) {
      setBanner({
        tone: "err",
        text: err instanceof Error ? err.message : "Lỗi phân quyền tài khoản",
      });
    } finally {
      setBusy(false);
    }
  }

  async function handleDeleteUser(userId: number) {
    setBusy(true);
    setBanner(null);
    try {
      await apiRequest(`/api/m07/users/${userId}`, {
        method: "DELETE",
        actorEmail: getActiveActorEmail(),
      });
      setBanner({ tone: "ok", text: "Đã thu hồi quyền truy cập tài khoản." });
      revalidator.revalidate();
    } catch (err) {
      setBanner({
        tone: "err",
        text: err instanceof Error ? err.message : "Không thể thu hồi quyền",
      });
    } finally {
      setBusy(false);
    }
  }

  async function handleSaveInstruction(ev: React.FormEvent) {
    ev.preventDefault();
    setBusy(true);
    setBanner(null);
    try {
      await apiRequest(`/api/m07/departments/${instDeptId}/instruction`, {
        method: "PUT",
        actorEmail: getActiveActorEmail(),
        body: { instruction: instText },
      });
      setBanner({
        tone: "ok",
        text: `Đã lưu Instruction nghiệp vụ cho phòng ${instDeptId}.`,
      });
      revalidator.revalidate();
    } catch (err) {
      setBanner({
        tone: "err",
        text: err instanceof Error ? err.message : "Không thể cập nhật Instruction",
      });
    } finally {
      setBusy(false);
    }
  }

  async function handleSaveConnector(ev: React.FormEvent) {
    ev.preventDefault();
    if (!firstConnector) return;
    setBusy(true);
    setBanner(null);
    try {
      await apiRequest(`/api/m07/api-connectors/${firstConnector.id}`, {
        method: "PUT",
        actorEmail: getActiveActorEmail(),
        body: {
          name: connName,
          provider: "openai-compatible",
          base_url: connUrl,
          model_name: connModel,
          api_key: connKey.trim() || null,
          active: connActive,
        },
      });
      setConnKey("");
      setBanner({
        tone: "ok",
        text: "Đã cập nhật cấu hình Cổng API đấu nối (khóa bí mật được che an toàn).",
      });
      revalidator.revalidate();
    } catch (err) {
      setBanner({
        tone: "err",
        text: err instanceof Error ? err.message : "Không thể lưu Cổng API",
      });
    } finally {
      setBusy(false);
    }
  }

  async function handleCloneTenant(ev: React.FormEvent) {
    ev.preventDefault();
    if (!communeName.trim() || !communeAdmin.trim()) return;
    setBusy(true);
    setBanner(null);
    try {
      const created = await apiRequest<ClonedTenant>("/api/m07/clone-tenant", {
        method: "POST",
        actorEmail: getActiveActorEmail(),
        body: {
          commune_name: communeName.trim(),
          admin_email: communeAdmin.trim(),
        },
      });
      setBanner({
        tone: "ok",
        text: `Đã nhân bản thành công hệ thống AI độc lập '${created.commune_name}' (mã định danh: ${created.slug}).`,
      });
      revalidator.revalidate();
    } catch (err) {
      setBanner({
        tone: "err",
        text: err instanceof Error ? err.message : "Không thể nhân bản hệ thống",
      });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <div>
        <p className="text-[11px] font-bold uppercase tracking-wider text-blue-600">
          MÔ-ĐUN 07 · QUẢN TRỊ, PHÂN QUYỀN & NHÂN BẢN HỆ THỐNG
        </p>
        <h2 className="text-xl font-bold text-slate-900">
          Tổ chức tài khoản theo 4 nhóm nghiệp vụ & Triển khai độc lập cho từng xã, phường
        </h2>
      </div>

      {/* 4 Specialized Department Group Summary Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        {loaderData.departments.map((d) => {
          const count = loaderData.users.filter(
            (u) => u.department_id === d.id,
          ).length;
          return (
            <Card key={d.id} className="border-slate-200 shadow-xs">
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                  <Badge variant="secondary" className="font-bold">
                    {d.code}
                  </Badge>
                  <span className="text-xs font-semibold text-blue-700">
                    {count} tài khoản
                  </span>
                </div>
                <CardTitle className="text-sm pt-1">{d.name}</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-[11px] text-slate-500 line-clamp-2">
                  {d.scope_summary}
                </p>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {banner && (
        <Alert
          variant={banner.tone === "err" ? "destructive" : "default"}
          className={
            banner.tone === "ok"
              ? "border-emerald-200 bg-emerald-50 text-emerald-900 py-2.5"
              : "py-2.5"
          }
        >
          <AlertDescription className="text-xs flex items-center gap-1.5">
            {banner.tone === "ok" ? (
              <CheckCircle2 className="h-4 w-4 text-emerald-600 shrink-0" />
            ) : (
              <AlertTriangle className="h-4 w-4 shrink-0" />
            )}
            {banner.text}
          </AlertDescription>
        </Alert>
      )}

      <Tabs value={activeTab} onValueChange={(v) => handleTabChange(v as AdminTabId)}>
        <TabsList className="flex flex-wrap h-auto">
          {ADMIN_TABS.map((t) => (
            <TabsTrigger key={t.id} value={t.id} className="text-xs">
              {t.label}
            </TabsTrigger>
          ))}
        </TabsList>

        {/* Tab 1: Phân quyền email */}
        <TabsContent value="phan-quyen" className="grid grid-cols-1 lg:grid-cols-12 gap-4 pt-3">
          <Card className="lg:col-span-4 border-slate-200 shadow-xs h-fit">
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-1.5">
                <ShieldCheck className="h-4 w-4 text-blue-600" />
                Cấp quyền email cán bộ
              </CardTitle>
              <CardDescription className="text-xs">
                Chỉ Chủ sở hữu hệ thống mới có quyền thêm hoặc thu hồi tài khoản.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleAddUser} className="space-y-3">
                <Input
                  type="email"
                  value={newEmail}
                  onChange={(e) => setNewEmail(e.target.value)}
                  placeholder="Email công vụ (VD: canbo.tp@ubnd.vn)"
                  required
                />
                <Input
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  placeholder="Họ và tên cán bộ..."
                  required
                />
                <Input
                  value={newPosition}
                  onChange={(e) => setNewPosition(e.target.value)}
                  placeholder="Chức danh / Vị trí..."
                />
                <Select
                  value={newUserDept}
                  onValueChange={(v) => setNewUserDept(v as DepartmentId)}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="VP">Văn phòng HĐND & UBND</SelectItem>
                    <SelectItem value="KT">Kinh tế</SelectItem>
                    <SelectItem value="VHXH">Văn hóa - Xã hội</SelectItem>
                    <SelectItem value="NNMT">Nông nghiệp & Môi trường</SelectItem>
                  </SelectContent>
                </Select>
                <div className="flex items-center justify-between rounded-lg border border-slate-200 p-2.5 text-xs">
                  <span>Quyền khai thác Kho dữ liệu riêng</span>
                  <Switch
                    checked={newPrivateAccess}
                    onCheckedChange={setNewPrivateAccess}
                  />
                </div>
                <Button
                  type="submit"
                  disabled={busy}
                  className="w-full bg-blue-600 hover:bg-blue-700 text-white gap-1.5"
                >
                  <Plus className="h-4 w-4" />
                  Thêm tài khoản cán bộ
                </Button>
              </form>
            </CardContent>
          </Card>

          <Card className="lg:col-span-8 border-slate-200 shadow-xs">
            <CardHeader>
              <CardTitle className="text-base">
                Danh sách tài khoản & Phạm vi phân quyền ({loaderData.users.length})
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="rounded-lg border border-slate-200 overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow className="bg-slate-50">
                      <TableHead>Email & Họ tên</TableHead>
                      <TableHead>Nhóm nghiệp vụ</TableHead>
                      <TableHead>Kho riêng</TableHead>
                      <TableHead>Vai trò</TableHead>
                      <TableHead className="text-right">Thao tác</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {loaderData.users.map((u) => (
                      <TableRow key={u.id}>
                        <TableCell className="text-xs">
                          <p className="font-semibold text-slate-900">{u.email}</p>
                          <p className="text-slate-500">
                            {u.full_name} · {u.position}
                          </p>
                        </TableCell>
                        <TableCell>
                          <Badge variant="secondary" className="text-xs">
                            {u.department_id}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-xs">
                          {u.private_repo_access ? "Được phép" : "Giới hạn"}
                        </TableCell>
                        <TableCell>
                          <Badge
                            className={
                              u.role === "owner"
                                ? "bg-blue-600 text-white text-[10px]"
                                : "bg-slate-200 text-slate-800 text-[10px]"
                            }
                          >
                            {u.role === "owner" ? "Chủ sở hữu" : "Cán bộ"}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-right">
                          {u.role !== "owner" && (
                            <Button
                              type="button"
                              variant="ghost"
                              size="sm"
                              disabled={busy}
                              onClick={() => void handleDeleteUser(u.id)}
                              className="h-7 px-2 text-rose-600 hover:text-rose-700"
                            >
                              <Trash2 className="h-3.5 w-3.5" />
                            </Button>
                          )}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Tab 2: Instruction của phòng */}
        <TabsContent value="instruction" className="pt-3">
          <Card className="border-slate-200 shadow-xs max-w-3xl">
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-1.5">
                <SlidersHorizontal className="h-4 w-4 text-blue-600" />
                Cấu hình Instruction chuyên biệt cho từng phòng
              </CardTitle>
              <CardDescription className="text-xs">
                Chỉ dẫn này được gắn trực tiếp vào ngữ cảnh của Trợ lý AI khi cán bộ
                làm việc trong không gian phòng tương ứng.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleSaveInstruction} className="space-y-4">
                <Select
                  value={instDeptId}
                  onValueChange={(v) => setInstDeptId(v as DepartmentId)}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {loaderData.departments.map((d) => (
                      <SelectItem key={d.id} value={d.id}>
                        {d.name} ({d.code})
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>

                <Textarea
                  rows={6}
                  value={instText}
                  onChange={(e) => setInstText(e.target.value)}
                />

                <Button
                  type="submit"
                  disabled={busy}
                  className="bg-blue-600 hover:bg-blue-700 text-white gap-1.5"
                >
                  <Save className="h-4 w-4" />
                  Lưu Instruction của phòng {instDeptId}
                </Button>
              </form>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Tab 3: Cổng API đấu nối */}
        <TabsContent value="api" className="pt-3">
          <Card className="border-slate-200 shadow-xs max-w-2xl">
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-1.5">
                <KeyRound className="h-4 w-4 text-blue-600" />
                Cổng API đấu nối mô hình ngôn ngữ (LLM Gateway)
              </CardTitle>
              <CardDescription className="text-xs">
                Khóa bí mật API luôn được che dạng <code>***</code> khi hiển thị trên
                giao diện quản trị.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleSaveConnector} className="space-y-3.5">
                <div className="space-y-1">
                  <label className="text-xs font-semibold text-slate-700">
                    Tên cổng kết nối
                  </label>
                  <Input
                    value={connName}
                    onChange={(e) => setConnName(e.target.value)}
                  />
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div className="space-y-1">
                    <label className="text-xs font-semibold text-slate-700">
                      Base URL (OpenAI-compatible)
                    </label>
                    <Input
                      value={connUrl}
                      onChange={(e) => setConnUrl(e.target.value)}
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs font-semibold text-slate-700">
                      Model Name
                    </label>
                    <Input
                      value={connModel}
                      onChange={(e) => setConnModel(e.target.value)}
                    />
                  </div>
                </div>
                <div className="space-y-1">
                  <label className="text-xs font-semibold text-slate-700 flex items-center justify-between">
                    <span>API Secret Key (chỉ nhập khi muốn thay đổi)</span>
                    <Badge variant="outline" className="font-mono text-[11px]">
                      Hiện tại:{" "}
                      {firstConnector?.api_key_masked || "Chưa thiết lập khóa"}
                    </Badge>
                  </label>
                  <Input
                    type="password"
                    value={connKey}
                    onChange={(e) => setConnKey(e.target.value)}
                    placeholder="sk-..."
                  />
                </div>
                <div className="flex items-center justify-between rounded-lg border border-slate-200 p-3 text-xs">
                  <div>
                    <p className="font-semibold text-slate-900">
                      Kích hoạt gọi LLM trực tiếp
                    </p>
                    <p className="text-slate-500">
                      Khi tắt, hệ thống sử dụng bộ tổng hợp hành chính chuẩn nội bộ.
                    </p>
                  </div>
                  <Switch checked={connActive} onCheckedChange={setConnActive} />
                </div>
                <Button
                  type="submit"
                  disabled={busy}
                  className="bg-blue-600 hover:bg-blue-700 text-white gap-1.5"
                >
                  <Save className="h-4 w-4" />
                  Lưu cấu hình Cổng API
                </Button>
              </form>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Tab 4: Nhật ký hệ thống */}
        <TabsContent value="nhat-ky" className="pt-3">
          <Card className="border-slate-200 shadow-xs">
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle className="text-base flex items-center gap-1.5">
                  <History className="h-4 w-4 text-blue-600" />
                  Nhật ký hoạt động hệ thống ({loaderData.logs.length} bản ghi gần nhất)
                </CardTitle>
                <CardDescription className="text-xs">
                  Ghi nhận thao tác nghiệp vụ mà không lưu trữ nội dung tài liệu tạm
                  của phiên.
                </CardDescription>
              </div>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => revalidator.revalidate()}
                className="gap-1.5 text-xs"
              >
                <RefreshCw className="h-3.5 w-3.5" />
                Làm mới
              </Button>
            </CardHeader>
            <CardContent>
              <div className="rounded-lg border border-slate-200 overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow className="bg-slate-50">
                      <TableHead className="w-[170px]">Thời gian</TableHead>
                      <TableHead className="w-[180px]">Tài khoản</TableHead>
                      <TableHead className="w-[90px]">Mô-đun</TableHead>
                      <TableHead className="w-[150px]">Hành động</TableHead>
                      <TableHead>Chi tiết</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {loaderData.logs.map((log) => (
                      <TableRow key={log.id} className="text-xs">
                        <TableCell className="text-slate-500 font-mono text-[11px]">
                          {log.created_at.slice(0, 19).replace("T", " ")}
                        </TableCell>
                        <TableCell className="font-medium">
                          {log.actor_email}
                        </TableCell>
                        <TableCell>
                          <Badge variant="outline" className="text-[10px]">
                            {log.module_code} · {log.department_id}
                          </Badge>
                        </TableCell>
                        <TableCell className="font-mono text-[11px] text-blue-700">
                          {log.action}
                        </TableCell>
                        <TableCell className="text-slate-700">
                          {log.detail}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Tab 5: Nhân bản AI */}
        <TabsContent value="nhan-ban" className="grid grid-cols-1 lg:grid-cols-12 gap-4 pt-3">
          <Card className="lg:col-span-5 border-slate-200 shadow-xs h-fit">
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-1.5">
                <Copy className="h-4 w-4 text-blue-600" />
                Nhân bản hệ thống AI độc lập
              </CardTitle>
              <CardDescription className="text-xs">
                Khởi tạo ngay một hệ thống độc lập mới (CSDL riêng, 4 không gian phòng
                ban và Chủ sở hữu riêng) cho từng xã, phường.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleCloneTenant} className="space-y-3">
                <div className="space-y-1">
                  <label className="text-xs font-semibold text-slate-700">
                    Tên đơn vị UBND xã / phường mới
                  </label>
                  <Input
                    value={communeName}
                    onChange={(e) => setCommuneName(e.target.value)}
                    placeholder="VD: UBND Phường Bến Nghé"
                    required
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-xs font-semibold text-slate-700">
                    Email Chủ sở hữu đơn vị mới
                  </label>
                  <Input
                    type="email"
                    value={communeAdmin}
                    onChange={(e) => setCommuneAdmin(e.target.value)}
                    placeholder="admin@tenphuong.gov.vn"
                    required
                  />
                </div>
                <Button
                  type="submit"
                  disabled={busy}
                  className="w-full bg-blue-600 hover:bg-blue-700 text-white gap-1.5"
                >
                  <Copy className="h-4 w-4" />
                  {busy ? "Đang khởi tạo..." : "Nhân bản hệ thống độc lập"}
                </Button>
              </form>
            </CardContent>
          </Card>

          <Card className="lg:col-span-7 border-slate-200 shadow-xs">
            <CardHeader>
              <CardTitle className="text-base">
                Các đơn vị xã, phường đã nhân bản ({loaderData.tenants.length})
              </CardTitle>
            </CardHeader>
            <CardContent>
              {loaderData.tenants.length === 0 ? (
                <p className="text-xs text-slate-500 py-8 text-center">
                  Chưa có bản nhân bản xã/phường nào. Hãy nhập tên đơn vị ở cột bên
                  trái để khởi tạo.
                </p>
              ) : (
                <div className="space-y-2.5">
                  {loaderData.tenants.map((t) => (
                    <div
                      key={t.id}
                      className="rounded-lg border border-slate-200 bg-slate-50/70 p-3.5 text-xs space-y-1"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-bold text-slate-900">
                          {t.commune_name}
                        </span>
                        <Badge className="bg-emerald-600 text-white font-mono text-[10px]">
                          {t.slug}
                        </Badge>
                      </div>
                      <p className="text-slate-600">
                        Chủ sở hữu: <strong>{t.admin_email}</strong>
                      </p>
                      <p className="font-mono text-[11px] text-slate-400 truncate">
                        CSDL độc lập: {t.db_path}
                      </p>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
