import type { ReactNode } from "react";
import { ShieldCheck } from "lucide-react";

type PageHeroProps = {
  title: string;
  description: string;
  eyebrow?: ReactNode;
  actions?: ReactNode;
  metrics?: ReactNode;
};

export function PageHero({ title, description, eyebrow, actions, metrics }: PageHeroProps) {
  return (
    <section className="overflow-hidden rounded-xl border border-slate-800 bg-slate-950 px-5 py-6 text-white shadow-soft sm:px-6 sm:py-7">
      <div className="flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
        <div className="max-w-3xl">
          {eyebrow ? (
            <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/10 px-3 py-1 text-xs text-slate-200">
              <ShieldCheck size={14} />
              {eyebrow}
            </div>
          ) : null}
          <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">{title}</h1>
          <p className="mt-2 text-sm leading-6 text-slate-300">{description}</p>
        </div>
        {actions || metrics ? <div className="flex flex-wrap items-center gap-3">{actions}{metrics}</div> : null}
      </div>
    </section>
  );
}
