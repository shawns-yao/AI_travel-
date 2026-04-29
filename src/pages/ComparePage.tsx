import { useMemo, useState } from "react";
import { ArrowLeft, Bookmark, Calendar, Check, Crown, Gem, PiggyBank, Star, Users, Wallet } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { TravelPlanResult } from "@/types";

export interface PlanningDraft {
  destination: string;
  duration: string;
  startDate: string;
  people: string;
  budget: string;
  notes: string;
}

interface ComparePageProps {
  plan: TravelPlanResult | null;
  draft: PlanningDraft;
  onDraftChange: (draft: PlanningDraft) => void;
  onBack: () => void;
  onSaveDraft?: () => void;
  onGenerateVariant: (variant: string, draft: PlanningDraft) => void;
}

const variants = [
  {
    title: "舒适版",
    sub: "轻松舒适，体验经典精华",
    price: 4200,
    color: "from-[#0fb6bd] to-[#28c6b0]",
    icon: Crown,
    audience: "父母同行 / 休闲度假",
    points: ["每天安排 2-3 个精华景点，节奏舒适", "优选交通便利住宿，出行更省心", "住宿靠近核心区域", "预留自由时间"],
  },
  {
    title: "省钱版",
    sub: "经济实惠，性价比之选",
    price: 2800,
    color: "from-[#20b978] to-[#48c76b]",
    icon: PiggyBank,
    audience: "预算有限 / 学生党",
    points: ["公共交通优先", "住宿选地铁沿线", "免费或低价景点优先", "平价本地美食"],
  },
  {
    title: "深度游版",
    sub: "深度探索，体验地道城市",
    price: 4800,
    color: "from-[#2f91dd] to-[#65b8f5]",
    icon: Gem,
    audience: "年轻人 / 体力较好者",
    points: ["更多小众路线", "文化体验优先", "每天 4-5 个地点", "行程更紧凑"],
  },
];

