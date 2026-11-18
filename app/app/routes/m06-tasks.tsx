import { useState } from "react";
import { useRevalidator, useSearchParams } from "react-router";
import {
  BellRing,
  CheckCircle2,
  ClipboardList,
  Clock,
  Plus,
  TrendingUp,
} from "lucide-react";
import type { Route } from "./+types/m06-tasks";
import {
  apiRequest,
  normalizeDepartmentId,
  resolveServerApiBase,
  type DepartmentId,
  type TaskItem,
  type TasksOverview,
} from "~/lib/api";
import {
  formatPriorityLabel,
  formatTaskStatusLabel,
} from "~/lib/m06-m07-helpers";
import { getActiveActorEmail } from "~/lib/session";
import { Badge } from "~/components/ui/badge";
import { Button } from "~/components/ui/button";
import {
  Card,
  CardContent,
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
import { Progress } from "~/components/ui/progress";
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
import { Textarea } from "~/components/ui/textarea";

export function meta({ }: Route.MetaArgs) {
  return [{ title: "Mô-đun 06 · Điều hành công việc — UBND Xã, Phường" }];
}

export async function loader({ request }: Route.LoaderArgs) {
  const url = new URL(request.url);
  const deptId = normalizeDepartmentId(url.searchParams.get("dept"));
  const filterDept = url.searchParams.get("filterDept") ?? "ALL";
  const baseUrl = resolveServerApiBase();

  try {
    const query =
      filterDept !== "ALL"
        ? `?department_id=${encodeURIComponent(filterDept)}`
        : "";
    const overview = await apiRequest<TasksOverview>(`/api/m06/tasks${query}`, {
      baseUrl,
    });
    return { deptId, filterDept, overview };
  } catch {
    return {
      deptId,
      filterDept,
      overview: {
        kpis: { total: 0, in_progress: 0, due_soon: 0, completed: 0 },
        tasks: [],
      } as TasksOverview,
    };
  }
}

export default function Module06TasksRoute({ loaderData }: Route.ComponentProps) {
  const [searchParams, setSearchParams] = useSearchParams();
  const revalidator = useRevalidator();
  const deptId = normalizeDepartmentId(
    searchParams.get("dept") ?? loaderData.deptId,
  );

  const [createOpen, setCreateOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [taskDept, setTaskDept] = useState<DepartmentId>(deptId);
  const [assignee, setAssignee] = useState("");
  const [dueDate, setDueDate] = useState("2026-11-28");
  const [priority, setPriority] = useState<TaskItem["priority"]>("cao");
  const [refDoc, setRefDoc] = useState("399/2026/NĐ-CP");
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);

  function setDeptFilter(nextFilter: string) {
    const next = new URLSearchParams(searchParams);
    next.set("dept", deptId);
    if (nextFilter === "ALL") next.delete("filterDept");
    else next.set("filterDept", nextFilter);
    setSearchParams(next);
  }

  async function handleCreateTask(ev: React.FormEvent) {
    ev.preventDefault();
    if (!title.trim() || !assignee.trim()) return;
    setBusy(true);
    setFeedback(null);
    try {
      await apiRequest("/api/m06/tasks", {
        method: "POST",
        actorEmail: getActiveActorEmail(),
        body: {
          title: title.trim(),
          description: description.trim(),
          department_id: taskDept,
          assignee: assignee.trim(),
          due_date: dueDate,
          priority,
          ref_doc_number: refDoc.trim(),
        },
      });
      setTitle("");
      setDescription("");
      setAssignee("");
      setCreateOpen(false);
      setFeedback("Đã giao nhiệm vụ mới và ghi nhận vào bảng điều hành.");
      revalidator.revalidate();
    } catch (err) {
      setFeedback(err instanceof Error ? err.message : "Không thể giao việc");
    } finally {
      setBusy(false);
    }
  }

  async function handlePatchTask(
    task: TaskItem,
    opts: { progress?: number; status?: TaskItem["status"]; remind?: boolean },
  ) {
    setBusy(true);
    setFeedback(null);
    try {
      await apiRequest(`/api/m06/tasks/${task.id}`, {
        method: "PATCH",
        actorEmail: getActiveActorEmail(),
        body: opts,
      });
      if (opts.remind) {
        setFeedback(`Đã gửi nhắc việc cho cán bộ ${task.assignee}.`);
      }
      revalidator.revalidate();
    } catch (err) {
      setFeedback(err instanceof Error ? err.message : "Lỗi cập nhật tiến độ");
    } finally {
      setBusy(false);
    }
  }

  const { kpis, tasks } = loaderData.overview;

  return (
    <div className="mx-auto max-w-6xl space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-[11px] font-bold uppercase tracking-wider text-blue-600">
            MÔ-ĐUN 06 · ĐIỀU HÀNH & THEO DÕI NHIỆM VỤ
          </p>
          <h2 className="text-xl font-bold text-slate-900">
            Giao việc, nhắc việc và tổng hợp tiến độ các bộ phận chuyên môn
          </h2>
        </div>

        <Dialog open={createOpen} onOpenChange={setCreateOpen}>
          <DialogTrigger asChild>
            <Button className="bg-blue-600 hover:bg-blue-700 text-white gap-1.5">
              <Plus className="h-4 w-4" />
              Giao nhiệm vụ mới
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Giao nhiệm vụ mới cho bộ phận chuyên môn</DialogTitle>
              <DialogDescription>
                Phân công rõ đầu mối cán bộ, hạn hoàn thành và văn bản căn cứ.
              </DialogDescription>
            </DialogHeader>
            <form onSubmit={handleCreateTask} className="space-y-3">
              <Input
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Tên nhiệm vụ cần thực hiện..."
                required
              />
              <Textarea
                rows={2}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Yêu cầu chi tiết về sản phẩm đầu ra..."
              />
              <div className="grid grid-cols-2 gap-2.5">
                <Select
                  value={taskDept}
                  onValueChange={(v) => setTaskDept(v as DepartmentId)}
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

                <Select
                  value={priority}
                  onValueChange={(v) => setPriority(v as TaskItem["priority"])}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="thap">Mức độ: Thấp</SelectItem>
                    <SelectItem value="trung_binh">Mức độ: Trung bình</SelectItem>
                    <SelectItem value="cao">Mức độ: Cao</SelectItem>
                    <SelectItem value="khan">Mức độ: Khẩn</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="grid grid-cols-2 gap-2.5">
                <Input
                  value={assignee}
                  onChange={(e) => setAssignee(e.target.value)}
                  placeholder="Cán bộ phụ trách..."
                  required
                />
                <Input
                  type="date"
                  value={dueDate}
                  onChange={(e) => setDueDate(e.target.value)}
                  required
                />
              </div>
              <Input
                value={refDoc}
                onChange={(e) => setRefDoc(e.target.value)}
                placeholder="Số hiệu văn bản giao việc / căn cứ..."
              />
              <DialogFooter>
                <Button type="submit" disabled={busy}>
                  {busy ? "Đang lưu..." : "Xác nhận giao việc"}
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      {/* 4 KPI Summary Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3.5">
        <Card className="border-slate-200 shadow-xs">
          <CardHeader className="pb-2 flex flex-row items-center justify-between">
            <CardTitle className="text-xs font-semibold text-slate-500">
              Tổng nhiệm vụ
            </CardTitle>
            <ClipboardList className="h-4 w-4 text-blue-600" />
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-extrabold text-slate-900">{kpis.total}</p>
          </CardContent>
        </Card>

        <Card className="border-slate-200 shadow-xs">
          <CardHeader className="pb-2 flex flex-row items-center justify-between">
            <CardTitle className="text-xs font-semibold text-slate-500">
              Đang thực hiện
            </CardTitle>
            <TrendingUp className="h-4 w-4 text-indigo-600" />
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-extrabold text-indigo-700">
              {kpis.in_progress}
            </p>
          </CardContent>
        </Card>

        <Card className="border-slate-200 shadow-xs">
          <CardHeader className="pb-2 flex flex-row items-center justify-between">
            <CardTitle className="text-xs font-semibold text-slate-500">
              Sắp đến hạn / Cần đôn đốc
            </CardTitle>
            <Clock className="h-4 w-4 text-amber-600" />
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-extrabold text-amber-600">
              {kpis.due_soon}
            </p>
          </CardContent>
        </Card>

        <Card className="border-slate-200 shadow-xs">
          <CardHeader className="pb-2 flex flex-row items-center justify-between">
            <CardTitle className="text-xs font-semibold text-slate-500">
              Đã hoàn thành
            </CardTitle>
            <CheckCircle2 className="h-4 w-4 text-emerald-600" />
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-extrabold text-emerald-700">
              {kpis.completed}
            </p>
          </CardContent>
        </Card>
      </div>

      {feedback && (
        <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-2 text-xs font-medium text-emerald-900">
          {feedback}
        </div>
      )}

      {/* Filter Pills + Tasks Table */}
      <Card className="border-slate-200 shadow-xs">
        <CardContent className="pt-5 space-y-4">
          <div className="flex flex-wrap items-center gap-2">
            {[
              { id: "ALL", label: "Tất cả 4 bộ phận" },
              { id: "VP", label: "Văn phòng HĐND & UBND" },
              { id: "KT", label: "Kinh tế" },
              { id: "VHXH", label: "Văn hóa - Xã hội" },
              { id: "NNMT", label: "Nông nghiệp & Môi trường" },
            ].map((item) => (
              <Button
                key={item.id}
                type="button"
                size="sm"
                variant={loaderData.filterDept === item.id ? "default" : "outline"}
                onClick={() => setDeptFilter(item.id)}
                className="text-xs h-8"
              >
                {item.label}
              </Button>
            ))}
          </div>

          <div className="rounded-lg border border-slate-200 overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow className="bg-slate-50">
                  <TableHead>Nhiệm vụ & Căn cứ</TableHead>
                  <TableHead className="w-[120px]">Bộ phận</TableHead>
                  <TableHead className="w-[150px]">Phụ trách & Hạn</TableHead>
                  <TableHead className="w-[170px]">Tiến độ</TableHead>
                  <TableHead className="w-[210px] text-right">Điều hành</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {tasks.map((t) => (
                  <TableRow key={t.id}>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-xs text-slate-900">
                          {t.title}
                        </span>
                        <Badge variant="outline" className="text-[10px]">
                          {formatPriorityLabel(t.priority)}
                        </Badge>
                      </div>
                      {t.description && (
                        <p className="text-xs text-slate-500 mt-0.5 line-clamp-1">
                          {t.description}
                        </p>
                      )}
                      {t.ref_doc_number && (
                        <p className="text-[11px] text-blue-600 mt-0.5">
                          Văn bản: {t.ref_doc_number}
                        </p>
                      )}
                    </TableCell>
                    <TableCell>
                      <Badge variant="secondary" className="text-xs">
                        {t.department_id}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-xs">
                      <p className="font-medium text-slate-900">{t.assignee}</p>
                      <p className="text-[11px] text-slate-500">Hạn: {t.due_date}</p>
                    </TableCell>
                    <TableCell>
                      <div className="space-y-1">
                        <div className="flex items-center justify-between text-[11px]">
                          <span className="font-medium text-slate-700">
                            {formatTaskStatusLabel(t.status)}
                          </span>
                          <span className="font-bold text-blue-700">
                            {t.progress}%
                          </span>
                        </div>
                        <Progress value={t.progress} className="h-1.5" />
                      </div>
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="inline-flex items-center gap-1.5">
                        {t.progress < 100 && (
                          <Button
                            type="button"
                            variant="outline"
                            size="sm"
                            disabled={busy}
                            onClick={() =>
                              void handlePatchTask(t, {
                                progress: Math.min(100, t.progress + 25),
                              })
                            }
                            className="h-7 px-2 text-[11px]"
                          >
                            +25%
                          </Button>
                        )}
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          disabled={busy}
                          onClick={() => void handlePatchTask(t, { remind: true })}
                          className="h-7 px-2 text-[11px] gap-1 text-amber-700 border-amber-200 hover:bg-amber-50"
                        >
                          <BellRing className="h-3 w-3" />
                          Nhắc ({t.reminder_count})
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
