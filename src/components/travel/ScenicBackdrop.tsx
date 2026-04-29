export function ScenicBackdrop() {
  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden">
      <div className="absolute inset-x-0 top-0 h-[360px] bg-gradient-to-b from-cyan-50 via-white to-transparent" />
      <div className="absolute left-0 top-24 h-[460px] w-[460px] rounded-full bg-cyan-100/45 blur-3xl" />
      <div className="absolute right-0 top-28 h-[420px] w-[520px] rounded-full bg-blue-100/50 blur-3xl" />
      <div className="absolute bottom-0 left-0 h-[260px] w-full bg-gradient-to-t from-cyan-50/70 to-transparent" />
    </div>
  );
}
