import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { Link, useNavigate } from "react-router";
import { api, type DocumentInfo, type Package, type Project, type Run } from "../api";
import { DOC_TYPE } from "../labels";
import { Alert, Button, Card, Spinner } from "./ui";

const ACCEPT = ".pdf,.doc,.docx,.rtf,.odt,.xls,.xlsx,.xlsm,.ods,.csv,.txt,.jpg,.jpeg,.png,.tif,.tiff,.bmp,.webp,.heic,.heif,.zip,.rar,.7z";

export function Documents({ project }: { project: Project }) {
  const customer = project.packages.find((p) => p.kind === "customer");
  const bids = project.packages.filter((p) => p.kind === "bid");
  const latestBid = bids.at(-1);
  const queryClient = useQueryClient();
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["project", String(project.id)] });

  const newVersion = useMutation({
    mutationFn: () =>
      api.post<Package>(`/projects/${project.id}/packages`, { kind: "bid", participant_name: latestBid?.participant_name }),
    onSuccess: refresh,
  });

  return (
    <div className="grid gap-5 lg:grid-cols-2">
      <div className="space-y-3">
        <PackageCard project={project} kind="customer" pkg={customer} title="Документация заказчика" />
        {project.status === "extracting" && <Spinner label="Извлекаем требования из документации… Обычно 1–5 минут." />}
        {project.status === "failed" && <Alert>Ошибка извлечения требований: {project.error}</Alert>}
        {project.status === "extracted" && (
          <Alert kind="success">
            Требования извлечены.{" "}
            <Link to={`/projects/${project.id}/checklist`} className="font-medium underline">
              Проверьте и утвердите чек-лист →
            </Link>
          </Alert>
        )}
      </div>
      <div className="space-y-3">
        <PackageCard
          project={project}
          kind="bid"
          pkg={latestBid}
          title={bids.length > 1 ? `Заявка участника (версия ${bids.length})` : "Заявка участника"}
        />
        {latestBid && <RunButton project={project} pkg={latestBid} />}
        {latestBid && latestBid.documents.length > 0 && (
          <Button variant="secondary" onClick={() => newVersion.mutate()} disabled={newVersion.isPending}>
            + Новая версия заявки (повторная проверка)
          </Button>
        )}
      </div>
    </div>
  );
}

function PackageCard({ project, kind, pkg, title }: { project: Project; kind: "customer" | "bid"; pkg?: Package; title: string }) {
  const queryClient = useQueryClient();
  const input = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [participant, setParticipant] = useState(pkg?.participant_name ?? "");
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["project", String(project.id)] });

  const upload = useMutation({
    mutationFn: async (files: File[]) => {
      const target = pkg ?? (await api.post<Package>(`/projects/${project.id}/packages`, { kind, participant_name: participant || null }));
      const form = new FormData();
      files.forEach((f) => form.append("files", f));
      return api.post<Package>(`/packages/${target.id}/files`, form);
    },
    onSuccess: refresh,
  });
  const process = useMutation({ mutationFn: (id: number) => api.post(`/packages/${id}/process`), onSuccess: refresh });
  const remove = useMutation({ mutationFn: (id: number) => api.del(`/documents/${id}`), onSuccess: refresh });

  const locked = kind === "customer" && project.checklist_approved;
  const busy = pkg?.status === "processing" || (kind === "customer" && project.status === "extracting");
  const pending = pkg?.documents.some((d) => d.status === "new");

  return (
    <Card title={title}>
      {kind === "bid" && !pkg && (
        <input
          value={participant}
          onChange={(e) => setParticipant(e.target.value)}
          placeholder="Наименование участника (необязательно)"
          className="mb-3 w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
        />
      )}
      {!locked && (
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragging(false);
            const files = Array.from(e.dataTransfer.files);
            if (files.length) upload.mutate(files);
          }}
          onClick={() => input.current?.click()}
          className={`cursor-pointer rounded-xl border-2 border-dashed px-4 py-8 text-center text-sm transition ${
            dragging ? "border-blue-500 bg-blue-50" : "border-stone-300 hover:border-stone-400"
          }`}
        >
          <div className="font-medium">Перетащите файлы или нажмите для выбора</div>
          <div className="mt-1 text-xs text-stone-500">PDF (текст и сканы), Word, Excel, RTF, ODT, фото, ZIP/RAR/7Z · UZ / RU / EN</div>
          <input
            ref={input}
            type="file"
            multiple
            accept={ACCEPT}
            className="hidden"
            onChange={(e) => {
              const files = Array.from(e.target.files ?? []);
              if (files.length) upload.mutate(files);
              e.target.value = "";
            }}
          />
        </div>
      )}
      {upload.isPending && <div className="mt-3"><Spinner label="Загрузка файлов…" /></div>}
      {upload.error && <div className="mt-3"><Alert>{upload.error.message}</Alert></div>}
      {process.error && <div className="mt-3"><Alert>{process.error.message}</Alert></div>}

      {pkg && pkg.documents.length > 0 && (
        <ul className="mt-4 divide-y divide-stone-100 text-sm">
          {pkg.documents.map((d) => (
            <li key={d.id} className="flex items-center gap-2 py-2">
              <span className="flex-1 truncate" title={d.filename}>
                {d.filename}
              </span>
              <span className="text-xs text-stone-500">
                {d.status === "ready" && (d.doc_type ? DOC_TYPE[d.doc_type] ?? d.doc_type : `${d.page_count} стр.`)}
                {d.status === "ready" && sectionCount(d) > 1 && ` · документов в файле: ${sectionCount(d)}`}
                {d.status === "new" && "ожидает обработки"}
              </span>
              {d.status === "failed" && <span className="text-xs text-red-700" title={d.error ?? ""}>ошибка: {d.error?.slice(0, 60)}</span>}
              {!locked && !busy && (
                <button onClick={() => remove.mutate(d.id)} className="text-stone-400 hover:text-red-600" title="Удалить">
                  ✕
                </button>
              )}
            </li>
          ))}
        </ul>
      )}

      {pkg && pkg.documents.length > 0 && !locked && (
        <div className="mt-4 flex items-center gap-3">
          <Button onClick={() => process.mutate(pkg.id)} disabled={busy || process.isPending || (!pending && kind === "bid")}>
            {kind === "customer" ? "Извлечь требования" : "Подготовить документы"}
          </Button>
          {pkg.status === "processing" && <Spinner label="Обработка документов…" />}
          {pkg.status === "failed" && <span className="text-sm text-red-700">{pkg.error}</span>}
        </div>
      )}
      {locked && <div className="mt-3 text-sm text-stone-600">Чек-лист утверждён: документация заказчика зафиксирована.</div>}
    </Card>
  );
}

function RunButton({ project, pkg }: { project: Project; pkg: Package }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const start = useMutation({
    mutationFn: () => api.post<Run>(`/projects/${project.id}/runs`, { package_id: pkg.id }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["project", String(project.id)] });
      navigate(`/projects/${project.id}/compare`);
    },
  });
  const ready = pkg.status === "ready" && pkg.documents.some((d) => d.status === "ready");
  return (
    <div className="space-y-2">
      {!project.checklist_approved && <Alert kind="info">Чтобы запустить проверку, утвердите чек-лист требований.</Alert>}
      <Button onClick={() => start.mutate()} disabled={!project.checklist_approved || !ready || start.isPending} className="w-full py-3">
        Запустить проверку заявки
      </Button>
      {start.error && <Alert>{start.error.message}</Alert>}
    </div>
  );
}

function sectionCount(d: DocumentInfo): number {
  return Array.isArray(d.info.sections) ? d.info.sections.length : 0;
}
