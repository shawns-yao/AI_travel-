import { useMemo, useState } from "react";
import { Archive, Calendar, CheckCircle2, Download, Edit3, Plus, Share2, Trash2, Users, Wallet } from "lucide-react";
import { Button } from "@/components/ui/button";
import { TravelPlanResult } from "@/types";
import { isTransferActivity } from "@/lib/travelActivities";

interface PlansPageProps {
  plans: TravelPlanResult[];
  onNew: () => void;
  onOpenPlan: (plan: TravelPlanResult) => void;
  onDelete: (plan: TravelPlanResult) => void | Promise<void>;
}

type PlanStatus = "草稿" | "已生成" | "已分享" | "已归档";

interface PlanCard {
  id: string;
  plan: TravelPlanResult;
  title: string;
  date: string;
  people: string;
  budget: string;
  desc: string;
  status: PlanStatus;
  image: string;
}

const images = {
  hangzhou: "https://images.unsplash.com/photo-1596176530529-78163a4f7af2?auto=format&fit=crop&w=900&q=80",
  chengdu: "https://images.unsplash.com/photo-1532629345422-7515f3d16bb6?auto=format&fit=crop&w=900&q=80",
  qingdao: "https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?auto=format&fit=crop&w=900&q=80",
  sanya: "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=900&q=80",
  suzhou: "https://images.unsplash.com/photo-1506744038136-46273834b3fb?auto=format&fit=crop&w=900&q=80",
  dali: "https://images.unsplash.com/photo-1500534314209-a25ddb2bd429?auto=format&fit=crop&w=900&q=80",
};

const tabs: Array<{ label: "全部" | PlanStatus; icon: typeof CheckCircle2 }> = [
  { label: "全部", icon: Archive },
  { label: "草稿", icon: Edit3 },
  { label: "已生成", icon: CheckCircle2 },
  { label: "已分享", icon: Share2 },
  { label: "已归档", icon: Archive },
];

const formatDate = (plan: TravelPlanResult) => {
  if (!plan.start_date) return `${plan.duration || 3}天`;
  const parsed = new Date(plan.start_date);
  if (Number.isNaN(parsed.getTime())) return plan.start_date;
  const end = new Date(parsed);
  end.setDate(parsed.getDate() + Math.max((plan.duration || 3) - 1, 0));
  return `${parsed.getMonth() + 1}月${parsed.getDate()}日 - ${end.getMonth() + 1}月${end.getDate()}日`;
};

const inferPeopleCount = (plan: TravelPlanResult) => {
  const preferences = plan.preferences ?? [];
  if (preferences.some((item) => item.includes("父母") || item.includes("老人") || item.includes("孩子"))) return "3人";
  return "2人";
};

