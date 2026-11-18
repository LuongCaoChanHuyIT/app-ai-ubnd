import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router";
import {
  AlertTriangle,
  FileSpreadsheet,
  FileText,
  FlaskConical,
  ShieldAlert,
  Sparkles,
  Trash2,
  Upload,
} from "lucide-react";
import type { Route } from "./+types/m05-doc-session";
import {
  apiRequest,
  normalizeDepartmentId,
  uploadSessionFile,
  type SessionFileItem,
  type SessionProcessAction,
  type SessionProcessResult,
  type SessionState,
} from "~/lib/api";
import { SESSION_PROCESS_TABS } from "~/lib/m03-m05-helpers";
import {
  getActiveActorEmail,
  getOrInitSessionId,
  rotateSessionId,
} from "~/lib/session";
import { Alert, AlertDescription, AlertTitle } from "~/components/ui/alert";
import { Badge } from "~/components/ui/badge";
import { Button } from "~/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "~/components/ui/card";
import { FormattedMarkdown } from "~/components/ui/formatted-markdown";

export function meta({}: Route.MetaArgs) {
  return [{ title: "Mô-đun 05 · Tải & Xử lý tài liệu phiên — UBND Xã, Phường" }];
}

export default function Module05DocSessionRoute() {
  const [searchParams] = useSearchParams();
  const deptId = normalizeDepartmentId(searchParams.get("dept"));

  const [sessionId, setSessionId] = useState("");
  const [files, setFiles] = useState<SessionFileItem[]>([]);
  const [activeAction, setActiveAction] =
    useState<SessionProcessAction>("doi_chieu");
  const [result, setResult] = useState<SessionProcessResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [banner, setBanner] = useState<{
    tone: "info" | "error";
    text: string;
  } | null>(null);

  const inputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    const sid = getOrInitSessionId();
    setSessionId(sid);
    void apiRequest<SessionState>(`/api/sessions/${encodeURIComponent(sid)}`)
      .then((state) => setFiles(state.files))
      .catch(() => {});

    const onRotated = (ev: Event) => {
      const nextSid = (ev as CustomEvent<string>).detail;
      if (nextSid) {
        setSessionId(nextSid);
        setFiles([]);
        setResult(null);
      }
    };
    window.addEventListener("ubnd-session-changed", onRotated);
    return () => window.removeEventListener("ubnd-session-changed", onRotated);
  }, []);

  async function handleFilesChosen(ev: React.ChangeEvent<HTMLInputElement>) {
    const selected = Array.from(ev.target.files ?? []);
    ev.target.value = "";
    if (!selected.length) return;
    setBusy(true);
    setBanner(null);
    const activeSid = sessionId || getOrInitSessionId();

    try {
      let latest: SessionState | null = null;
      for (const f of selected) {
        latest = await uploadSessionFile(
          activeSid,
          f,
          deptId,
          getActiveActorEmail(),
        );
      }
      if (latest) {
        setFiles(latest.files);
        setBanner({
          tone: "info",
          text: `Đã tải lên ${selected.length} tệp vào bộ nhớ phiên hiện tại.`,
        });
      }
    } catch (err) {
      setBanner({
        tone: "error",
        text: err instanceof Error ? err.message : "Không thể tải tệp lên",
      });
    } finally {
      setBusy(false);
    }
  }

  async function handleLoadSampleDossier() {
    setBusy(true);
    setBanner(null);
    const activeSid = sessionId || getOrInitSessionId();
    try {
      const f1 = new File(
        [
          "ĐƠN ĐỀ NGHỊ XÁC NHẬN NGUỒN GỐC ĐẤT\nHọ tên chủ hộ: Nguyễn Văn An.\nThửa đất số 42, tờ bản đồ số 08.\nDiện tích kê khai: 125 m2.\nNgày viết đơn: 10/10/2026.",
        ],
        "01_Don_de_nghi_Nguyen_Van_An.txt",
        { type: "text/plain" },
      );
      const f2 = new File(
        [
          "BIÊN BẢN XÁC MINH THỰC ĐỊA\nHọ tên chủ hộ: Nguyễn Văn An.\nThửa đất số 42, tờ bản đồ số 08.\nDiện tích đo đạc thực tế: 142 m2.\nNgày lập biên bản: 16/10/2026.",
        ],
        "02_Bien_ban_xac_minh_thuc_dia.txt",
        { type: "text/plain" },
      );
      await uploadSessionFile(activeSid, f1, deptId, getActiveActorEmail());
      const state = await uploadSessionFile(
        activeSid,
        f2,
        deptId,
        getActiveActorEmail(),
      );
      setFiles(state.files);
      const proc = await apiRequest<SessionProcessResult>(
        `/api/m05/sessions/${encodeURIComponent(activeSid)}/process`,
        {
          method: "POST",
          actorEmail: getActiveActorEmail(),
          body: { action: "doi_chieu", department_id: deptId },
        },
      );
      setActiveAction("doi_chieu");
      setResult(proc);
      setBanner({
        tone: "info",
        text: "Đã nạp bộ 02 tệp hồ sơ mẫu và chạy đối chiếu phát hiện chênh lệch số liệu.",
      });
    } catch (err) {
      setBanner({
        tone: "error",
        text: err instanceof Error ? err.message : "Lỗi nạp hồ sơ mẫu",
      });
    } finally {
      setBusy(false);
    }
  }

  async function handleRunProcess(action: SessionProcessAction) {
    setActiveAction(action);
    setBusy(true);
    setBanner(null);
    const activeSid = sessionId || getOrInitSessionId();
    try {
      const proc = await apiRequest<SessionProcessResult>(
        `/api/m05/sessions/${encodeURIComponent(activeSid)}/process`,
        {
          method: "POST",
          actorEmail: getActiveActorEmail(),
          body: { action, department_id: deptId },
        },
      );
      setResult(proc);
    } catch (err) {
      setBanner({
        tone: "error",
        text: err instanceof Error ? err.message : "Lỗi xử lý tài liệu",
      });
    } finally {
      setBusy(false);
    }
  }

  async function handleWipe() {
    const activeSid = sessionId || getOrInitSessionId();
    setBusy(true);
    try {
      await apiRequest(
        `/api/sessions/${encodeURIComponent(activeSid)}?department_id=${encodeURIComponent(deptId)}&module_code=M05`,
        {
          method: "DELETE",
          actorEmail: getActiveActorEmail(),
        },
      );
      const nextSid = rotateSessionId();
      setSessionId(nextSid);
      setFiles([]);
      setResult(null);
      setBanner({
        tone: "info",
        text: "Đã kết thúc phiên và xóa sạch 100% dữ liệu tài liệu tạm trên bộ nhớ RAM.",
      });
    } catch (err) {
      setBanner({
        tone: "error",
        text: err instanceof Error ? err.message : "Không thể xóa bộ nhớ phiên",
      });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <input
        ref={inputRef}
        type="file"
        multiple
        accept=".txt,.md,.csv,.json,.docx,.pdf"
        className="hidden"
        onChange={handleFilesChosen}
      />

      <Alert className="border-blue-200 bg-blue-50/80 text-blue-950">
        <ShieldAlert className="h-4 w-4 text-blue-600" />
        <AlertTitle className="text-sm font-bold flex items-center justify-between gap-2 flex-wrap">
          <span>
            Cam kết bảo mật tài liệu phiên hiện tại ({files.length} tệp đang mở)
          </span>
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={busy}
            onClick={() => void handleWipe()}
            className="h-7 text-xs border-rose-200 bg-rose-50 text-rose-600 hover:bg-rose-100"
          >
            <Trash2 className="h-3.5 w-3.5 mr-1" />
            Kết thúc phiên - Xóa bộ nhớ
          </Button>
        </AlertTitle>
        <AlertDescription className="text-xs text-blue-900/90">
          Hỗ trợ <code>.txt</code>, <code>.md</code>, <code>.csv</code>,{" "}
          <code>.json</code>, <code>.docx</code>, <code>.pdf</code> (tối đa 10 MB/tệp).
          Tài liệu chỉ tồn tại trên RAM trong phiên làm việc và tự động chia sẻ sang
          Mô-đun 01 để hỏi đáp.
        </AlertDescription>
      </Alert>

      {banner && (
        <Alert
          variant={banner.tone === "error" ? "destructive" : "default"}
          className={
            banner.tone === "info"
              ? "border-emerald-200 bg-emerald-50 text-emerald-900 py-2.5"
              : "py-2.5"
          }
        >
          <AlertDescription className="text-xs">{banner.text}</AlertDescription>
        </Alert>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        {/* Left Column: Upload & Session Files List */}
        <Card className="lg:col-span-5 border-slate-200 shadow-xs h-fit">
          <CardHeader className="pb-3">
            <CardTitle className="text-base">
              Danh sách tệp hồ sơ trong phiên
            </CardTitle>
            <CardDescription className="text-xs">
              Tải lên các tài liệu cần đọc, trích xuất hoặc đối chiếu chéo.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                disabled={busy}
                onClick={() => inputRef.current?.click()}
                className="bg-blue-600 hover:bg-blue-700 text-white gap-1.5 text-xs flex-1"
              >
                <Upload className="h-3.5 w-3.5" />
                Chọn tệp tải lên
              </Button>
              <Button
                type="button"
                variant="outline"
                disabled={busy}
                onClick={() => void handleLoadSampleDossier()}
                className="gap-1.5 text-xs"
              >
                <FlaskConical className="h-3.5 w-3.5" />
                Nạp 02 tệp hồ sơ mẫu
              </Button>
            </div>

            {files.length === 0 ? (
              <div className="rounded-xl border border-dashed border-slate-200 p-6 text-center text-xs text-slate-500">
                Chưa có tệp nào trong phiên. Nhấn <strong>Chọn tệp tải lên</strong>{" "}
                hoặc <strong>Nạp 02 tệp hồ sơ mẫu</strong> để thử nghiệm ngay.
              </div>
            ) : (
              <div className="space-y-2">
                {files.map((f) => (
                  <div
                    key={f.file_id}
                    className="rounded-lg border border-slate-200 bg-slate-50/70 p-3 text-xs space-y-1"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-semibold text-slate-900 flex items-center gap-1.5 truncate">
                        <FileText className="h-3.5 w-3.5 text-blue-600 shrink-0" />
                        {f.filename}
                      </span>
                      <Badge variant="secondary" className="text-[10px] shrink-0">
                        {Math.max(1, Math.round(f.size_bytes / 1024))} KB
                      </Badge>
                    </div>
                    <p className="text-[11px] text-emerald-700">{f.parse_note}</p>
                    <p className="text-slate-600 line-clamp-2">
                      {f.extracted_text}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Right Column: 4 Processing Operations */}
        <Card className="lg:col-span-7 border-slate-200 shadow-xs">
          <CardHeader className="pb-3">
            <CardTitle className="text-base">
              Xử lý nghiệp vụ trên tài liệu phiên ({deptId})
            </CardTitle>
            <CardDescription className="text-xs">
              Chọn một trong 04 chế độ xử lý hồ sơ chuyên biệt bên dưới:
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              {SESSION_PROCESS_TABS.map((tab) => (
                <Button
                  key={tab.id}
                  type="button"
                  variant={activeAction === tab.id ? "default" : "outline"}
                  size="sm"
                  disabled={busy}
                  onClick={() => void handleRunProcess(tab.id)}
                  className={
                    activeAction === tab.id
                      ? "bg-blue-600 hover:bg-blue-700 text-white text-xs"
                      : "text-xs"
                  }
                >
                  <Sparkles className="h-3 w-3 mr-1" />
                  {tab.label}
                </Button>
              ))}
            </div>

            {!result ? (
              <div className="rounded-xl border border-dashed border-slate-200 p-8 text-center text-xs text-slate-500 space-y-2">
                <FileSpreadsheet className="h-8 w-8 mx-auto text-slate-400" />
                <p>
                  Chọn một tác vụ xử lý ở trên để AI đọc, trích xuất thông tin hoặc
                  đối chiếu mâu thuẫn giữa các tài liệu trong phiên.
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                {result.highlights.length > 0 && result.action === "doi_chieu" && (
                  <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 space-y-1.5">
                    <p className="text-xs font-bold text-amber-900 flex items-center gap-1.5">
                      <AlertTriangle className="h-4 w-4 text-amber-600" />
                      Điểm cần kiểm tra lại trong hồ sơ:
                    </p>
                    {result.highlights.map((h) => (
                      <p key={h} className="text-xs text-amber-900 pl-5">
                        • {h}
                      </p>
                    ))}
                  </div>
                )}

                <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 text-slate-800">
                  <FormattedMarkdown content={result.result_markdown} />
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
