import { Plane } from "lucide-react";

export function Brand() {
  return (
    <div className="flex items-center gap-3">
      <div className="flex h-9 w-9 items-center justify-center rounded-full bg-[#12b9bd] text-white shadow-sm">
        <Plane className="h-5 w-5" />
      </div>
      <span className="text-xl font-bold tracking-normal text-slate-950">AI Travel</span>
    </div>
  );
}