const exportPlan = (plan: TravelPlanResult) => {
  const blob = new Blob([JSON.stringify(plan, null, 2)], { type: "application/json;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `${plan.destination || "travel"}-${plan.duration || 3}days.json`;
  anchor.click();
  URL.revokeObjectURL(url);
};

export function PlansPage({ plans, onNew, onOpenPlan, onDelete }: PlansPageProps) {
  const [activeTab, setActiveTab] = useState<"全部" | PlanStatus>("全部");
  const [deletingIds, setDeletingIds] = useState<string[]>([]);

  const planCards = useMemo<PlanCard[]>(() => {
    return plans.map((plan, index) => ({
      id: `saved-${plan.destination}-${plan.start_date}-${index}`,
      plan,
      title: `${plan.destination} ${plan.duration || 3} 日轻松游`,
      date: formatDate(plan),
      people: inferPeopleCount(plan),
      budget: `¥${plan.budget || 0}`,
      desc: (plan.daily_plans?.[0]?.activities ?? []).filter((item) => !isTransferActivity(item)).slice(0, 2).map((item) => item.name).join("、") || "城市轻松游",
      status: "已生成" as PlanStatus,
      image: Object.values(images)[index % Object.values(images).length],
    }));
  }, [plans]);

  const filtered = activeTab === "全部" ? planCards : planCards.filter((item) => item.status === activeTab);
  const deletePlan = async (item: PlanCard) => {
    if (deletingIds.includes(item.id)) return;
    setDeletingIds((current) => [...current, item.id]);
    try {
      await onDelete(item.plan);
    } finally {
      setDeletingIds((current) => current.filter((id) => id !== item.id));
    }
  };

  return (
    <section className="min-h-[calc(100vh-68px)] bg-white">
      <div className="mx-auto max-w-[1260px] px-8 py-10">
        <div className="mb-8 flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <h1 className="text-4xl font-black tracking-normal">我的行程</h1>
            <div className="mt-3 text-sm font-medium text-slate-500">管理旅行计划，开启下一段旅程</div>
          </div>
          <Button onClick={onNew} className="h-12 rounded-xl bg-[#10b8bd] px-7 text-white shadow-lg shadow-cyan-200 hover:bg-[#0ca8ad]">
            <Plus className="h-5 w-5" />
            新建旅行计划
          </Button>
        </div>

        <div className="mb-7 flex flex-wrap gap-4">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const active = activeTab === tab.label;
            return (
              <button
                key={tab.label}
                onClick={() => setActiveTab(tab.label)}
                className={`flex h-12 items-center gap-2 rounded-xl border px-7 text-sm font-bold ${active ? "border-[#10b8bd] bg-[#10b8bd] text-white shadow-lg shadow-cyan-100" : "border-slate-200 bg-white text-slate-600"}`}
              >
                <Icon className="h-4 w-4" />
                {tab.label}
              </button>
            );
          })}
        </div>

        <div className="grid gap-6 xl:grid-cols-3">
          {filtered.length ? filtered.map((item) => (
            <div key={item.id} className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
              <img src={item.image} alt="" className="h-40 w-full object-cover" />
              <div className="p-5">
                <div className="flex items-center justify-between gap-3">
                  <h2 className="text-xl font-black">{item.title}</h2>
                  <span className={`shrink-0 rounded-full px-3 py-1 text-xs font-bold ${item.status === "草稿" ? "bg-amber-50 text-amber-600" : item.status === "已分享" ? "bg-sky-50 text-sky-600" : item.status === "已归档" ? "bg-slate-100 text-slate-500" : "bg-emerald-50 text-emerald-600"}`}>
                    {item.status}
                  </span>
                </div>
                <div className="mt-4 flex flex-wrap gap-4 text-sm font-medium text-slate-500">
                  <span className="flex items-center gap-1"><Calendar className="h-4 w-4" />{item.date}</span>
                  <span className="flex items-center gap-1"><Users className="h-4 w-4" />{item.people}</span>
                  <span className="flex items-center gap-1"><Wallet className="h-4 w-4" />{item.budget}</span>
                </div>
                <p className="mt-4 min-h-[48px] text-sm leading-6 text-slate-600">{item.desc}</p>
                <div className="mt-5 grid grid-cols-3 gap-2 border-t pt-4 text-xs font-semibold text-slate-500">
                  <button onClick={() => onOpenPlan(item.plan)} className="flex min-h-10 items-center justify-center gap-1 rounded-lg hover:bg-cyan-50 hover:text-[#0da8ad]"><Edit3 className="h-4 w-4" />编辑</button>
                  <button onClick={() => exportPlan(item.plan)} className="flex min-h-10 items-center justify-center gap-1 rounded-lg hover:bg-cyan-50 hover:text-[#0da8ad]"><Download className="h-4 w-4" />导出</button>
                  <button
                    onClick={() => void deletePlan(item)}
                    disabled={deletingIds.includes(item.id)}
                    className="flex min-h-10 items-center justify-center gap-1 rounded-lg text-rose-500 hover:bg-rose-50"
                  >
                    <Trash2 className="h-4 w-4" />
                    {deletingIds.includes(item.id) ? "删除中" : "删除"}
                  </button>
                </div>
              </div>
            </div>
          )) : (
            <div className="col-span-full rounded-2xl border border-dashed border-slate-200 bg-slate-50 p-10 text-center">
              <div className="text-lg font-black text-slate-900">暂无真实保存的行程</div>
              <Button onClick={onNew} className="mt-5 rounded-xl bg-[#10b8bd] px-7 text-white hover:bg-[#0ca8ad]">
                <Plus className="h-4 w-4" />
                新建旅行计划
              </Button>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
