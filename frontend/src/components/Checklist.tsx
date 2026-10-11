import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, type Issue, type Project, type Requirement } from "../api";
import { CATEGORY, condition, ISSUE_KIND, OPERATOR, REQ_TYPE, SCOPE } from "../labels";
import { Alert, Button, Card, SourceLink, Spinner } from "./ui";

type Draft = Pick<
  Requirement,
  "scope" | "category" | "lot_position" | "parameter" | "operator" | "value" | "unit" | "req_type" | "note"
>;

const EMPTY: Draft = {
  scope: "product",
  category: "technical",
  lot_position: null,
  parameter: "",
  operator: "text",
  value: "",
  unit: "",
  req_type: "mandatory",
  note: null,
};

export function Checklist({ project }: { project: Project }) {
  const queryClient = useQueryClient();
  const key = ["requirements", project.id, project.status, project.checklist_approved];
  const reqs = useQuery({ queryKey: key, queryFn: () => api.get<Requirement[]>(`/projects/${project.id}/requirements`) });
  const issues = useQuery({ queryKey: ["issues", project.id, project.status], queryFn: () => api.get<Issue[]>(`/projects/${project.id}/issues`) });
  const [scope, setScope] = useState<"all" | "product" | "participant">("all");
  const [editing, setEditing] = useState<Requirement | "new" | null>(null);

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["requirements", project.id] });
    queryClient.invalidateQueries({ queryKey: ["project", String(project.id)] });
  };
  const approve = useMutation({
    mutationFn: () => api.post(`/projects/${project.id}/checklist/${project.checklist_approved ? "reopen" : "approve"}`),
    onSuccess: refresh,
  });
  const remove = useMutation({ mutationFn: (id: number) => api.del(`/requirements/${id}`), onSuccess: refresh });

  if (project.status === "extracting") return <Spinner label="Извлекаем требования из документации заказчика…" />;
  if (project.status === "failed") return <Alert>Ошибка извлечения: {project.error}</Alert>;
  if (project.status === "new" && !reqs.data?.length)
    return <Alert kind="info">Загрузите документацию заказчика на вкладке «Документы» и нажмите «Извлечь требования».</Alert>;

  const all = reqs.data ?? [];
  const rows = all.filter((r) => scope === "all" || r.scope === scope);
  const mandatory = all.filter((r) => r.req_type === "mandatory").length;
  const locked = project.checklist_approved;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-2">
        {(["all", "product", "participant"] as const).map((s) => (
          <button
            key={s}
            onClick={() => setScope(s)}
            className={`rounded-full px-3 py-1 text-sm ring-1 ${scope === s ? "bg-blue-50 font-medium text-blue-800 ring-blue-400" : "ring-stone-300"}`}
          >
            {s === "all" ? `Все (${all.length})` : `${SCOPE[s]} (${all.filter((r) => r.scope === s).length})`}
          </button>
        ))}
        <span className="ml-2 text-sm text-stone-500">обязательных: {mandatory}</span>
        <div className="ml-auto flex gap-2">
          {!locked && (
            <Button variant="secondary" onClick={() => setEditing("new")}>
              + Добавить требование
            </Button>
          )}
          <Button variant={locked ? "secondary" : "primary"} onClick={() => approve.mutate()} disabled={!all.length || approve.isPending}>
            {locked ? "Открыть для редактирования" : "Утвердить чек-лист"}
          </Button>
        </div>
      </div>
      {locked && <Alert kind="success">Чек-лист утверждён. Можно запускать проверку заявки на вкладке «Документы».</Alert>}
      {approve.error && <Alert>{approve.error.message}</Alert>}

      <Card className="overflow-x-auto p-0">
        <table className="w-full text-sm">
          <thead className="bg-stone-50 text-left text-xs text-stone-500">
            <tr>
              <th className="px-3 py-2">ID</th>
              <th>Требование</th>
              <th>Тип</th>
              <th>Категория</th>
              <th>Поз.</th>
              <th>Подтверждение</th>
              <th>Источник</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id} className="border-t border-stone-100 align-top">
                <td className="whitespace-nowrap px-3 py-2 font-mono text-xs font-semibold">{r.code}</td>
                <td className="py-2 pr-3">
                  {condition(r)}
                  {r.note && <div className="mt-0.5 text-xs text-orange-700">{r.note}</div>}
                  {r.origin === "user" && <span className="ml-1 text-xs text-stone-400">(вручную)</span>}
                </td>
                <td className="whitespace-nowrap pr-3">
                  <span className={r.req_type === "mandatory" ? "font-medium text-red-700" : "text-stone-600"}>{REQ_TYPE[r.req_type]}</span>
                  {r.rated_points ? <span className="text-xs text-stone-500"> · {r.rated_points} б.</span> : null}
                </td>
                <td className="pr-3 text-stone-600">{CATEGORY[r.category]}</td>
                <td className="pr-3 text-stone-600">{r.lot_position ?? "—"}</td>
                <td className="max-w-40 pr-3 text-xs text-stone-600">{r.proof_documents.join(", ") || "—"}</td>
                <td className="max-w-56 pr-3 text-xs">
                  {r.sources.slice(0, 2).map((s, i) => (
                    <div key={i}>
                      <SourceLink source={s} />
                    </div>
                  ))}
                </td>
                <td className="whitespace-nowrap pr-3 text-right">
                  {!locked && (
                    <>
                      <button onClick={() => setEditing(r)} className="mr-2 text-stone-500 hover:text-blue-700" title="Изменить">
                        ✎
                      </button>
                      <button onClick={() => remove.mutate(r.id)} className="text-stone-400 hover:text-red-600" title="Удалить">
                        ✕
                      </button>
                    </>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>

      {!!issues.data?.length && (
        <Card title="Вопросы к заказчику">
          <ul className="space-y-2 text-sm">
            {issues.data.map((i) => (
              <li key={i.id} className="rounded-lg bg-stone-50 p-3">
                <span className="mr-2 rounded bg-orange-100 px-2 py-0.5 text-xs text-orange-800">{ISSUE_KIND[i.kind]}</span>
                {i.description}
                <div className="mt-1 text-xs">
                  {i.sources.map((s, n) => (
                    <span key={n} className="mr-3">
                      <SourceLink source={s} />
                    </span>
                  ))}
                </div>
              </li>
            ))}
          </ul>
        </Card>
      )}

      {editing && (
        <RequirementForm
          projectId={project.id}
          initial={editing === "new" ? null : editing}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            refresh();
          }}
        />
      )}
    </div>
  );
}

