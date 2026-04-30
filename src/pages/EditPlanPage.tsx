import { useEffect, useMemo, useState } from "react";
import { Bed, Bike, Bus, Clock, Edit3, MapPin, RefreshCw, Save, Sparkles, Trash2, Utensils, Wallet } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Activity, POI, TravelPlanResult } from "@/types";
import { RouteMap } from "@/components/travel/RouteMap";
import { PlaceDetailModal } from "@/components/travel/PlaceDetailModal";
import { activityImage } from "@/lib/travelMedia";
import { activityDescriptionForCard, isTransferActivity } from "@/lib/travelActivities";

interface EditPlanPageProps {
  plan: TravelPlanResult;
  onSave: (plan: TravelPlanResult) => void;
  onOptimize: (query: string) => void;
  initialChanges?: string[];
  initialDay?: number;
}

const slots = [
  { label: "上午", time: "08:30 - 12:00", icon: Sparkles },
  { label: "下午", time: "13:30 - 16:30", icon: Sparkles },
  { label: "傍晚", time: "16:30 - 18:30", icon: Bed },
  { label: "晚上", time: "18:30 - 20:30", icon: Sparkles },
];

const changeOptions = [
  ["这天太累了", Bike],
  ["少走路", Sparkles],
  ["换一个景点", Sparkles],
  ["预算低一点", Wallet],
] as const;

const formatCost = (cost?: number) => {
  if (!Number.isFinite(cost) || Number(cost) <= 0) return "";
  return `¥${Math.round(Number(cost))}`;
};

const budgetLabels: Record<string, string> = {
  transport: "交通",
  accommodation: "住宿",
  meals: "餐饮",
  attractions: "景点门票",
  shopping: "购物",
  contingency: "机动",
};

const hasUserBudget = (plan: TravelPlanResult) =>
  Number(plan.budget) > 0
  && (plan.budget_source === "user" || plan.budget_breakdown?.budget_source === "user" || plan.budget_breakdown?.estimated === false);

const budgetItems = (plan: TravelPlanResult) => {
  if (!hasUserBudget(plan)) return [];
  return Object.entries(plan.budget_breakdown?.allocated ?? {})
    .filter(([, value]) => Number(value) > 0)
    .slice(0, 4)
    .map(([key, value]) => `${budgetLabels[key] ?? key} ¥${Math.round(Number(value) || 0)}`);
};

const foodItems = (plan: TravelPlanResult) =>
  (plan.map_data?.travel_tips?.food?.length ? plan.map_data.travel_tips.food : (plan.map_data?.food ?? []).map((item) => item.name))
    .slice(0, 3);

const hotelItems = (plan: TravelPlanResult) =>
  (plan.map_data?.travel_tips?.hotel?.length ? plan.map_data.travel_tips.hotel : (plan.map_data?.hotels ?? []).map((item) => item.name))
    .slice(0, 2);

const allPois = (plan: TravelPlanResult) => [
  ...(plan.map_data?.attractions ?? []),
  ...(plan.map_data?.food ?? []),
  ...(plan.map_data?.hotels ?? []),
];

const poiForActivity = (plan: TravelPlanResult, activity?: Activity): POI | null => {
  if (!activity) return null;
  if (activity.coordinate) {
    return {
      ...(allPois(plan).find((poi) => poi.photo && (poi.name.includes(activity.name) || activity.name.includes(poi.name))) ?? {}),
      id: activity.id,
      name: activity.name,
      type: activity.type,
      address: activity.location,
      location: activity.coordinate,
      source: activity.source,
      photo: activity.photo || allPois(plan).find((poi) => poi.photo && (poi.name.includes(activity.name) || activity.name.includes(poi.name)))?.photo,
    };
  }
  return allPois(plan).find((poi) => poi.name && (poi.name.includes(activity.name) || activity.name.includes(poi.name))) ?? {
    id: activity.id,
    name: activity.name,
    type: activity.type,
    address: activity.location,
    location: null,
    source: activity.source,
    photo: activity.photo,
  };
};

