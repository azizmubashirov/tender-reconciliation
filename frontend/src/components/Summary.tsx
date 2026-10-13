import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type Project, type Recommendation, type Run } from "../api";
import { ACTION_TYPE, CATEGORY, pct, pointsText, SEVERITY, STATUS, VERDICT } from "../labels";
import { useSelectedRun } from "../useSelectedRun";
import { RunPicker, RunState } from "./Compare";
import { Alert, Button, Card, Kpi } from "./ui";

export function Summary({ project }: { project: Project }) {
  const [run, selectRun] = useSelectedRun(project);
  const queryClient = useQueryClient();
  const done = run?.status === "done";
  const full = useQuery({ queryKey: ["run", run?.id, run?.score.total], queryFn: () => api.get<Run>(`/runs/${run!.id}`), enabled: done });
  const recs = useQuery({
    queryKey: ["recs", run?.id],
    queryFn: () => api.get<Recommendation[]>(`/runs/${run!.id}/recommendations`),
    enabled: done,
  });
  const toggle = useMutation({
    mutationFn: (r: Recommendation) => api.patch(`/recommendations/${r.id}`, { done: !r.done }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["recs", run?.id] }),
  });

  if (!run) return <Alert kind="info">Проверок пока нет.</Alert>;
  if (!done)
    return (
      <div className="space-y-3">
        <RunPicker project={project} run={run} onSelect={selectRun} />
        <RunState run={run} />
      </div>
    );

  const s = run.score;
  const verdict = s.verdict ? VERDICT[s.verdict] : null;
  const history = project.runs.filter((r) => r.status === "done");

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-2">
        <RunPicker project={project} run={run} onSelect={selectRun} />
        <div className="ml-auto flex gap-2">
          <a href={`/api/v1/runs/${run.id}/report.pdf`}>
            <Button>Скачать PDF</Button>
          </a>
          <a href={`/api/v1/runs/${run.id}/report.xlsx`}>
            <Button variant="secondary">Скачать Excel</Button>
          </a>
        </div>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <Kpi label="Вердикт" value={verdict?.label ?? "—"} className={`lg:col-span-2 ${verdict?.cls ?? ""}`} hint={`если выполнить рекомендации: ${pct(s.forecast)}`} />
        <Kpi label="Соответствие" value={pct(s.total)} className="border-blue-300 bg-blue-50" />
        <Kpi label="Товар / Участник" value={`${pct(s.product)} / ${pct(s.participant)}`} />
        <Kpi label="Обязательные" value={`${s.mandatory_done} из ${s.mandatory_total}`} />
      </div>

      {s.points && s.points.pass !== null && (
        <Alert kind={s.points.passed === false ? "error" : s.points.passed ? "success" : "info"}>
          Баллы квалификационной оценки: <b>{pointsText(s.points)}</b>, проходной балл — <b>{s.points.pass}</b>.{" "}
          {s.points.passed === false
            ? `Заявка не набирает проходной балл${s.points_forecast != null ? ` (даже после рекомендаций — не более ${s.points_forecast})` : ""}.`
            : s.points.passed
              ? "Проходной балл набран."
              : "Итог зависит от пунктов на проверке."}
        </Alert>
      )}

      <div className="grid gap-5 lg:grid-cols-3">
        <Card title="По категориям">
          <div className="space-y-2.5">
            {Object.entries(s.categories ?? {}).map(([k, v]) => (
              <div key={k}>
                <div className="flex justify-between text-sm">
                  <span>{CATEGORY[k as keyof typeof CATEGORY] ?? k}</span>
                  <span className="font-medium">{pct(v)}</span>
                </div>
                <div className="mt-1 h-2 rounded bg-stone-100">
                  <div className="h-2 rounded bg-blue-500" style={{ width: `${v ?? 0}%` }} />
                </div>
              </div>
            ))}
          </div>
          <div className="mt-4 flex flex-wrap gap-x-4 gap-y-1 text-xs text-stone-600">
            {Object.entries(s.counts ?? {}).map(([k, v]) => (
              <span key={k}>
                {STATUS[k as keyof typeof STATUS]?.label ?? k}: <b>{v}</b>
              </span>
            ))}
          </div>
        </Card>
        <Card title="Аналитический вывод" className="lg:col-span-2">
          {!!s.warnings?.length && (
            <ul className="mb-3 list-disc space-y-0.5 pl-5 text-sm text-orange-800">
              {s.warnings.map((w) => (
                <li key={w}>{w}</li>
              ))}
            </ul>
          )}
          <div className="whitespace-pre-wrap text-sm leading-relaxed">{full.data?.summary ?? "…"}</div>
        </Card>
      </div>

      <Card title={`План действий (${recs.data?.length ?? 0})`}>
        <table className="w-full text-sm">
          <thead className="text-left text-xs text-stone-500">
            <tr>
              <th className="w-8" />
              <th>ID</th>
              <th>Что не так</th>
              <th>Действие</th>
              <th>Критичность</th>
              <th className="text-right">Влияние</th>
            </tr>
          </thead>
          <tbody>
            {recs.data?.map((r) => (
              <tr key={r.id} className={`border-t border-stone-100 align-top ${r.done ? "text-stone-400 line-through" : ""}`}>
                <td className="py-2">
                  <input type="checkbox" checked={r.done} onChange={() => toggle.mutate(r)} />
                </td>
                <td className="whitespace-nowrap py-2 pr-3 font-mono text-xs font-semibold">{r.code}</td>
                <td className="py-2 pr-3">
                  <div className="font-medium">{r.parameter}</div>
                  <div className="text-stone-600">{r.problem}</div>
                </td>
                <td className="py-2 pr-3">
                  {r.action}
                  <div className="text-xs text-stone-500">{ACTION_TYPE[r.action_type] ?? r.action_type}</div>
                </td>
                <td className={`py-2 pr-3 ${SEVERITY[r.severity].cls}`}>{SEVERITY[r.severity].label}</td>
                <td className="py-2 text-right font-semibold">+{r.impact}%</td>
              </tr>
            ))}
          </tbody>
        </table>
        {recs.data?.length === 0 && <div className="text-sm text-stone-500">Проблем не найдено.</div>}
      </Card>

      {history.length > 1 && (
        <Card title="История проверок">
          <div className="flex flex-wrap items-center gap-2 text-sm">
            {history.map((r, i) => (
              <span key={r.id} className="flex items-center gap-2">
                {i > 0 && <span className="text-stone-400">→</span>}
                <button onClick={() => selectRun(r.id)} className={`rounded px-2 py-1 ${r.id === run.id ? "bg-blue-100 font-semibold" : "bg-stone-100"}`}>
                  {pct(r.score.total)}
                </button>
              </span>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}
