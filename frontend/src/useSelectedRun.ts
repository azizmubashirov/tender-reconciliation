import { useState } from "react";
import type { Project } from "./api";

/** The run chosen in the run picker, or the latest one. */
export function useSelectedRun(project: Project) {
  const [selected, setSelected] = useState<number | null>(null);
  const run = project.runs.find((r) => r.id === selected) ?? project.runs.at(-1);
  return [run, setSelected] as const;
}