export function EditPlanPage({ plan, onSave, onOptimize, initialChanges = [], initialDay = 0 }: EditPlanPageProps) {
  const [selectedDay, setSelectedDay] = useState(initialDay);
  const [saved, setSaved] = useState(false);
  const [selectedChanges, setSelectedChanges] = useState<string[]>(initialChanges);
  const [selectedPoi, setSelectedPoi] = useState<POI | null>(null);
  const day = plan.daily_plans?.[selectedDay] ?? plan.daily_plans?.[0];
  const budgets = useMemo(() => budgetItems(plan), [plan]);
  const foods = useMemo(() => foodItems(plan), [plan]);
  const hotels = useMemo(() => hotelItems(plan), [plan]);

  const activities = useMemo(
    () => (day?.activities ?? []).filter((activity) => !isTransferActivity(activity)).slice(0, 4),
    [day],
  );

  useEffect(() => {
    setSelectedDay(initialDay);
    setSelectedChanges(initialChanges);
  }, [initialChanges, initialDay]);

  const title = `${plan.destination || "杭州"} ${plan.duration || 3} 日轻松游`;
  const toggleChange = (text: string) => {
    setSelectedChanges((current) =>
      current.includes(text) ? current.filter((item) => item !== text) : [...current, text],
    );
  };

  const submitChanges = () => {
    if (!selectedChanges.length) return;
    onOptimize(`${title}，仅调整 Day ${day?.day ?? selectedDay + 1}：${selectedChanges.join("，")}。生成前保持原天数、预算和目的地不变。`);
  };

  return (
    <section className="min-h-[calc(100vh-68px)] bg-gradient-to-br from-cyan-50 via-white to-white">
      <div className="mx-auto max-w-[1500px] px-8 py-10">
        <div className="mb-7 flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-4xl font-black tracking-normal">编辑{title}</h1>
              <Edit3 className="h-6 w-6 text-[#0da8ad]" />
            </div>
            <div className="mt-3 text-sm font-medium text-slate-500">自由调整行程顺序、修改景点和时间</div>
          </div>
          <div className="flex flex-wrap gap-3">
            <Button
              variant="outline"
              onClick={() => {
                onSave(plan);
                setSaved(true);
              }}
              className="h-12 rounded-xl px-8"
            >
              <Save className="h-4 w-4" />
              {saved ? "已保存" : "保存"}
            </Button>
            <Button variant="outline" onClick={() => setSelectedChanges([])} disabled={!selectedChanges.length} className="h-12 rounded-xl px-8">
              <RefreshCw className="h-4 w-4" />
              撤销
            </Button>
            <Button onClick={submitChanges} disabled={!selectedChanges.length} className="h-12 rounded-xl bg-[#10b8bd] px-8 text-white shadow-lg shadow-cyan-200 hover:bg-[#0ca8ad] disabled:bg-slate-300 disabled:shadow-none">
              <Sparkles className="h-4 w-4" />
              确认优化
            </Button>
          </div>
        </div>

        <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_420px]">
          <div className="rounded-2xl border border-slate-200 bg-white/92 shadow-sm">
            <div className="flex border-b border-slate-100 px-6">
              {(plan.daily_plans?.length ? plan.daily_plans : [{ day: 1 }]).map((item, index) => (
                <button
                  key={item.day}
                  onClick={() => setSelectedDay(index)}
                  className={`h-16 px-8 text-sm font-bold ${selectedDay === index ? "border-b-2 border-[#10b8bd] text-[#0da8ad]" : "text-slate-500"}`}
                >
                  Day {item.day}
                </button>
              ))}
            </div>

            <div className="p-6">
              {activities.map((item, index) => {
                const slot = slots[index] ?? { label: item.time || `时段 ${index + 1}`, time: item.time || "", icon: Sparkles };
                const Icon = slot.icon;
                const itemCost = formatCost(item.cost);
                const image = activityImage(plan, item, index);
                return (
                  <div key={`${item.id}-${index}`} className="border-b border-slate-100 py-5 last:border-0">
                    <div className="min-w-0 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                      <div className="space-y-4">
                        <div className="flex flex-wrap items-start gap-5">
                          <div className="w-24 shrink-0">
                            <Icon className="mb-2 h-5 w-5 text-[#0da8ad]" />
                            <div className="text-lg font-black">{slot.label}</div>
                            <div className="mt-1 text-sm font-medium text-slate-500">{slot.time}</div>
                          </div>
                          <div className="min-w-[260px] flex-1">
                            <div className="text-xl font-black leading-snug break-words">{item.name}</div>
                            <div className="mt-1 text-sm font-medium text-slate-500">{item.location || plan.destination}</div>
                            <div className="mt-3 flex flex-wrap gap-2 text-sm font-semibold text-slate-600">
                              <span className="inline-flex items-center gap-1 rounded-full border border-slate-200 px-3 py-1.5">
                                <Clock className="h-4 w-4 text-[#0da8ad]" />
                                {slot.time}
                              </span>
                              <span className="inline-flex items-center gap-1 rounded-full border border-slate-200 px-3 py-1.5">
                                <Bus className="h-4 w-4 text-[#0da8ad]" />
                                步行
                              </span>
                              {itemCost && (
                                <span className="rounded-full border border-slate-200 px-3 py-1.5">
                                  预计费用 <span className="font-black text-[#0da8ad]">{itemCost}</span>
                                </span>
                              )}
                            </div>
                          </div>
                        </div>
                        <div className="rounded-xl bg-slate-50 px-5 py-4 text-sm font-semibold leading-7 text-slate-600">
                          {activityDescriptionForCard(item)}
                        </div>
                        {image && <img src={image} alt="" className="h-48 w-full rounded-xl object-cover" />}
                        <div className="flex flex-wrap gap-2 text-sm font-semibold">
                            <button
                              onClick={() => {
                                const poi = poiForActivity(plan, item);
                                if (poi) setSelectedPoi(poi);
                              }}
                              className="inline-flex h-9 items-center gap-1 rounded-full border border-slate-200 px-3 text-[#0da8ad] hover:border-[#10b8bd] hover:bg-cyan-50 disabled:text-slate-300 disabled:hover:border-slate-200 disabled:hover:bg-transparent"
                              disabled={!poiForActivity(plan, item)}
                            >
                              <MapPin className="h-4 w-4" />
                              地图
                            </button>
                            <ActionButton
                              icon={Trash2}
                              label="删除"
                              active={selectedChanges.includes(`删除${slot.label}：${item.name}`)}
                              tone="danger"
                              onClick={() => toggleChange(`删除${slot.label}：${item.name}`)}
                            />
                            <ActionButton
                              icon={RefreshCw}
                              label="替换"
                              active={selectedChanges.includes(`替换${slot.label}：${item.name}`)}
                              onClick={() => toggleChange(`替换${slot.label}：${item.name}`)}
                            />
                            <ActionButton
                              icon={Clock}
                              label="调时"
                              active={selectedChanges.includes(`调整${slot.label}时间`)}
                              tone="muted"
                              onClick={() => toggleChange(`调整${slot.label}时间`)}
                            />
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
            <div className="border-t border-slate-100 p-6">
              <RouteMap mapData={plan.map_data} heightClass="min-h-[420px]" />
            </div>
          </div>

          <aside className="space-y-5 xl:sticky xl:top-24 xl:self-start">
            <Panel title="你想怎么改？">
              <div className="grid grid-cols-2 gap-3">
                {changeOptions.map(([text, Icon]) => {
                  const I = Icon as typeof Sparkles;
                  const selected = selectedChanges.includes(text);
                  return (
                    <button
                      key={text}
                      onClick={() => toggleChange(text)}
                      className={`h-12 rounded-xl border text-sm font-bold transition ${selected ? "border-[#10b8bd] bg-cyan-50 text-[#0da8ad]" : "border-slate-200 bg-white text-slate-700 hover:border-[#10b8bd] hover:text-[#0da8ad]"}`}
                    >
                      <I className="mr-2 inline h-4 w-4" />
                      {text}
                    </button>
                  );
                })}
              </div>
              <div className="mt-4 flex gap-3">
                <Button onClick={submitChanges} disabled={!selectedChanges.length} className="flex-1 rounded-xl bg-[#10b8bd] text-white hover:bg-[#0ca8ad] disabled:bg-slate-300">
                  确认优化{selectedChanges.length ? `（${selectedChanges.length}）` : ""}
                </Button>
                <Button variant="outline" onClick={() => setSelectedChanges([])} disabled={!selectedChanges.length} className="rounded-xl">
                  清空
                </Button>
              </div>
            </Panel>

            <Panel title="方案信息">
              {!!budgets.length && <InfoBlock icon={Wallet} title="预算估算" items={budgets} />}
              <InfoBlock icon={Bed} title="住宿推荐" items={hotels.length ? hotels : ["住宿区域待补充"]} />
              <InfoBlock icon={Utensils} title="美食清单" items={foods.length ? foods : ["美食信息待补充"]} />
            </Panel>

            <Panel title="待确认修改">
              {selectedChanges.length ? (
                <div className="flex flex-wrap gap-2">
                  {selectedChanges.map((item) => (
                    <button
                      key={item}
                      onClick={() => toggleChange(item)}
                      className="rounded-full bg-cyan-50 px-3 py-2 text-sm font-bold text-[#0b7f84] hover:bg-cyan-100"
                    >
                      {item}
                    </button>
                  ))}
                </div>
              ) : (
                <div className="rounded-xl bg-slate-50 px-4 py-3 text-sm font-semibold text-slate-500">未选择修改项</div>
              )}
            </Panel>
          </aside>
        </div>
      </div>
      {selectedPoi && <PlaceDetailModal plan={plan} initialPoi={selectedPoi} onClose={() => setSelectedPoi(null)} />}
    </section>
  );
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white/92 p-5 shadow-sm">
      <div className="mb-4 text-xl font-black">{title}</div>
      {children}
    </div>
  );
}

function InfoBlock({ icon: Icon, title, items }: { icon: typeof Wallet; title: string; items: string[] }) {
  return (
    <div className="mb-4 last:mb-0">
      <div className="mb-2 flex items-center gap-2 text-sm font-black text-slate-900">
        <Icon className="h-4 w-4 text-[#0da8ad]" />
        {title}
      </div>
      <div className="flex flex-wrap gap-2">
        {items.map((item) => (
          <div key={item} className="rounded-full bg-slate-50 px-3 py-2 text-sm font-semibold leading-6 text-slate-600">
            {item}
          </div>
        ))}
      </div>
    </div>
  );
}

function ActionButton({
  icon: Icon,
  label,
  active,
  tone = "primary",
  onClick,
}: {
  icon: typeof RefreshCw;
  label: string;
  active: boolean;
  tone?: "primary" | "danger" | "muted";
  onClick: () => void;
}) {
  const activeClass = tone === "danger" ? "border-rose-200 bg-rose-50 text-rose-600" : "border-[#10b8bd] bg-cyan-50 text-[#0da8ad]";
  const idleClass = tone === "danger" ? "text-rose-500 hover:bg-rose-50" : tone === "muted" ? "text-slate-600 hover:bg-slate-50" : "text-[#0da8ad] hover:bg-cyan-50";
  return (
    <button onClick={onClick} className={`inline-flex h-9 items-center gap-1 rounded-full border px-3 ${active ? activeClass : `border-transparent ${idleClass}`}`}>
      <Icon className="h-4 w-4" />
      {label}
    </button>
  );
}
