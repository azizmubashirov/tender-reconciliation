import type { ButtonHTMLAttributes, ReactNode } from "react";
import type { Source, Status } from "../api";
import { documentUrl } from "../api";
import { STATUS } from "../labels";

export function Button({
  variant = "primary",
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" | "danger" }) {
  const styles = {
    primary: "bg-blue-600 text-white hover:bg-blue-700 disabled:bg-blue-300",
    secondary: "bg-white text-stone-800 ring-1 ring-stone-300 hover:bg-stone-100 disabled:text-stone-400",
    danger: "bg-white text-red-700 ring-1 ring-red-300 hover:bg-red-50",
  };
  return (
    <button
      className={`rounded-lg px-3.5 py-2 text-sm font-medium transition disabled:cursor-not-allowed ${styles[variant]} ${className}`}
      {...props}
    />
  );
}

export function StatusBadge({ status }: { status: Status }) {
  const s = STATUS[status];
  return (
    <span className={`inline-block whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ${s.cls}`}>
      {s.label}
    </span>
  );
}

export function Card({ title, children, className = "" }: { title?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`rounded-xl border border-stone-200 bg-white p-5 ${className}`}>
      {title && <h2 className="mb-3 text-base font-semibold">{title}</h2>}
      {children}
    </section>
  );
}

export function Kpi({ label, value, hint, className = "" }: { label: string; value: ReactNode; hint?: ReactNode; className?: string }) {
  return (
    <div className={`rounded-xl border-2 border-stone-200 bg-white px-4 py-3 ${className}`}>
      <div className="text-sm opacity-75">{label}</div>
      <div className="mt-1 text-2xl font-bold">{value}</div>
      {hint && <div className="mt-0.5 text-xs opacity-70">{hint}</div>}
    </div>
  );
}

export function Spinner({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-2 text-sm text-blue-800">
      <span className="size-4 animate-spin rounded-full border-2 border-blue-300 border-t-blue-700" />
      {label}
    </div>
  );
}

export function Alert({ kind = "error", children }: { kind?: "error" | "info" | "success"; children: ReactNode }) {
  const cls = {
    error: "border-red-200 bg-red-50 text-red-800",
    info: "border-blue-200 bg-blue-50 text-blue-900",
    success: "border-green-200 bg-green-50 text-green-900",
  };
  return <div className={`rounded-lg border px-4 py-3 text-sm ${cls[kind]}`}>{children}</div>;
}

export function SourceLink({ source }: { source: Source }) {
  return (
    <a
      href={documentUrl(source)}
      target="_blank"
      rel="noreferrer"
      className="text-blue-700 hover:underline"
      title={source.quote ?? undefined}
    >
      {source.filename}
      {source.page ? `, стр. ${source.page}` : ""}
      {source.verified === false && <span className="ml-1 text-orange-600" title="Цитата не найдена в тексте документа">⚠</span>}
    </a>
  );
}

export function Quote({ source, tone = "blue" }: { source: Source & { value?: string }; tone?: "blue" | "red" | "green" }) {
  const tones = { blue: "bg-blue-50 border-blue-200", red: "bg-red-50 border-red-200", green: "bg-green-50 border-green-200" };
  return (
    <div className={`rounded-lg border p-3 text-sm ${tones[tone]}`}>
      <div className="mb-1 text-xs text-stone-600">
        <SourceLink source={source} />
        {source.value && <span className="ml-2 font-medium text-stone-800">→ {source.value}</span>}
      </div>
      {source.quote && <div className="italic">«{source.quote}»</div>}
    </div>
  );
}
