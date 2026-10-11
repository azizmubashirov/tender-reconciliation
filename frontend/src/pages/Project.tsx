import { useQuery } from "@tanstack/react-query";
import { NavLink, useParams } from "react-router";
import { api, type Project } from "../api";
import { Checklist } from "../components/Checklist";
import { Compare } from "../components/Compare";
import { Documents } from "../components/Documents";
import { Summary } from "../components/Summary";
import { Alert } from "../components/ui";

const TABS = [
  { key: "documents", label: "1. Документы" },
  { key: "checklist", label: "2. Чек-лист" },
  { key: "compare", label: "3. Сравнение" },
  { key: "summary", label: "4. Сводка" },
] as const;

function isBusy(p: Project) {
  return (
    p.status === "extracting" ||
    p.packages.some((pk) => pk.status === "processing") ||
    p.runs.some((r) => r.status === "queued" || r.status === "running")
  );
}

export function ProjectPage() {
  const { id, tab = "documents" } = useParams();
  const project = useQuery({
    queryKey: ["project", id],
    queryFn: () => api.get<Project>(`/projects/${id}`),
    refetchInterval: (q) => (q.state.data && isBusy(q.state.data) ? 2000 : false),
  });

  if (project.error) return <Alert>{project.error.message}</Alert>;
  if (!project.data) return <div className="text-sm text-stone-500">Загрузка…</div>;
  const p = project.data;

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-bold">{p.title}</h1>
        <div className="mt-1 text-sm text-stone-600">
          {[p.lot_number && `Лот ${p.lot_number}`, p.customer_name, p.submission_deadline && `подача до ${new Date(p.submission_deadline).toLocaleDateString("ru-RU")}`]
            .filter(Boolean)
            .join(" · ") || "Загрузите документацию заказчика"}
        </div>
      </div>
      <nav className="flex gap-1 border-b border-stone-200">
        {TABS.map((t) => (
          <NavLink
            key={t.key}
            to={`/projects/${p.id}/${t.key}`}
            className={() =>
              `-mb-px border-b-2 px-4 py-2 text-sm font-medium ${
                tab === t.key ? "border-blue-600 text-blue-700" : "border-transparent text-stone-600 hover:text-stone-900"
              }`
            }
          >
            {t.label}
          </NavLink>
        ))}
      </nav>
      {tab === "documents" && <Documents project={p} />}
      {tab === "checklist" && <Checklist project={p} />}
      {tab === "compare" && <Compare project={p} />}
      {tab === "summary" && <Summary project={p} />}
    </div>
  );
}
