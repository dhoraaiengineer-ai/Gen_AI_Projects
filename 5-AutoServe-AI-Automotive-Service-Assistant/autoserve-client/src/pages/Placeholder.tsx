type Props = { title: string; task: string };

/** Empty route shell (P1-1). Each page is implemented in the task named in `task`. */
export function Placeholder({ title, task }: Props) {
  return (
    <section aria-labelledby="page-title" className="mx-auto max-w-4xl p-6">
      <h1 id="page-title" className="text-2xl font-semibold">
        {title}
      </h1>
      <p className="mt-2 text-sm text-slate-600 dark:text-slate-400">Not built yet — planned in {task}.</p>
    </section>
  );
}
