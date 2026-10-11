import type { Status } from "./api";

export const STATUS: Record<Status, { label: string; cls: string }> = {
  match: { label: "Соответствует", cls: "bg-green-100 text-green-800 ring-green-300" },
  partial: { label: "Частично", cls: "bg-yellow-100 text-yellow-800 ring-yellow-300" },
  unconfirmed: { label: "Не подтверждено", cls: "bg-orange-100 text-orange-800 ring-orange-300" },
  mismatch: { label: "Не соответствует", cls: "bg-red-100 text-red-800 ring-red-300" },
  review: { label: "Требует проверки", cls: "bg-stone-200 text-stone-700 ring-stone-300" },
};

export const VERDICT = {
  ready: { label: "Готова к подаче", cls: "border-green-400 bg-green-50 text-green-900" },
  needs_work: { label: "Требует доработки", cls: "border-yellow-400 bg-yellow-50 text-yellow-900" },
  rejection_risk: { label: "Риск отклонения", cls: "border-red-400 bg-red-50 text-red-900" },
} as const;

export const REQ_TYPE = { mandatory: "Обязательное", rated: "Оценочное", desired: "Желательное" };
export const SCOPE = { product: "Товар", participant: "Участник" };
export const CATEGORY = {
  technical: "Тех. характеристики",
  documents: "Документы",
  qualification: "Квалификация",
  commercial: "Коммерческие условия",
};
export const OPERATOR: Record<string, string> = {
  gte: "≥",
  lte: "≤",
  eq: "=",
  range_within: "в диапазоне",
  range_covers: "покрывает",
  exists: "наличие",
  text: "",
};
export const ACTION_TYPE: Record<string, string> = {
  add_document: "Добавить документ",
  fix_data: "Исправить данные",
  replace_product: "Заменить товар",
  request_clarification: "Запросить разъяснение",
  unfixable: "Неустранимо",
};
export const SEVERITY = {
  high: { label: "Высокая", cls: "text-red-700" },
  medium: { label: "Средняя", cls: "text-yellow-700" },
  low: { label: "Низкая", cls: "text-stone-500" },
};
export const ISSUE_KIND = {
  contradiction: "Противоречие",
  ambiguity: "Неоднозначность",
  restrictive: "Ограничение конкуренции",
};
export const DOC_TYPE: Record<string, string> = {
  tender_documentation: "Тендерная документация",
  technical_specification: "Техническое задание",
  specification: "Спецификация",
  qualification_requirements: "Квалификационные требования",
  evaluation_criteria: "Критерии оценки",
  draft_contract: "Проект договора",
  forms: "Формы",
  clarification: "Разъяснение",
  tech_proposal: "Техническое предложение",
  commercial_proposal: "Коммерческое предложение",
  product_passport: "Паспорт товара",
  manufacturer_catalog: "Каталог производителя",
  certificate: "Сертификат",
  declaration: "Декларация",
  license: "Лицензия",
  reference_letter: "Справка",
  power_of_attorney: "Доверенность",
  authorization_letter: "Авторизационное письмо",
  experience_contract: "Договор (опыт)",
  acceptance_act: "Акт выполнения",
  financial_statement: "Финансовая отчётность",
  company_registration: "Свидетельство о регистрации",
  bank_guarantee: "Банковская гарантия",
  drawing: "Чертёж",
  marketing: "Маркетинговый материал",
  other: "Прочее",
};
export const RUN_STAGE: Record<string, string> = {
  facts: "Извлечение фактов из заявки",
  match: "Сопоставление требований",
  report: "Расчёт и рекомендации",
};

export function condition(r: { parameter: string; operator: string; value: string | null; unit: string | null }) {
  const op = OPERATOR[r.operator] ?? "";
  return [r.parameter, r.value ? `${op} ${r.value} ${r.unit ?? ""}` : op && `(${op})`]
    .filter(Boolean)
    .join(" ")
    .trim();
}

export const pct = (v: number | null | undefined) => (v === null || v === undefined ? "—" : `${Math.round(v)}%`);
