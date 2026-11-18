import { useState } from "react";
import { Form, useRevalidator, useSearchParams } from "react-router";
import {
  BookOpen,
  Eye,
  Plus,
  RefreshCw,
  Search,
  Shield,
} from "lucide-react";
import type { Route } from "./+types/m04-official-docs";
import {
  apiRequest,
  normalizeDepartmentId,
  resolveServerApiBase,
  type DocTier,
  type DocUpdateRequest,
  type OfficialDoc,
} from "~/lib/api";
import { formatTierLabel } from "~/lib/m03-m05-helpers";
import { getActiveActorEmail } from "~/lib/session";
import { Badge } from "~/components/ui/badge";
import { Button } from "~/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "~/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "~/components/ui/dialog";
import { Input } from "~/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "~/components/ui/select";
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

export function meta({}: Route.MetaArgs) {
  return [{ title: "Mô-đun 04 · Nguồn văn bản chính thức — UBND Xã, Phường" }];
}

export async function loader({ request }: Route.LoaderArgs) {
  const url = new URL(request.url);
  const deptId = normalizeDepartmentId(url.searchParams.get("dept"));
  const q = url.searchParams.get("q") ?? "";
  const tier = url.searchParams.get("tier") ?? "";
  const baseUrl = resolveServerApiBase();

  try {
    const params = new URLSearchParams();
    params.set("department_id", deptId);
    if (q) params.set("q", q);
    if (tier) params.set("tier", tier);

    const [docRes, reqRes] = await Promise.all([
      apiRequest<{ documents: OfficialDoc[] }>(
        `/api/m04/documents?${params.toString()}`,
        { baseUrl },
      ),
      apiRequest<{ requests: DocUpdateRequest[] }>("/api/m04/update-requests", {
        baseUrl,
      }),
    ]);

    return {
      deptId,
      q,
      tier,
      documents: docRes.documents,
      updateRequests: reqRes.requests,
    };
  } catch {
    return {
      deptId,
      q,
      tier,
      documents: [] as OfficialDoc[],
      updateRequests: [] as DocUpdateRequest[],
    };
  }
}

