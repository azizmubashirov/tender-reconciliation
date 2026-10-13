import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, type Match, type Project, type Recommendation, type Run, type Status } from "../api";
import { ACTION_TYPE, condition, OK_STATUSES, pct, pointsText, REQ_TYPE, RUN_STAGE, STATUS, VERDICT } from "../labels";
import { useSelectedRun } from "../useSelectedRun";
import { Alert, Button, Card, Kpi, Quote, Spinner, StatusBadge } from "./ui";

export function RunPicker({ project, run, onSelect }: { project: Project; run: Run; onSelect: (id: number) => void }) {
  if (project.runs.length < 2) return null;
  return (
    <select value={run.id} onChange={(e) => onSelect(Number(e.target.value))} className="rounded-lg border border-stone-300 px-2 py-1.5 text-sm">
      {project.runs.map((r, i) => (
        <option key={r.id} value={r.id}>
          Проверка {i + 1} · {new Date(r.created_at).toLocaleString("ru-RU")} · {r.status === "done" ? pct(r.score.total) : r.status}
        </option>
      ))}
    </select>
  );
}

export function RunState({ run }: { run: Run }) {
  if (run.status === "failed") return <Alert>Проверка завершилась с ошибкой: {run.error}</Alert>;
  return <Spinner label={`Идёт проверка: ${RUN_STAGE[run.stage ?? ""] ?? "в очереди"}… Обычно 2–10 минут.`} />;
}

type Filter = "all" | "problems" | "product" | "participant";

