import { useMemo, useState } from "react";
import { Bed, Bike, Bus, Clock, Edit3, Plus, RefreshCw, Save, Sparkles, Trash2, Utensils, Wallet } from "lucide-react";
import { Button } from "@/components/ui/button";
import { TravelPlanResult } from "@/types";

interface EditPlanPageProps {
  plan: TravelPlanResult;
  onSave: (plan: TravelPlanResult) => void;
  onOptimize: (query: string) => void;
}

const slots = [
  { label: "上午", time: "08:30 - 12:00", icon: Sparkles },
  { label: "下午", time: "13:30 - 16:30", icon: Sparkles },
  { label: "傍晚", time: "16:30 - 18:30", icon: Bed },
  { label: "晚上", time: "18:30 - 20:30", icon: Utensils },
];

const images = [
  "https://images.unsplash.com/photo-1596176530529-78163a4f7af2?auto=format&fit=crop&w=240&q=80",
  "https://images.unsplash.com/photo-1543353071-873f17a7a088?auto=format&fit=crop&w=240&q=80",
  "https://images.unsplash.com/photo-1528127269322-539801943592?auto=format&fit=crop&w=240&q=80",
  "https://images.unsplash.com/photo-1512453979798-5ea266f8880c?auto=format&fit=crop&w=240&q=80",
];

const changeOptions = [
  ["这天太累了", Bike],
  ["少走路", Sparkles],
  ["换一个景点", Sparkles],
  ["晚餐想吃火锅", Utensils],
  ["预算低一点", Wallet],
  ["多加本地美食", Utensils],
] as const;

const formatCost = (cost?: number) => {
  if (!Number.isFinite(cost) || Number(cost) <= 0) return "费用待查";
  return `¥${Math.round(Number(cost))}`;
};

export function EditPlanPage({ plan, onSave, onOptimize }: EditPlanPageProps) {
  const [selectedDay, setSelectedDay] = useState(0);
  const [saved, setSaved] = useState(false);
  const [selectedChanges, setSelectedChanges] = useState<string[]>([]);
  const day = plan.daily_plans?.[selectedDay] ?? plan.daily_plans?.[0];

  const activities = useMemo(
    () =>
      [
        ...(day?.activities ?? []).slice(0, 3),
        ...((day?.meals ?? []).filter((meal) => meal.time.includes("晚") || meal.type === "dinner").slice(0, 1)).map((meal) => ({
          id: meal.id,
          name: meal.name,
          location: meal.location,
          time: meal.time,
          cost: meal.cost,
          transport: "步行",
        })),
      ].slice(0, 4),
    [day],
  );

  const title = `${plan.destination || "杭州"} ${plan.duration || 3} 日轻松游`;
  const toggleChange = (text: string) => {
    setSelectedChanges((current) =>
      current.includes(text) ? current.filter((item) => item !== text) : [...current, text],
    );
  };
  const addChange = (text: string) => {
    setSelectedChanges((current) => (current.includes(text) ? current : [...current, text]));
  };

  const submitChanges = () => {
    if (!selectedChanges.length) return;
    onOptimize(`${title}，仅调整 Day ${day?.day ?? selectedDay + 1}：${selectedChanges.join("，")}。生成前保持原天数、预算和目的地不变。`);
  };

  return (
    <section className="min-h-[calc(100vh-68px)] bg-gradient-to-br from-cyan-50 via-white to-white">
      <div className="mx-auto max-w-[1360px] px-8 py-10">
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

        <div className="grid gap-6 xl:grid-cols-[1fr_390px]">
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
              {slots.map((slot, index) => {
                const Icon = slot.icon;
                const item = activities[index];
                return (
                  <div key={slot.label} className="grid gap-6 border-b border-slate-100 py-5 last:border-0 lg:grid-cols-[110px_1fr_34px]">
                    <div className="flex gap-3 lg:block">
                      <Icon className="h-5 w-5 text-[#0da8ad]" />
                      <div className="mt-1 text-lg font-black">{slot.label}</div>
                      <div className="mt-1 text-sm font-medium text-slate-500">{slot.time}</div>
                    </div>
                    <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                      <div className="grid gap-4 md:grid-cols-[120px_1fr_160px]">
                        <img src={images[index % images.length]} alt="" className="h-24 w-full rounded-xl object-cover" />
                        <div>
                          <div className="text-lg font-black">{item?.name || `${plan.destination}自由活动`}</div>
                          <div className="mt-2 flex flex-wrap gap-4 text-sm font-medium text-slate-500">
                            <span className="flex items-center gap-1"><Clock className="h-4 w-4" />{slot.time}</span>
                            <span className="flex items-center gap-1"><Bus className="h-4 w-4" />步行</span>
                          </div>
                          <div className="mt-3 text-sm font-medium text-slate-500">预计费用 <span className="font-black text-[#0da8ad]">{formatCost(item?.cost)}</span></div>
                        </div>
                        <div className="grid grid-cols-2 gap-2 text-sm font-semibold">
                          <button onClick={() => addChange(`删除${slot.label}${item?.name ? `：${item.name}` : "空时段"}`)} className="rounded-lg text-rose-500 hover:bg-rose-50"><Trash2 className="mr-1 inline h-4 w-4" />删除</button>
                          <button onClick={() => addChange(`替换${slot.label}${item?.name ? `：${item.name}` : "空时段"}`)} className="rounded-lg text-[#0da8ad] hover:bg-cyan-50"><RefreshCw className="mr-1 inline h-4 w-4" />替换</button>
                          <button onClick={() => addChange(`调整${slot.label}时间`)} className="col-span-2 rounded-lg text-slate-600 hover:bg-slate-50"><Clock className="mr-1 inline h-4 w-4" />调整时间</button>
                        </div>
                      </div>
                    </div>
                    <div className="hidden items-center justify-center text-slate-300 lg:flex">::</div>
                  </div>
                );
              })}

              <button
                onClick={() => {
                  const text = "增加一个景点时段";
                  addChange(text);
                }}
                className="mx-auto mt-5 flex h-14 w-[360px] max-w-full items-center justify-center rounded-xl border border-slate-200 text-base font-bold text-[#0da8ad] hover:border-[#10b8bd] hover:bg-cyan-50"
              >
                <Plus className="mr-2 h-5 w-5" />
                添加时段 / 景点
              </button>
            </div>
          </div>

          <aside className="space-y-5">
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

            <Panel title="修改影响预览">
              {[
                ["预计步行减少 30%", "约减少 2.6 公里步行"],
                ["预算减少 200 元", "人均从 ¥215 降至 ¥15"],
                ["下午路线已调整", "将替换为更轻松的景点组合"],
                ["不会影响 Day 1 和 Day 3", "仅调整当前日期内容"],
              ].map(([titleText, desc]) => (
                <div key={titleText} className="mb-3 rounded-xl border border-slate-100 bg-white p-4">
                  <div className="font-bold text-slate-900">{titleText}</div>
                  <div className="mt-1 text-sm text-slate-500">{desc}</div>
                </div>
              ))}
            </Panel>
          </aside>
        </div>
      </div>
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