export function ComparePage({ plan, draft, onDraftChange, onBack, onSaveDraft, onGenerateVariant }: ComparePageProps) {
  const [selectedVariant, setSelectedVariant] = useState("舒适版");
  const [detailVariant, setDetailVariant] = useState("舒适版");
  const activeDetail = useMemo(() => variants.find((item) => item.title === detailVariant) ?? variants[0], [detailVariant]);

  const updateDraft = (key: keyof PlanningDraft, value: string) => {
    onDraftChange({ ...draft, [key]: value });
  };

  return (
    <section className="min-h-[calc(100vh-68px)] bg-white">
      <div className="mx-auto max-w-[1240px] px-8 py-10">
        <div className="mb-8 flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <h1 className="text-4xl font-black tracking-normal">{draft.destination || plan?.destination || "杭州"} 旅行规划</h1>
            <div className="mt-4 flex flex-wrap items-center gap-5 text-sm font-medium text-slate-500">
              <span className="flex items-center gap-2"><Calendar className="h-4 w-4 text-[#0da8ad]" />{draft.startDate || plan?.start_date || "未定日期"}</span>
              <span className="flex items-center gap-2"><Users className="h-4 w-4 text-[#0da8ad]" />{draft.people || "2"}人</span>
              <span className="flex items-center gap-2"><Wallet className="h-4 w-4 text-[#0da8ad]" />预算约 {draft.budget || plan?.budget || 4000} 元</span>
            </div>
          </div>
          <div className="flex flex-wrap gap-3">
            <Button variant="outline" onClick={onBack} className="h-12 rounded-xl border-[#10b8bd] px-6 text-[#0da8ad]">
              <ArrowLeft className="h-4 w-4" />
              返回修改需求
            </Button>
            <Button onClick={onSaveDraft} disabled={!onSaveDraft} className="h-12 rounded-xl bg-[#10b8bd] px-6 text-white shadow-lg shadow-cyan-200 hover:bg-[#0ca8ad]">
              <Bookmark className="h-4 w-4" />
              保存当前方案
            </Button>
          </div>
        </div>

        <div className="mb-6 rounded-2xl border border-slate-200 bg-slate-50/70 p-5">
          <div className="grid gap-4 lg:grid-cols-5">
            <Field label="目的地" value={draft.destination} onChange={(value) => updateDraft("destination", value)} />
            <Field label="天数" value={draft.duration} onChange={(value) => updateDraft("duration", value)} />
            <Field label="出发日期" type="date" value={draft.startDate} onChange={(value) => updateDraft("startDate", value)} />
            <Field label="人数" value={draft.people} onChange={(value) => updateDraft("people", value)} />
            <Field label="预算" value={draft.budget} onChange={(value) => updateDraft("budget", value)} />
          </div>
          <div className="mt-4">
            <Field label="补充约束" value={draft.notes} onChange={(value) => updateDraft("notes", value)} />
          </div>
        </div>

        <div className="grid gap-6 lg:grid-cols-3">
          {variants.map((item) => {
            const Icon = item.icon;
            const selected = selectedVariant === item.title;
            return (
              <div key={item.title} className={`overflow-hidden rounded-2xl border bg-white shadow-sm ${selected ? "border-[#10b8bd] ring-2 ring-cyan-100" : "border-slate-200"}`}>
                <div className={`relative h-28 bg-gradient-to-r ${item.color} p-5 text-white`}>
                  <div className="absolute inset-0 bg-[url('https://images.unsplash.com/photo-1596176530529-78163a4f7af2?auto=format&fit=crop&w=900&q=60')] bg-cover bg-center opacity-25" />
                  <div className="relative flex items-center gap-3">
                    <div className="flex h-12 w-12 items-center justify-center rounded-full bg-white/90 text-[#0da8ad]">
                      <Icon className="h-7 w-7" />
                    </div>
                    <div>
                      <div className="text-2xl font-black">{item.title}</div>
                      <div className="text-sm font-medium opacity-95">{item.sub}</div>
                    </div>
                  </div>
                </div>
                <div className="p-6">
                  {[
                    ["预算", `约 ¥${item.price.toLocaleString()} / 人`],
                    ["行程强度", item.title === "舒适版" ? "轻松" : item.title === "省钱版" ? "中等" : "较高"],
                    ["每日景点", item.title === "舒适版" ? "2-3 个地点" : item.title === "省钱版" ? "3-4 个地点" : "4-5 个地点"],
                    ["适合人群", item.audience],
                  ].map(([label, value]) => (
                    <div key={label} className="flex justify-between gap-5 border-b border-slate-100 py-3 text-sm">
                      <span className="shrink-0 text-slate-500">{label}</span>
                      <span className="text-right font-semibold text-slate-900">{value}</span>
                    </div>
                  ))}
                  <div className="mt-5 space-y-3 text-sm text-slate-600">
                    {item.points.map((text) => (
                      <div key={text} className="flex gap-2"><Check className="mt-0.5 h-4 w-4 shrink-0 text-[#0da8ad]" />{text}</div>
                    ))}
                  </div>
                  <div className="mt-6 grid grid-cols-2 gap-3">
                    <Button variant="outline" onClick={() => setDetailVariant(item.title)} className="rounded-xl border-[#10b8bd] text-[#0da8ad]">查看详情</Button>
                    <Button onClick={() => setSelectedVariant(item.title)} className="rounded-xl bg-[#10b8bd] text-white hover:bg-[#0ca8ad]"><Star className="h-4 w-4" />设为主方案</Button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        <div className="mt-6 grid gap-6 lg:grid-cols-[1fr_320px]">
          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            <div className="mb-4 font-black">{activeDetail.title}详情</div>
            <div className="grid gap-4 md:grid-cols-2">
              {activeDetail.points.map((item) => (
                <div key={item} className="rounded-xl bg-slate-50 px-4 py-3 text-sm font-semibold text-slate-700">{item}</div>
              ))}
            </div>
          </div>
          <div className="rounded-2xl border border-cyan-100 bg-cyan-50/80 p-6 shadow-sm">
            <div className="text-sm font-semibold text-slate-500">当前主方案</div>
            <div className="mt-2 text-2xl font-black text-slate-950">{selectedVariant}</div>
            <Button onClick={() => onGenerateVariant(selectedVariant, draft)} className="mt-5 h-12 w-full rounded-xl bg-[#10b8bd] text-white hover:bg-[#0ca8ad]">
              <Star className="h-4 w-4" />
              开始规划
            </Button>
          </div>
        </div>
      </div>
    </section>
  );
}

interface FieldProps {
  label: string;
  value: string;
  type?: string;
  onChange: (value: string) => void;
}

function Field({ label, value, type = "text", onChange }: FieldProps) {
  return (
    <label className="block">
      <span className="mb-2 block text-sm font-bold text-slate-700">{label}</span>
      <Input
        type={type}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="h-12 rounded-xl border-slate-200 bg-white text-sm shadow-none focus-visible:ring-[#10b8bd]"
      />
    </label>
  );
}
