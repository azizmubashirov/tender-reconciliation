import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Link, Route, Routes } from "react-router";
import "./index.css";
import { ProjectPage } from "./pages/Project";
import { ProjectsPage } from "./pages/Projects";

const queryClient = new QueryClient({ defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } } });

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <header className="border-b border-stone-200 bg-white">
          <div className="mx-auto flex max-w-7xl items-center gap-3 px-6 py-3">
            <Link to="/" className="text-lg font-bold tracking-tight">
              Тендер-Сверка
            </Link>
            <span className="text-sm text-stone-500">сверка заявки с требованиями тендера</span>
          </div>
        </header>
        <main className="mx-auto max-w-7xl px-6 py-6">
          <Routes>
            <Route path="/" element={<ProjectsPage />} />
            <Route path="/projects/:id/:tab?" element={<ProjectPage />} />
          </Routes>
        </main>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);
