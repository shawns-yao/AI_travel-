import { useMemo, useState } from "react";
import { Calendar, CheckCircle2, Download, Hotel, Save, Share2, Utensils, Users, Wallet } from "lucide-react";
import { Button } from "@/components/ui/button";
import { TravelPlanResult } from "@/types";
import { RouteMapMock } from "@/components/travel/RouteMapMock";

interface ResultPageProps {
  plan: TravelPlanResult;
  onSave?: (plan: TravelPlanResult) => void;
  onDuplicate?: (query: string) => void;
}

const timeLabels = ["上午", "下午", "傍晚", "晚上"];

const formatDateRange = (startDate: string, duration: number) => {
  if (!startDate) return `${duration} 天`;
  const parsed = new Date(startDate);
  if (Number.isNaN(parsed.getTime())) return `${startDate} - ${duration} 天`;
  const end = new Date(parsed);
  end.setDate(parsed.getDate() + Math.max(duration - 1, 0));
  const format = (date: Date) => `${date.getMonth() + 1}月${date.getDate()}日`;
  return `${format(parsed)} - ${format(end)}`;
};

const inferPeopleCount = (preferences: string[]) => {
  if (preferences.some((item) => item.includes("父母") || item.includes("老人"))) return "3人";
  if (preferences.some((item) => item.includes("亲子") || item.includes("孩子"))) return "3人";
  return "2人";
};

const isMissingWeather = (day: { condition?: string; temp_high?: number; temp_low?: number; source?: string }) =>
  day.condition === "no_data" || day.condition === "unknown" || day.source === "fallback";

const weatherLabel = (condition?: string) => {
  if (condition === "no_data") return "暂无预报";
  if (condition === "unknown") return "待更新";
  return condition || "待更新";
};

const weatherMeta = (day: { condition?: string; temp_high?: number; temp_low?: number; source?: string }) => {
  if (day.condition === "no_data") return "超出7日";
  if (isMissingWeather(day)) return "天气待查";
  return `${day.temp_low}° / ${day.temp_high}°`;
};

const cleanHotelCost = (cost?: string) => {
  const value = String(cost || "").trim();
  if (!value || value === "[]" || value === "{}" || value === "0") return "";
  const normalized = value.replace(/^¥?\s*/, "");
  return normalized ? `¥${normalized}` : "";
};

const formatActivityCost = (cost?: number) => {
  if (!Number.isFinite(cost) || Number(cost) <= 0) return "费用待查";
  return `预计 ¥${Math.round(Number(cost))}`;
};