function RequirementForm({
  projectId,
  initial,
  onClose,
  onSaved,
}: {
  projectId: number;
  initial: Requirement | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [draft, setDraft] = useState<Draft>(initial ?? EMPTY);
  const save = useMutation({
    mutationFn: () => {
      const body = { ...draft, value: draft.value || null, unit: draft.unit || null };
      return initial ? api.patch(`/requirements/${initial.id}`, body) : api.post(`/projects/${projectId}/requirements`, body);
    },
    onSuccess: onSaved,
  });
  const set = <K extends keyof Draft>(k: K, v: Draft[K]) => setDraft((d) => ({ ...d, [k]: v }));
  const field = "w-full rounded-lg border border-stone-300 px-3 py-2 text-sm";

  return (
    <div className="fixed inset-0 z-10 flex items-center justify-center bg-black/30 p-4" onClick={onClose}>
      <div className="w-full max-w-xl rounded-xl bg-white p-5 shadow-xl" onClick={(e) => e.stopPropagation()}>
        <h3 className="mb-4 text-lg font-semibold">{initial ? `Изменить ${initial.code}` : "Новое требование"}</h3>
        <div className="grid grid-cols-2 gap-3 text-sm">
          <label className="col-span-2">
            Параметр
            <input className={field} value={draft.parameter} onChange={(e) => set("parameter", e.target.value)} />
          </label>
          <label>
            Условие
            <select className={field} value={draft.operator} onChange={(e) => set("operator", e.target.value)}>
              {Object.entries(OPERATOR).map(([k, v]) => (
                <option key={k} value={k}>
                  {v || "текстовое"}
                </option>
              ))}
            </select>
          </label>
          <div className="grid grid-cols-2 gap-2">
            <label>
              Значение
              <input className={field} value={draft.value ?? ""} onChange={(e) => set("value", e.target.value)} />
            </label>
            <label>
              Ед.
              <input className={field} value={draft.unit ?? ""} onChange={(e) => set("unit", e.target.value)} />
            </label>
          </div>
          <label>
            Относится к
            <select className={field} value={draft.scope} onChange={(e) => set("scope", e.target.value as Draft["scope"])}>
              {Object.entries(SCOPE).map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
            </select>
          </label>
          <label>
            Тип
            <select className={field} value={draft.req_type} onChange={(e) => set("req_type", e.target.value as Draft["req_type"])}>
              {Object.entries(REQ_TYPE).map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
            </select>
          </label>
          <label>
            Категория
            <select className={field} value={draft.category} onChange={(e) => set("category", e.target.value as Draft["category"])}>
              {Object.entries(CATEGORY).map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
            </select>
          </label>
          <label>
            Позиция лота
            <input
              className={field}
              type="number"
              value={draft.lot_position ?? ""}
              onChange={(e) => set("lot_position", e.target.value ? Number(e.target.value) : null)}
            />
          </label>
        </div>
        {save.error && <div className="mt-3"><Alert>{save.error.message}</Alert></div>}
        <div className="mt-5 flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>
            Отмена
          </Button>
          <Button onClick={() => save.mutate()} disabled={!draft.parameter.trim() || save.isPending}>
            Сохранить
          </Button>
        </div>
      </div>
    </div>
  );
}
