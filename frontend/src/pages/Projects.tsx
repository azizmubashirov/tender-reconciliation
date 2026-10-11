import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate } from "react-router";
import { api, type Project, type ProjectListItem } from "../api";
import { Alert, Button, Card } from "../components/ui";
import { pct, VERDICT } from "../labels";

export function ProjectsPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const projects = useQuery({ queryKey: ["projects"], queryFn: () => api.get<ProjectListItem[]>("/projects") });
  const [title, setTitle] = useState("");
  const [language, setLanguage] = useState("ru");

  const create = useMutation({
    mutationFn: () => api.post<Project>("/projects", { title, report_language: language }),
    onSuccess: (project) => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      navigate(`/projects/${project.id}`);
    },
  });

  return (
    <div className="space-y-6">
      <Card title="Новая проверка">
        <form
          className="flex flex-wrap items-end gap-3"
          onSubmit={(e) => {
            e.preventDefault();
            if (title.trim()) create.mutate();
          }}
        >
          <label className="flex-1 text-sm">
            <span className="mb-1 block text-stone-600">Название лота</span>
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Например: Поставка ноутбуков, лот 2026-114"
              className="w-full rounded-lg border border-stone-300 px-3 py-2"
            />
          </label>
          <label className="text-sm">
            <span className="mb-1 block text-stone-600">Язык отчёта</span>
            <select value={language} onChange={(e) => setLanguage(e.target.value)} className="rounded-lg border border-stone-300 px-3 py-2">
              <option value="ru">Русский</option>
              <option value="uz">O'zbekcha</option>
              <option value="en">English</option>
            </select>
          </label>
          <Button type="submit" disabled={!title.trim() || create.isPending}>
            Создать
          </Button>
        </form>
        {create.error && <div className="mt-3"><Alert>{create.error.message}</Alert></div>}
      </Card>

      <Card title="Проекты">
        {projects.isLoading && <div className="text-sm text-stone-500">Загрузка…</div>}
        {projects.error && <Alert>{projects.error.message}</Alert>}
        {projects.data?.length === 0 && <div className="text-sm text-stone-500">Пока нет проверок.</div>}
        {!!projects.data?.length && (
          <table className="w-full text-sm">
            <thead className="text-left text-stone-500">
              <tr>
                <th className="py-2">Лот</th>
                <th>Заказчик</th>
                <th>Подача до</th>
                <th>Чек-лист</th>
                <th>Соответствие</th>
                <th>Вердикт</th>
              </tr>
            </thead>
            <tbody>
              {projects.data.map((p) => (
                <tr key={p.id} className="border-t border-stone-100 hover:bg-stone-50">
                  <td className="py-2.5">
                    <Link to={`/projects/${p.id}`} className="font-medium text-blue-700 hover:underline">
                      {p.title}
                    </Link>
                    {p.lot_number && <span className="ml-2 text-stone-500">№ {p.lot_number}</span>}
                  </td>
                  <td>{p.customer_name ?? "—"}</td>
                  <td>{p.submission_deadline ? new Date(p.submission_deadline).toLocaleDateString("ru-RU") : "—"}</td>
                  <td>{p.checklist_approved ? "утверждён" : p.status === "extracting" ? "извлекается…" : "черновик"}</td>
                  <td className="font-semibold">{pct(p.score)}</td>
                  <td>{p.verdict ? <span className={`rounded px-2 py-0.5 text-xs ${VERDICT[p.verdict].cls}`}>{VERDICT[p.verdict].label}</span> : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
}