export default function Module04OfficialDocsRoute({
  loaderData,
}: Route.ComponentProps) {
  const [searchParams, setSearchParams] = useSearchParams();
  const revalidator = useRevalidator();
  const deptId = normalizeDepartmentId(
    searchParams.get("dept") ?? loaderData.deptId,
  );
  const activeTab =
    searchParams.get("tab") === "de-nghi" ? "de-nghi" : "danh-muc";

  const [selectedDoc, setSelectedDoc] = useState<OfficialDoc | null>(null);
  const [addOpen, setAddOpen] = useState(false);
  const [docNumber, setDocNumber] = useState("");
  const [docTitle, setDocTitle] = useState("");
  const [docTier, setDocTier] = useState<DocTier>("kho_rieng");
  const [docContent, setDocContent] = useState("");
  const [busyAdd, setBusyAdd] = useState(false);

  const [reqNumber, setReqNumber] = useState("");
  const [reqTitle, setReqTitle] = useState("");
  const [reqTier, setReqTier] = useState<DocTier>("trung_uong");
  const [reqReason, setReqReason] = useState("");
  const [busyReq, setBusyReq] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);

  function setTabParam(nextTab: string) {
    const next = new URLSearchParams(searchParams);
    next.set("dept", deptId);
    if (nextTab === "de-nghi") next.set("tab", "de-nghi");
    else next.delete("tab");
    setSearchParams(next);
  }

  function setTierFilter(nextTier: string) {
    const next = new URLSearchParams(searchParams);
    next.set("dept", deptId);
    if (nextTier === "all") next.delete("tier");
    else next.set("tier", nextTier);
    setSearchParams(next);
  }

  async function handleCreateDoc(ev: React.FormEvent) {
    ev.preventDefault();
    if (!docNumber.trim() || !docTitle.trim() || !docContent.trim()) return;
    setBusyAdd(true);
    setFeedback(null);
    try {
      await apiRequest("/api/m04/documents", {
        method: "POST",
        actorEmail: getActiveActorEmail(),
        body: {
          doc_number: docNumber.trim(),
          title: docTitle.trim(),
          doc_type: "Văn bản nội bộ",
          tier: docTier,
          department_id: docTier === "kho_rieng" ? deptId : "ALL",
          issuer: `UBND (${deptId})`,
          issued_date: "2026-11-18",
          summary: docContent.trim().slice(0, 180),
          content: docContent.trim(),
        },
      });
      setDocNumber("");
      setDocTitle("");
      setDocContent("");
      setAddOpen(false);
      setFeedback("Đã bổ sung văn bản mới vào kho dữ liệu.");
      revalidator.revalidate();
    } catch (err) {
      setFeedback(err instanceof Error ? err.message : "Không thể thêm văn bản");
    } finally {
      setBusyAdd(false);
    }
  }

  async function handleSubmitUpdateRequest(ev: React.FormEvent) {
    ev.preventDefault();
    if (!reqNumber.trim() || !reqTitle.trim() || !reqReason.trim()) return;
    setBusyReq(true);
    setFeedback(null);
    try {
      await apiRequest("/api/m04/update-requests", {
        method: "POST",
        actorEmail: getActiveActorEmail(),
        body: {
          doc_number: reqNumber.trim(),
          title: reqTitle.trim(),
          tier: reqTier,
          department_id: deptId,
          reason: reqReason.trim(),
          requested_by: getActiveActorEmail(),
        },
      });
      setReqNumber("");
      setReqTitle("");
      setReqReason("");
      setFeedback("Đã gửi đề nghị cập nhật văn bản thành công.");
      revalidator.revalidate();
    } catch (err) {
      setFeedback(err instanceof Error ? err.message : "Không thể gửi đề nghị");
    } finally {
      setBusyReq(false);
    }
  }

  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-[11px] font-bold uppercase tracking-wider text-blue-600">
            MÔ-ĐUN 04 · KHO PHÁP LÝ & DỮ LIỆU ĐƠN VỊ ({deptId})
          </p>
          <h2 className="text-xl font-bold text-slate-900">
            Nguồn văn bản chính thức & Kho dữ liệu riêng theo phân quyền
          </h2>
        </div>

        <Dialog open={addOpen} onOpenChange={setAddOpen}>
          <DialogTrigger asChild>
            <Button size="sm" className="bg-blue-600 hover:bg-blue-700 text-white gap-1.5">
              <Plus className="h-4 w-4" />
              Bổ sung văn bản vào kho
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Bổ sung văn bản vào kho ({deptId})</DialogTitle>
              <DialogDescription>
                Văn bản thuộc &ldquo;Kho dữ liệu riêng&rdquo; sẽ được cô lập theo đúng
                phòng chuyên môn {deptId}.
              </DialogDescription>
            </DialogHeader>
            <form onSubmit={handleCreateDoc} className="space-y-3">
              <Input
                value={docNumber}
                onChange={(e) => setDocNumber(e.target.value)}
                placeholder="Số hiệu (VD: QC-05/2026/UBND-VP)"
                required
              />
              <Input
                value={docTitle}
                onChange={(e) => setDocTitle(e.target.value)}
                placeholder="Trích yếu văn bản..."
                required
              />
              <Select
                value={docTier}
                onValueChange={(v) => setDocTier(v as DocTier)}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="kho_rieng">
                    Kho dữ liệu riêng phòng {deptId}
                  </SelectItem>
                  <SelectItem value="dia_phuong">Văn bản Địa phương</SelectItem>
                  <SelectItem value="trung_uong">Văn bản Trung ương</SelectItem>
                </SelectContent>
              </Select>
              <Textarea
                rows={4}
                value={docContent}
                onChange={(e) => setDocContent(e.target.value)}
                placeholder="Nội dung điều khoản cốt lõi phục vụ AI tra cứu..."
                required
              />
              <DialogFooter>
                <Button type="submit" disabled={busyAdd}>
                  {busyAdd ? "Đang lưu..." : "Lưu văn bản"}
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      {feedback && (
        <div className="rounded-lg border border-blue-200 bg-blue-50 px-4 py-2 text-xs font-medium text-blue-900">
          {feedback}
        </div>
      )}

      <Tabs value={activeTab} onValueChange={setTabParam}>
        <TabsList>
          <TabsTrigger value="danh-muc" className="gap-1.5">
            <BookOpen className="h-3.5 w-3.5" />
            Danh mục văn bản ({loaderData.documents.length})
          </TabsTrigger>
          <TabsTrigger value="de-nghi" className="gap-1.5">
            <RefreshCw className="h-3.5 w-3.5" />
            Đề nghị cập nhật văn bản ({loaderData.updateRequests.length})
          </TabsTrigger>
        </TabsList>

        <TabsContent value="danh-muc" className="space-y-4 pt-3">
          <Card className="border-slate-200 shadow-xs">
            <CardContent className="pt-5 space-y-4">
              <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
                <Form method="get" className="flex flex-1 gap-2">
                  <input type="hidden" name="dept" value={deptId} />
                  {loaderData.tier && (
                    <input type="hidden" name="tier" value={loaderData.tier} />
                  )}
                  <Input
                    name="q"
                    defaultValue={loaderData.q}
                    placeholder="Tìm theo số hiệu (VD: 30/2020/NĐ-CP, 399/2026/NĐ-CP) hoặc trích yếu..."
                    className="flex-1"
                  />
                  <Button type="submit" variant="secondary" className="gap-1.5">
                    <Search className="h-4 w-4" />
                    Tra cứu
                  </Button>
                </Form>

                <div className="flex flex-wrap gap-1.5">
                  {[
                    { id: "all", label: "Tất cả nguồn" },
                    { id: "trung_uong", label: "Trung ương" },
                    { id: "dia_phuong", label: "Địa phương" },
                    { id: "kho_rieng", label: `Kho riêng (${deptId})` },
                  ].map((t) => (
                    <Button
                      key={t.id}
                      type="button"
                      size="sm"
                      variant={
                        (loaderData.tier || "all") === t.id ? "default" : "outline"
                      }
                      onClick={() => setTierFilter(t.id)}
                      className="text-xs h-8"
                    >
                      {t.label}
                    </Button>
                  ))}
                </div>
              </div>

              <div className="rounded-lg border border-slate-200 overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow className="bg-slate-50">
                      <TableHead className="w-[150px]">Số hiệu</TableHead>
                      <TableHead>Trích yếu & Tóm tắt</TableHead>
                      <TableHead className="w-[150px]">Nguồn kho</TableHead>
                      <TableHead className="w-[110px]">Phạm vi</TableHead>
                      <TableHead className="w-[90px] text-right">Chi tiết</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {loaderData.documents.map((doc) => (
                      <TableRow key={doc.id}>
                        <TableCell className="font-semibold text-blue-700 text-xs">
                          {doc.doc_number}
                          <div className="text-[11px] font-normal text-slate-400">
                            {doc.issued_date}
                          </div>
                        </TableCell>
                        <TableCell>
                          <p className="font-semibold text-xs text-slate-900">
                            {doc.title}
                          </p>
                          <p className="text-xs text-slate-500 line-clamp-2 mt-0.5">
                            {doc.summary}
                          </p>
                        </TableCell>
                        <TableCell>
                          <Badge
                            variant="outline"
                            className={
                              doc.tier === "kho_rieng"
                                ? "border-amber-300 bg-amber-50 text-amber-800 text-[11px]"
                                : "border-blue-200 bg-blue-50 text-blue-700 text-[11px]"
                            }
                          >
                            {formatTierLabel(doc.tier)}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-xs">
                          <span className="inline-flex items-center gap-1 font-medium text-slate-700">
                            <Shield className="h-3 w-3 text-slate-400" />
                            {doc.department_id === "ALL"
                              ? "Toàn UBND"
                              : `Phòng ${doc.department_id}`}
                          </span>
                        </TableCell>
                        <TableCell className="text-right">
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            onClick={() => setSelectedDoc(doc)}
                            className="h-7 px-2 text-xs gap-1"
                          >
                            <Eye className="h-3.5 w-3.5" />
                            Xem
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="de-nghi" className="grid grid-cols-1 lg:grid-cols-12 gap-4 pt-3">
          <Card className="lg:col-span-5 border-slate-200 shadow-xs h-fit">
            <CardHeader>
              <CardTitle className="text-base">
                Gửi đề nghị cập nhật văn bản mới
              </CardTitle>
              <CardDescription className="text-xs">
                Khi phát hiện văn bản mới ban hành hoặc hết hiệu lực, cán bộ gửi đề
                nghị để Quản trị viên cập nhật vào nguồn chính thức.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleSubmitUpdateRequest} className="space-y-3">
                <Input
                  value={reqNumber}
                  onChange={(e) => setReqNumber(e.target.value)}
                  placeholder="Số hiệu văn bản (VD: 12/2026/TT-BNV)"
                  required
                />
                <Input
                  value={reqTitle}
                  onChange={(e) => setReqTitle(e.target.value)}
                  placeholder="Tên / Trích yếu văn bản cần cập nhật"
                  required
                />
                <Select
                  value={reqTier}
                  onValueChange={(v) => setReqTier(v as DocTier)}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="trung_uong">Văn bản Trung ương</SelectItem>
                    <SelectItem value="dia_phuong">Văn bản Địa phương</SelectItem>
                    <SelectItem value="kho_rieng">Kho dữ liệu riêng</SelectItem>
                  </SelectContent>
                </Select>
                <Textarea
                  rows={3}
                  value={reqReason}
                  onChange={(e) => setReqReason(e.target.value)}
                  placeholder="Lý do cập nhật / thay thế điều khoản nào..."
                  required
                />
                <Button
                  type="submit"
                  disabled={busyReq}
                  className="w-full bg-blue-600 hover:bg-blue-700 text-white"
                >
                  {busyReq ? "Đang gửi..." : "Gửi đề nghị cập nhật"}
                </Button>
              </form>
            </CardContent>
          </Card>

          <Card className="lg:col-span-7 border-slate-200 shadow-xs">
            <CardHeader>
              <CardTitle className="text-base">
                Danh sách đề nghị cập nhật đã ghi nhận
              </CardTitle>
            </CardHeader>
            <CardContent>
              {loaderData.updateRequests.length === 0 ? (
                <p className="text-xs text-slate-500 py-6 text-center">
                  Chưa có đề nghị cập nhật văn bản nào.
                </p>
              ) : (
                <div className="space-y-2.5">
                  {loaderData.updateRequests.map((r) => (
                    <div
                      key={r.id}
                      className="rounded-lg border border-slate-200 p-3 text-xs space-y-1"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-bold text-blue-700">
                          {r.doc_number} — {r.title}
                        </span>
                        <Badge variant="secondary" className="text-[10px]">
                          Chờ duyệt · {r.department_id}
                        </Badge>
                      </div>
                      <p className="text-slate-600">{r.reason}</p>
                      <p className="text-[11px] text-slate-400">
                        Người đề nghị: {r.requested_by}
                      </p>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Document Preview Dialog */}
      <Dialog
        open={Boolean(selectedDoc)}
        onOpenChange={(open) => !open && setSelectedDoc(null)}
      >
        <DialogContent className="max-w-2xl">
          {selectedDoc && (
            <>
              <DialogHeader>
                <DialogTitle>
                  {selectedDoc.doc_number} · {selectedDoc.title}
                </DialogTitle>
                <DialogDescription>
                  Cơ quan ban hành: {selectedDoc.issuer} · Ngày ban hành:{" "}
                  {selectedDoc.issued_date} · Phạm vi: {selectedDoc.department_id}
                </DialogDescription>
              </DialogHeader>
              <div className="space-y-3 text-xs leading-relaxed text-slate-700">
                <div className="rounded-lg bg-slate-50 p-3 border border-slate-200">
                  <p className="font-semibold text-slate-900 mb-1">Tóm tắt:</p>
                  <p>{selectedDoc.summary}</p>
                </div>
                <div className="rounded-lg bg-white p-3 border border-slate-200 whitespace-pre-wrap">
                  <p className="font-semibold text-slate-900 mb-1">
                    Nội dung trích lục phục vụ tra cứu AI:
                  </p>
                  <p>{selectedDoc.content}</p>
                </div>
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