export function Compare({ project }: { project: Project }) {
  const [run, selectRun] = useSelectedRun(project);
  const [filter, setFilter] = useState<Filter>("problems");
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const done = run?.status === "done";
  const matches = useQuery({
    queryKey: ["matches", run?.id],
    queryFn: () => api.get<Match[]>(`/runs/${run!.id}/matches`),
    enabled: done,
  });
  const recs = useQuery({
    queryKey: ["recs", run?.id],
    queryFn: () => api.get<Recommendation[]>(`/runs/${run!.id}/recommendations`),
    enabled: done,
  });

  if (!run) return <Alert kind="info">Проверок пока нет. Загрузите заявку на вкладке «Документы» и запустите проверку.</Alert>;
  if (!done)
    return (
      <div className="space-y-3">
        <RunPicker project={project} run={run} onSelect={selectRun} />
        <RunState run={run} />
      </div>
    );

  const s = run.score;
  const all = matches.data ?? [];
  const isProblem = (m: Match) => !OK_STATUSES.includes(m.status);
  const problems = all.filter(isProblem);
  const rows = all.filter((m) => (filter === "all" ? true : filter === "problems" ? isProblem(m) : m.requirement.scope === filter));
  const selected = all.find((m) => m.id === selectedId) ?? rows[0];
  const verdict = s.verdict ? VERDICT[s.verdict] : null;

  return (
    <div className="space-y-4">
      <RunPicker project={project} run={run} onSelect={selectRun} />
      <div className={`grid gap-3 sm:grid-cols-2 ${s.points ? "lg:grid-cols-5" : "lg:grid-cols-4"}`}>
        <Kpi
          label="Соответствие"
          value={pct(s.total)}
          hint={s.total_min !== s.total_max ? `с учётом пунктов на проверке: ${pct(s.total_min)}–${pct(s.total_max)}` : undefined}
          className="border-blue-300 bg-blue-50"
        />
        <Kpi label="Обязательные" value={`${s.mandatory_done} из ${s.mandatory_total}`} />
        <Kpi label="Проблемные пункты" value={s.problems ?? 0} />
        {s.points && (
          <Kpi
            label="Баллы"
            value={pointsText(s.points)}
            hint={s.points.pass !== null ? `проходной балл: ${s.points.pass}` : undefined}
            className={s.points.passed === false ? "border-red-400 bg-red-50 text-red-900" : undefined}
          />
        )}
        <Kpi label="Вердикт" value={verdict?.label ?? "—"} hint={`если устранить всё: ${pct(s.forecast)}`} className={verdict?.cls} />
      </div>

      <div className="flex flex-wrap gap-2">
        {(
          [
            ["all", `Все (${all.length})`],
            ["problems", `Только проблемы (${problems.length})`],
            ["product", "Товар"],
            ["participant", "Участник"],
          ] as [Filter, string][]
        ).map(([k, label]) => (
          <button
            key={k}
            onClick={() => setFilter(k)}
            className={`rounded-full px-3 py-1 text-sm ring-1 ${filter === k ? "bg-blue-50 font-medium text-blue-800 ring-blue-400" : "ring-stone-300"}`}
          >
            {label}
          </button>
        ))}
        <a href={`/api/v1/runs/${run.id}/report.pdf`} className="ml-auto">
          <Button variant="secondary">Экспорт отчёта (PDF)</Button>
        </a>
      </div>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_420px]">
        <Card className="overflow-x-auto p-0">
          <table className="w-full text-sm">
            <thead className="bg-stone-50 text-left text-xs text-stone-500">
              <tr>
                <th className="px-3 py-2">ID</th>
                <th>Требование</th>
                <th>Заявка</th>
                <th className="pr-3">Статус</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((m) => (
                <tr
                  key={m.id}
                  onClick={() => setSelectedId(m.id)}
                  className={`cursor-pointer border-t border-stone-100 align-top hover:bg-stone-50 ${
                    selected?.id === m.id ? "bg-blue-50/60 shadow-[inset_3px_0_0_#2563eb]" : ""
                  }`}
                >
                  <td className="whitespace-nowrap px-3 py-2 font-mono text-xs font-semibold">{m.requirement.code}</td>
                  <td className="py-2 pr-3">
                    {condition(m.requirement)}
                    <div className="text-xs text-stone-500">{REQ_TYPE[m.requirement.req_type]}</div>
                  </td>
                  <td className="py-2 pr-3 text-stone-700">{m.status === "na" ? "—" : (m.evidence.map((e) => e.value).filter(Boolean)[0] ?? "не найдено")}</td>
                  <td className="py-2 pr-3">
                    <StatusBadge status={m.status} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {!rows.length && <div className="p-6 text-center text-sm text-stone-500">Нет пунктов по фильтру</div>}
        </Card>
        {selected && (
          <MatchPanel key={selected.id} match={selected} run={run} recommendation={recs.data?.find((r) => r.requirement_id === selected.requirement.id)} />
        )}
      </div>
    </div>
  );
}

function MatchPanel({ match, run, recommendation }: { match: Match; run: Run; recommendation?: Recommendation }) {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [status, setStatus] = useState<Status>(match.status);
  const [comment, setComment] = useState("");
  const override = useMutation({
    mutationFn: () => api.patch<Match>(`/matches/${match.id}`, { status, comment }),
    onSuccess: () => {
      setEditing(false);
      queryClient.invalidateQueries({ queryKey: ["matches", run.id] });
      queryClient.invalidateQueries({ queryKey: ["recs", run.id] });
      queryClient.invalidateQueries({ queryKey: ["project"] });
    },
  });
  const tone = match.status === "match" ? "green" : match.status === "mismatch" ? "red" : "blue";

  return (
    <div className="space-y-3">
      <div className="text-xs font-medium uppercase text-stone-500">Документация заказчика</div>
      {match.requirement.sources.map((s, i) => (
        <Quote key={i} source={s} />
      ))}
      <div className="text-xs font-medium uppercase text-stone-500">Заявка</div>
      {match.evidence.length ? (
        match.evidence.map((e, i) => <Quote key={i} source={e} tone={tone} />)
      ) : (
        <div className="rounded-lg border border-dashed border-stone-300 p-3 text-sm text-stone-500">В документах заявки не найдено</div>
      )}
      <Card title="Обоснование и рекомендация" className="p-4">
        <div className="flex items-center gap-2 text-sm">
          <StatusBadge status={match.status} />
          <span className="text-xs text-stone-500">
            {match.method === "rule" ? "сравнение по правилам (код)" : match.method === "manual" ? "изменено вручную" : "оценка AI"}
          </span>
        </div>
        <p className="mt-2 text-sm">{match.reasoning}</p>
        {match.requirement.rated_points !== null && (
          <p className="mt-1 text-xs text-stone-500">
            Баллы: {match.points ?? (match.status === "match" ? match.requirement.rated_points : "—")} из {match.requirement.rated_points}
          </p>
        )}
        {match.comment && <p className="mt-1 text-sm italic text-stone-600">Комментарий: {match.comment}</p>}
        {recommendation && (
          <div className="mt-3 rounded-lg bg-stone-50 p-3 text-sm">
            <div className="font-semibold">{recommendation.action}</div>
            <div className="mt-1 text-xs text-stone-500">
              {ACTION_TYPE[recommendation.action_type] ?? recommendation.action_type} · влияние +{recommendation.impact}%
            </div>
          </div>
        )}
      </Card>
      {!editing ? (
        <Button variant="secondary" onClick={() => setEditing(true)}>
          Изменить статус
        </Button>
      ) : (
        <div className="space-y-2 rounded-xl border border-stone-200 bg-white p-3">
          <select value={status} onChange={(e) => setStatus(e.target.value as Status)} className="w-full rounded-lg border border-stone-300 px-2 py-2 text-sm">
            {Object.entries(STATUS).map(([k, v]) => (
              <option key={k} value={k}>
                {v.label}
              </option>
            ))}
          </select>
          <textarea
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder="Комментарий (обязательно)"
            className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
          />
          {override.error && <Alert>{override.error.message}</Alert>}
          <div className="flex gap-2">
            <Button onClick={() => override.mutate()} disabled={!comment.trim() || override.isPending}>
              Сохранить
            </Button>
            <Button variant="secondary" onClick={() => setEditing(false)}>
              Отмена
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
