export function ComingSoon({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="flex max-w-xl flex-col gap-2">
      <h1 className="m-0 text-[26px] font-semibold tracking-[-0.02em]">{title}</h1>
      <p className="text-subtle">{children}</p>
    </section>
  );
}