export function ResultPage({ plan, onSave, onDuplicate }: ResultPageProps) {
  const [selectedDay, setSelectedDay] = useState(0);
  const [saved, setSaved] = useState(false);
  const [selectedOptimizations, setSelectedOptimizations] = useState<string[]>([]);
  const currentDay = plan.daily_plans?.[selectedDay] ?? plan.daily_plans?.[0];
  const dateRange = formatDateRange(plan.start_date, plan.duration || 3);
  const peopleCount = inferPeopleCount(plan.preferences ?? []);
  const hotel = plan.map_data?.hotels?.[0];
  const hotelCost = cleanHotelCost(hotel?.cost);
  const activities = useMemo(() => (currentDay?.activities ?? []).slice(0, 4), [currentDay]);
  const dinner = useMemo(
    () => (currentDay?.meals ?? []).find((meal) => meal.time.includes("晚") || meal.type === "dinner") ?? currentDay?.meals?.[0],
    [currentDay],
  );
  const meals = dinner ? [dinner] : [];

  const exportPlan = () => {
    const blob = new Blob([JSON.stringify(plan, null, 2)], { type: "application/json;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${plan.destination || "travel"}-${plan.duration || 3}days.json`;
    anchor.click();
    URL.revokeObjectURL(url);
  };

  const sharePlan = async () => {
    const text = `${plan.destination}${plan.duration}日旅行方案，预算约${plan.budget}元`;
    if (navigator.share) {
      await navigator.share({ title: "AI Travel 行程", text });
    } else {
      await navigator.clipboard.writeText(text);
    }
  };
  const toggleOptimization = (text: string) => {
    setSelectedOptimizations((current) =>
      current.includes(text) ? current.filter((item) => item !== text) : [...current, text],
    );
  };
  const submitOptimizations = () => {
    if (!selectedOptimizations.length) return;
    onDuplicate?.([
      `${plan.destination}${plan.duration}日游`,
      plan.start_date ? `出发日期：${plan.start_date}` : "",
      `预算：${plan.budget || 4000}元`,
      `基于当前方案调整：${selectedOptimizations.join("，")}`,
      "保持目的地、天数和预算不变",
    ].filter(Boolean).join("，"));
  };

  return (
    <section className="min-h-[calc(100vh-68px)] bg-white">
      <div className="mx-auto max-w-[1360px] px-8 py-10">
        <div className="mb-7 flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <h1 className="text-4xl font-black tracking-normal">{plan.destination || "杭州"} {plan.duration || 3} 日轻松游</h1>
            <div className="mt-4 flex flex-wrap items-center gap-6 text-sm font-medium text-slate-600">
              <span className="flex items-center gap-2"><Calendar className="h-4 w-4 text-[#0da8ad]" />{dateRange}</span>
              <span className="flex items-center gap-2"><Users className="h-4 w-4 text-[#0da8ad]" />{peopleCount}</span>
              <span className="flex items-center gap-2"><Wallet className="h-4 w-4 text-[#0da8ad]" />预算约 {plan.budget || 4000} 元</span>
            </div>
          </div>
          <div className="flex gap-3">
            <Button
              onClick={() => {
                onSave?.(plan);
                setSaved(true);
              }}
              className="rounded-xl bg-[#10b8bd] px-6 text-white hover:bg-[#0ca8ad]"
            >
              {saved ? <CheckCircle2 className="h-4 w-4" /> : <Save className="h-4 w-4" />}
              {saved ? "已保存" : "保存"}
            </Button>
            <Button variant="outline" onClick={() => void sharePlan()} className="rounded-xl px-6"><Share2 className="h-4 w-4" />分享</Button>
            <Button variant="outline" onClick={exportPlan} className="rounded-xl px-6"><Download className="h-4 w-4" />导出</Button>
          </div>
        </div>

        <div className="grid gap-6 xl:grid-cols-[260px_1fr_430px]">
          <aside className="space-y-4">
            {(plan.daily_plans?.length ? plan.daily_plans : [{ day: 1, activities: [], meals: [] }]).map((day, index) => (
              <button
                key={day.day}
                onClick={() => setSelectedDay(index)}
                className={`flex w-full gap-4 rounded-xl border p-3 text-left ${index === selectedDay ? "border-[#10b8bd] bg-cyan-50" : "border-slate-200 bg-white"}`}
              >
                <div className="h-16 w-16 overflow-hidden rounded-lg bg-cyan-100">
                  <img src={index === 0 ? "https://images.unsplash.com/photo-1596176530529-78163a4f7af2?auto=format&fit=crop&w=200&q=80" : "https://images.unsplash.com/photo-1528127269322-539801943592?auto=format&fit=crop&w=200&q=80"} alt="" className="h-full w-full object-cover" />
                </div>
                <div>
                  <div className="font-bold">Day {day.day}</div>
                  <div className="mt-1 text-sm leading-5 text-slate-600">{day.activities?.[0]?.name || "城市轻松游"}</div>
                </div>
              </button>
            ))}
          </aside>

          <div>
            <div className="mb-4 text-xl font-bold">Day {currentDay?.day ?? 1}　{currentDay?.activities?.[0]?.name || `抵达${plan.destination || "杭州"}`}</div>
            {selectedOptimizations.length > 0 && (
              <div className="mb-4 flex flex-wrap items-center gap-3 rounded-xl border border-cyan-100 bg-cyan-50/80 p-3">
                <div className="flex-1 text-sm font-semibold text-slate-700">{selectedOptimizations.join("，")}</div>
                <Button onClick={submitOptimizations} className="h-10 rounded-xl bg-[#10b8bd] px-5 text-white hover:bg-[#0ca8ad]">确认优化</Button>
                <Button variant="outline" onClick={() => setSelectedOptimizations([])} className="h-10 rounded-xl">清空</Button>
              </div>
            )}
            <div className="relative border-l border-dashed border-[#12b9bd]/45 pl-8">
              {activities.length ? activities.map((item, index) => (
                <div key={item.id} className="relative mb-5 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                  <div className="absolute -left-[43px] top-6 h-5 w-5 rounded-full border-4 border-white bg-[#12b9bd] shadow" />
                  <div className="grid gap-4 md:grid-cols-[86px_1fr_170px]">
                    <div>
                      <div className="text-lg font-bold">{timeLabels[index] ?? item.time}</div>
                      <div className="mt-1 text-sm text-slate-500">{index === 0 ? "09:00" : index === 1 ? "12:00" : index === 2 ? "13:30" : "18:30"}</div>
                    </div>
                    <div>
                      <div className="text-lg font-bold">{item.name}</div>
                      <div className="mt-1 text-sm text-slate-500">{item.location}</div>
                      <div className="mt-3 flex flex-wrap gap-4 text-sm text-slate-500">
                        <span>停留 {item.duration}</span>
                        <span>{formatActivityCost(item.cost)}</span>
                      </div>
                      <div className="mt-3 text-sm text-slate-600">{item.description}</div>
                      <div className="mt-4 grid grid-cols-3 gap-3">
                        {["替换", "轻松点", "省钱点"].map((action) => {
                          const text = `Day ${currentDay?.day ?? selectedDay + 1} ${item.name}${action}`;
                          const active = selectedOptimizations.includes(text);
                          return (
                            <button
                              key={action}
                              onClick={() => toggleOptimization(text)}
                              className={`h-9 rounded-lg border text-sm font-semibold ${active ? "border-[#10b8bd] bg-cyan-50 text-[#0da8ad]" : "border-slate-200 text-[#0da8ad]"}`}
                            >
                              {action}
                            </button>
                          );
                        })}
                      </div>
                    </div>
                    <img src={index % 2 === 0 ? "https://images.unsplash.com/photo-1596176530529-78163a4f7af2?auto=format&fit=crop&w=280&q=80" : "https://images.unsplash.com/photo-1543353071-873f17a7a088?auto=format&fit=crop&w=280&q=80"} alt="" className="h-24 w-full rounded-xl object-cover" />
                  </div>
                </div>
              )) : (
                <div className="relative mb-5 rounded-2xl border border-slate-200 bg-white p-5 text-sm font-semibold text-slate-500 shadow-sm">
                  <div className="absolute -left-[43px] top-6 h-5 w-5 rounded-full border-4 border-white bg-[#12b9bd] shadow" />
                  暂无景点时段，建议重新优化补充景点。
                </div>
              )}
            </div>
          </div>

          <aside className="space-y-4">
            <RouteMapMock mapData={plan.map_data} />

            <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
              <div className="mb-4 flex items-center justify-between">
                <h3 className="font-bold">天气提醒</h3>
                <span className="text-xs text-slate-400">行程日期</span>
              </div>
              <div className="grid grid-cols-3 gap-3">
                {(plan.weather?.forecast ?? []).slice(0, 3).map((day) => (
                  <div key={day.date} className={`rounded-xl p-3 text-center ${isMissingWeather(day) ? "bg-slate-50 text-slate-500" : "bg-cyan-50"}`}>
                    <div className="text-xs text-slate-500">{day.date}</div>
                    <div className="mt-2 text-sm font-semibold">{weatherLabel(day.condition)}</div>
                    <div className="mt-1 font-bold">{weatherMeta(day)}</div>
                  </div>
                ))}
                {!plan.weather?.forecast?.length && (
                  <div className="col-span-3 rounded-xl bg-cyan-50 p-4 text-sm font-semibold text-slate-500">
                    天气数据待更新
                  </div>
                )}
              </div>
            </div>

            <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
              <div className="mb-4 flex items-center gap-2 font-bold"><Hotel className="h-5 w-5 text-[#0da8ad]" />住宿区域推荐</div>
              <div className="flex gap-4">
                <img src="https://images.unsplash.com/photo-1566073771259-6a8506099945?auto=format&fit=crop&w=220&q=80" alt="" className="h-24 w-32 rounded-xl object-cover" />
                <div>
                  <div className="font-bold">{hotel?.name || "湖滨商圈"}</div>
                  <p className="mt-1 text-sm leading-6 text-slate-500">{hotel?.address || "靠近核心景区，交通便利，餐饮购物选择多。"}</p>
                  <div className="mt-2 font-bold text-[#0da8ad]">{hotelCost ? `${hotelCost} / 晚` : "价格待查"}</div>
                </div>
              </div>
            </div>

            <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
              <div className="mb-4 flex items-center gap-2 font-bold"><Utensils className="h-5 w-5 text-[#0da8ad]" />餐饮安排</div>
              <div className="space-y-3">
                {meals.length ? meals.map((meal) => (
                  <div key={meal.id} className="rounded-xl bg-slate-50 p-3">
                    <div className="font-bold">{meal.name}</div>
                    <div className="mt-1 text-sm text-slate-500">{meal.time} · {meal.location}</div>
                  </div>
                )) : (
                  <div className="rounded-xl bg-slate-50 p-3 text-sm font-semibold text-slate-500">餐饮待补充</div>
                )}
              </div>
            </div>
          </aside>
        </div>
      </div>
    </section>
  );
}
