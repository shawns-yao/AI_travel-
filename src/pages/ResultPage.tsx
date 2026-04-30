import { ReactNode, useMemo, useState } from "react";
import { AlertTriangle, ArrowLeft, BookOpen, Calendar, CheckCircle2, Download, Edit3, Hotel, Luggage, MapPin, Save, Share2, Utensils, Users, Wallet } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Activity, DailyPlan, MapData, POI, TravelPlanResult } from "@/types";
import { RouteMap } from "@/components/travel/RouteMap";
import { PlaceDetailModal } from "@/components/travel/PlaceDetailModal";
import { activityImage, hotelImage } from "@/lib/travelMedia";
import { activityDescriptionForCard, isTransferActivity } from "@/lib/travelActivities";

interface ResultPageProps {
  plan: TravelPlanResult;
  onSave?: (plan: TravelPlanResult) => void;
  onEdit?: (changes?: string[], dayIndex?: number) => void;
}

const timeLabels = ["上午", "下午", "傍晚", "晚上"];
const proseTimes = ["8:00-12:00", "13:30-17:00", "17:00-19:00", "19:00-20:30"];

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
  if (condition === "no_data") return "超出 7 日预报";
  if (condition === "unknown") return "暂无实时天气";
  return condition || "暂无实时天气";
};

const weatherMeta = (day: { condition?: string; temp_high?: number; temp_low?: number; source?: string }) => {
  if (day.condition === "no_data") return "出行日期超出范围";
  if (isMissingWeather(day)) return "接口未返回";
  return `${day.temp_low}° / ${day.temp_high}°`;
};

const cleanHotelCost = (cost?: string) => {
  const value = String(cost || "").trim();
  if (!value || value === "[]" || value === "{}" || value === "0") return "";
  const normalized = value.replace(/^¥?\s*/, "");
  return normalized ? `¥${normalized}` : "";
};

const formatActivityCost = (cost?: number) => {
  if (!Number.isFinite(cost) || Number(cost) <= 0) return "";
  return `预计 ¥${Math.round(Number(cost))}`;
};

const hasUserBudget = (plan: TravelPlanResult) =>
  Number(plan.budget) > 0
  && (plan.budget_source === "user" || plan.budget_breakdown?.budget_source === "user" || plan.budget_breakdown?.estimated === false);

const allPois = (plan: TravelPlanResult) => [
  ...(plan.map_data?.attractions ?? []),
  ...(plan.map_data?.food ?? []),
  ...(plan.map_data?.hotels ?? []),
];

const attractionPois = (plan: TravelPlanResult) => plan.map_data?.attractions ?? [];

const textOfActivity = (activity: Activity) =>
  `${activity.name} ${activity.location} ${activity.description}`.replace(/\s+/g, "");

const matchPoiByActivity = (plan: TravelPlanResult, activity: Activity) => {
  const text = textOfActivity(activity);
  const stopWords = ["泉州", "厦门", "鼓浪屿", "登岛", "返程", "动车", "高铁", "码头", "酒店", "民宿", "客栈"];
  const keywords = ["皓月园", "长寿园", "电影音乐", "日光岩", "菽庄", "港仔后", "龙头路", "风琴博物馆", "沙坡尾", "南普陀"];
  return attractionPois(plan).find((poi) => {
    if (!poi.name || !poi.location) return false;
    if (poi.name.length < 3 || stopWords.includes(poi.name)) return false;
    return text.includes(poi.name)
      || poi.name.includes(activity.name)
      || keywords.some((keyword) => text.includes(keyword) && poi.name.includes(keyword));
  });
};

const poiForActivity = (plan: TravelPlanResult, activity: Activity): POI | null => {
  if (activity.coordinate) {
    return {
      id: activity.id,
      name: activity.name,
      type: activity.type,
      address: activity.location,
      location: activity.coordinate,
      source: activity.source,
      photo: activity.photo || matchPoiByActivity(plan, activity)?.photo,
    };
  }
  const matched = matchPoiByActivity(plan, activity);
  return matched ?? {
    id: activity.id,
    name: activity.name,
    type: activity.type,
    address: activity.location,
    location: null,
    source: activity.source,
    photo: activity.photo,
  };
};

const defaultTips = (plan: TravelPlanResult) => ({
  pre_trip: ["提前确认景区开放时间和预约规则", "准备舒适步行鞋", "保留雨具和移动电源"],
  food: (plan.map_data?.food ?? []).slice(0, 3).map((item) => `${item.name}${item.address ? ` · ${item.address}` : ""}`),
  hotel: (plan.map_data?.hotels ?? []).slice(0, 3).map((item) => `${item.name}${item.address ? ` · ${item.address}` : ""}`),
  avoidance: ["热门景区尽量错峰进入"],
  backup: [],
});

const cleanInfoText = (value: string) =>
  String(value || "")
    .replace(/[。；;]+$/g, "")
    .replace(/\s+/g, " ")
    .trim();

const uniqueInfoList = (values?: string[], fallback: string[] = [], limit = 4) => {
  const seen = new Set<string>();
  return [...(values ?? []), ...fallback]
    .map(cleanInfoText)
    .filter((item) => {
      if (!item) return false;
      const key = item.replace(/[，,、：:。“”"「」]/g, "");
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    })
    .slice(0, limit);
};

const travelTips = (plan: TravelPlanResult) => {
  const tips = plan.map_data?.travel_tips;
  const fallback = defaultTips(plan);
  return {
    pre_trip: uniqueInfoList(tips?.pre_trip, fallback.pre_trip, 4),
    food: uniqueInfoList(tips?.food, fallback.food, 4),
    hotel: uniqueInfoList(tips?.hotel, fallback.hotel, 3),
    avoidance: uniqueInfoList(tips?.avoidance, fallback.avoidance, 4),
    backup: uniqueInfoList(tips?.backup, fallback.backup, 4),
  };
};

const spotNotes = (plan: TravelPlanResult) => plan.map_data?.spot_notes ?? [];
const routeAdvice = (plan: TravelPlanResult) => plan.map_data?.route_advice ?? [];
const strategyTags = (plan: TravelPlanResult) => plan.variant_profile?.strategy_tags ?? plan.map_data?.variant_profile?.strategy_tags ?? [];
const dayTitle = (plan: TravelPlanResult, day: { day: number; notes?: string }) => {
  const destination = plan.map_data?.display_destination || plan.destination || "目的地";
  const noteTitle = day.notes?.includes("·") ? day.notes.split(/[，。]/)[0] : "";
  if (destination.includes("鼓浪屿")) {
    return "厦门 · 鼓浪屿的琴岛时光";
  }
  if (noteTitle && (noteTitle.includes(destination) || destination.includes(noteTitle.split("·")[0]?.trim()))) return noteTitle;
  return `${destination} · 第 ${day.day} 天`;
};

const cleanDayNotes = (plan: TravelPlanResult, notes?: string) => {
  const destination = plan.map_data?.display_destination || plan.destination || "";
  const value = String(notes || "").trim();
  if (!value) return "";
  if (destination.includes("鼓浪屿")) {
    return value.replace(/^泉州\s*·[^，。]*[，。]?/, "").trim();
  }
  return value;
};

const proseIntro = (plan: TravelPlanResult, day: { day: number; notes?: string }) => {
  const notes = cleanDayNotes(plan, day.notes);
  if (notes) return notes;
  const destination = plan.map_data?.display_destination || plan.destination || "目的地";
  return day.day === 1 ? `抵达${destination}后，先按轻松节奏进入城市核心区。` : `继续围绕${destination}展开当天路线。`;
};

const mapDataForDay = (plan: TravelPlanResult, day?: { activities?: Activity[] }): MapData | null => {
  const pointsFromActivities = (day?.activities ?? [])
    .filter((activity) => !isTransferActivity(activity))
    .map((activity) => activity.coordinate ? poiForActivity(plan, activity) : matchPoiByActivity(plan, activity))
    .filter((poi): poi is POI => Boolean(poi?.location));
  const seen = new Set<string>();
  const points = [...pointsFromActivities, ...attractionPois(plan)]
    .filter((poi) => {
      if (!poi.location) return false;
      const key = poi.id || poi.name;
      if (!key || seen.has(key)) return false;
      seen.add(key);
      return true;
    })
    .slice(0, 8);
  return {
    destination: plan.destination,
    display_destination: plan.map_data?.display_destination,
    resolved_city: plan.map_data?.resolved_city,
    center: {
      formatted_address: points[0]?.address || plan.map_data?.center?.formatted_address,
      city: plan.map_data?.resolved_city || plan.destination,
      location: points[0]?.location ?? plan.map_data?.center?.location,
      source: points[0]?.source || plan.map_data?.center?.source,
    },
    attractions: points,
    food: [],
    hotels: [],
    routes: [],
  };
};

const firstVisibleActivityName = (day: { activities?: Activity[] }) =>
  day.activities?.find((activity) => !isTransferActivity(activity))?.name || "城市轻松游";

export function ResultPage({ plan, onSave, onEdit }: ResultPageProps) {
  const [selectedDay, setSelectedDay] = useState(0);
  const [saved, setSaved] = useState(false);
  const [guideDay, setGuideDay] = useState<number | null>(null);
  const currentDay = plan.daily_plans?.[selectedDay] ?? plan.daily_plans?.[0];
  const dateRange = formatDateRange(plan.start_date, plan.duration || 3);
  const peopleCount = inferPeopleCount(plan.preferences ?? []);
  const hotel = plan.map_data?.hotels?.[0];
  const hotelCost = cleanHotelCost(hotel?.cost);
  const activities = useMemo(() => (currentDay?.activities ?? []).filter((activity) => !isTransferActivity(activity)).slice(0, 4), [currentDay]);
  const tips = useMemo(() => travelTips(plan), [plan]);
  const spots = useMemo(() => spotNotes(plan), [plan]);
  const routes = useMemo(() => routeAdvice(plan), [plan]);
  const strategy = useMemo(() => strategyTags(plan), [plan]);
  const selectedDayMap = useMemo(() => mapDataForDay(plan, currentDay), [plan, currentDay]);
  const [selectedPoi, setSelectedPoi] = useState<POI | null>(null);
  const openActivity = (activity: Activity) => {
    const poi = poiForActivity(plan, activity);
    if (poi) setSelectedPoi(poi);
  };

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
    const text = `${plan.destination}${plan.duration}日旅行方案`;
    if (navigator.share) {
      await navigator.share({ title: "AI Travel 行程", text });
    } else {
      await navigator.clipboard.writeText(text);
    }
  };
  if (guideDay !== null) {
    const day = plan.daily_plans?.[guideDay] ?? plan.daily_plans?.[0];
    return <GuideDayPage plan={plan} day={day} onBack={() => setGuideDay(null)} onOpenPlace={openActivity} />;
  }

  return (
    <section className="min-h-[calc(100vh-68px)] bg-white">
      <div className="mx-auto max-w-[1500px] px-8 py-10">
        <div className="mb-7 flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <h1 className="text-4xl font-black tracking-normal">{plan.destination || "杭州"} {plan.duration || 3} 日轻松游</h1>
            <div className="mt-4 flex flex-wrap items-center gap-6 text-sm font-medium text-slate-600">
              <span className="flex items-center gap-2"><Calendar className="h-4 w-4 text-[#0da8ad]" />{dateRange}</span>
              <span className="flex items-center gap-2"><Users className="h-4 w-4 text-[#0da8ad]" />{peopleCount}</span>
              {hasUserBudget(plan) && <span className="flex items-center gap-2"><Wallet className="h-4 w-4 text-[#0da8ad]" />预算约 {plan.budget} 元</span>}
            </div>
            {!!strategy.length && (
              <div className="mt-3 flex flex-wrap gap-2">
                {strategy.map((item) => (
                  <span key={item} className="rounded-full bg-cyan-50 px-3 py-1.5 text-xs font-black text-[#0b7f84]">
                    {item}
                  </span>
                ))}
              </div>
            )}
          </div>
          <div className="flex gap-3">
            <Button variant="outline" onClick={() => onEdit?.([], selectedDay)} className="rounded-xl px-6">
              <Edit3 className="h-4 w-4" />
              编辑
            </Button>
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

        <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_520px]">
          <div className="min-w-0 space-y-5">
          <aside className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {(plan.daily_plans?.length ? plan.daily_plans : [{ day: 1, activities: [], meals: [] }]).map((day, index) => {
              const dayImage = activityImage(plan, day.activities?.find((activity) => !isTransferActivity(activity)), index);
              return (
              <button
                key={day.day}
                onClick={() => setSelectedDay(index)}
                className={`flex w-full gap-4 rounded-xl border p-3 text-left ${index === selectedDay ? "border-[#10b8bd] bg-cyan-50" : "border-slate-200 bg-white"}`}
              >
                <div className="flex h-16 w-16 items-center justify-center overflow-hidden rounded-lg bg-cyan-50 text-[#0da8ad]">
                  {dayImage ? <img src={dayImage} alt="" className="h-full w-full object-cover" /> : <MapPin className="h-5 w-5" />}
                </div>
                <div>
                  <div className="font-bold">Day {day.day}</div>
                  <div className="mt-1 text-sm leading-5 text-slate-600">{firstVisibleActivityName(day)}</div>
                </div>
              </button>
              );
            })}
          </aside>

          <div>
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
              <div className="text-2xl font-black">Day {currentDay?.day ?? 1} {dayTitle(plan, currentDay ?? { day: 1 })}</div>
              <Button onClick={() => setGuideDay(selectedDay)} className="h-11 rounded-xl bg-[#10b8bd] px-5 text-white hover:bg-[#0ca8ad]">
                <BookOpen className="h-4 w-4" />
                攻略
              </Button>
            </div>
            {cleanDayNotes(plan, currentDay?.notes) && (
              <div className="mb-4 rounded-2xl border border-cyan-100 bg-cyan-50/70 p-4 text-sm font-semibold leading-7 text-slate-700">
                {cleanDayNotes(plan, currentDay?.notes)}
              </div>
            )}
            <div className="relative border-l border-dashed border-[#12b9bd]/45 pl-8">
              {activities.length ? activities.map((item, index) => {
                const itemCost = formatActivityCost(item.cost);
                const image = activityImage(plan, item, index);
                return (
                <div key={item.id} className="relative mb-5 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
                  <div className="absolute -left-[43px] top-6 h-5 w-5 rounded-full border-4 border-white bg-[#12b9bd] shadow" />
                  <div className="space-y-4">
                    <div className="flex flex-wrap items-start gap-5">
                    <div className="w-24 shrink-0">
                      <div className="text-xl font-black">{timeLabels[index] ?? item.time}</div>
                      <div className="mt-1 text-sm text-slate-500">{index === 0 ? "09:00" : index === 1 ? "12:00" : index === 2 ? "13:30" : "18:30"}</div>
                    </div>
                    <div className="min-w-[260px] flex-1">
                      <div className="text-xl font-black leading-snug break-words">{item.name}</div>
                      <div className="mt-1 text-sm text-slate-500">{item.location}</div>
                      <div className="mt-3 flex flex-wrap gap-2 text-sm font-semibold text-slate-600">
                        <span className="rounded-full border border-slate-200 px-3 py-1.5">停留 {item.duration}</span>
                        {itemCost && <span className="rounded-full border border-slate-200 px-3 py-1.5">{itemCost}</span>}
                      </div>
                    </div>
                    </div>
                    <div className="rounded-xl bg-slate-50 px-5 py-4 text-sm font-semibold leading-7 text-slate-600">{activityDescriptionForCard(item)}</div>
                    {image && (
                      <img
                        src={image}
                        alt=""
                        className="h-48 w-full rounded-xl object-cover"
                      />
                    )}
                    <div className="flex flex-wrap gap-2">
                        <button
                          onClick={() => {
                            openActivity(item);
                          }}
                          disabled={!poiForActivity(plan, item)}
                          className="rounded-full border border-slate-200 px-3 py-2 text-sm font-bold text-[#0da8ad] hover:border-[#10b8bd] hover:bg-cyan-50 disabled:text-slate-300 disabled:hover:border-slate-200 disabled:hover:bg-transparent"
                        >
                          地图
                        </button>
                        {["替换", "轻松点", "省钱点"].map((action) => {
                          const text = `Day ${currentDay?.day ?? selectedDay + 1} ${item.name}${action}`;
                          return (
                            <button
                              key={action}
                              onClick={() => onEdit?.([text], selectedDay)}
                              className="rounded-full border border-slate-200 px-3 py-2 text-sm font-bold text-[#0da8ad] hover:border-[#10b8bd] hover:bg-cyan-50"
                            >
                              {action}
                            </button>
                          );
                        })}
                    </div>
                  </div>
                </div>
                );
              }) : (
                <div className="relative mb-5 rounded-2xl border border-slate-200 bg-white p-5 text-sm font-semibold text-slate-500 shadow-sm">
                  <div className="absolute -left-[43px] top-6 h-5 w-5 rounded-full border-4 border-white bg-[#12b9bd] shadow" />
                  暂无景点时段，建议重新优化补充景点。
                </div>
              )}
            </div>
          </div>
          </div>

          <aside className="space-y-4 xl:sticky xl:top-24 xl:self-start">
            <RouteMap mapData={selectedDayMap} heightClass="min-h-[520px]" previewLabel={`Day ${currentDay?.day ?? 1} 路线`} />
            <WeatherCard plan={plan} />
            <HotelCard plan={plan} hotel={hotel} hotelCost={hotelCost} />
          </aside>
        </div>

        {!!spots.length && (
          <section className="mt-8 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="mb-4 flex items-center gap-2 text-xl font-black"><MapPin className="h-5 w-5 text-[#0da8ad]" />景点与路线</div>
            <div className="grid gap-3 lg:grid-cols-2 xl:grid-cols-3">
              {spots.map((item, index) => (
                <button
                  key={item.name}
                  onClick={() => {
                    const poi = allPois(plan).find((p) => p.name && (p.name.includes(item.name) || item.name.includes(p.name))) ?? {
                      id: item.poi_id || item.name,
                      name: item.name,
                      type: "spot_note",
                      address: item.address || plan.destination,
                      location: item.location ?? null,
                      source: item.source,
                    };
                    setSelectedPoi(poi);
                  }}
                  className="rounded-2xl bg-slate-50 p-4 text-left text-sm font-semibold leading-6 text-slate-600 hover:bg-cyan-50"
                >
                  <div className="mb-1 text-base font-black text-slate-950">{index + 1}. {item.name}</div>
                  <div>{item.highlight}</div>
                  <div className="mt-2 text-[#0da8ad]">{item.tip}</div>
                </button>
              ))}
            </div>
            {!!routes.length && (
              <div className="mt-4 flex flex-wrap gap-2">
                {routes.map((item) => <InfoItem key={item} text={item} />)}
              </div>
            )}
          </section>
        )}

        <div className="mt-6 grid items-stretch gap-5 lg:grid-cols-3">
          <InfoPanel title="行前准备" icon={Luggage}>
            {tips.pre_trip.map((item) => <InfoItem key={item} text={item} />)}
          </InfoPanel>

          <InfoPanel title="美食清单" icon={Utensils}>
            {(tips.food.length ? tips.food : ["美食信息待工具链补充"]).map((item) => <InfoItem key={item} text={item} />)}
          </InfoPanel>

          <InfoPanel title="避坑提醒" icon={AlertTriangle}>
            {tips.avoidance.map((item) => <InfoItem key={item} text={item} />)}
          </InfoPanel>
        </div>
      </div>
      {selectedPoi && <PlaceDetailModal plan={plan} initialPoi={selectedPoi} onClose={() => setSelectedPoi(null)} />}
    </section>
  );
}

function InfoPanel({ title, icon: Icon, children }: { title: string; icon: typeof Luggage; children: ReactNode }) {
  return (
    <div className="flex h-full min-h-[260px] flex-col rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="mb-4 flex items-center gap-2 font-bold"><Icon className="h-5 w-5 text-[#0da8ad]" />{title}</div>
      <div className="flex flex-1 content-start flex-wrap gap-2">{children}</div>
    </div>
  );
}

function WeatherCard({ plan }: { plan: TravelPlanResult }) {
  return (
    <div className="h-fit rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
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
            未获取到天气数据
          </div>
        )}
      </div>
    </div>
  );
}

function HotelCard({ plan, hotel, hotelCost }: { plan: TravelPlanResult; hotel?: POI; hotelCost: string }) {
  const image = hotelImage(plan, hotel);
  return (
    <div className="h-fit rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="mb-4 flex items-center gap-2 font-bold"><Hotel className="h-5 w-5 text-[#0da8ad]" />住宿区域推荐</div>
      <div className="flex gap-4">
        {image && <img src={image} alt="" className="h-24 w-32 rounded-xl object-cover" />}
        <div>
          <div className="font-bold">{hotel?.name || "住宿区域待推荐"}</div>
          <p className="mt-1 text-sm leading-6 text-slate-500">{hotel?.address || "靠近核心景区和公共交通优先。"}</p>
          <div className="mt-2 font-bold text-[#0da8ad]">{hotelCost ? `${hotelCost} / 晚` : "价格待查"}</div>
        </div>
      </div>
    </div>
  );
}

function InfoItem({ text }: { text: string }) {
  return <div className="rounded-full bg-slate-50 px-4 py-2 text-sm font-semibold leading-6 text-slate-600">{text}</div>;
}

function GuideDayPage({
  plan,
  day,
  onBack,
  onOpenPlace,
}: {
  plan: TravelPlanResult;
  day?: DailyPlan;
  onBack: () => void;
  onOpenPlace: (activity: Activity) => void;
}) {
  if (!day) return null;
  const dinner = (day.meals ?? []).find((meal) => meal.type === "dinner") ?? day.meals?.[0];

  return (
    <section className="min-h-[calc(100vh-68px)] bg-white">
      <div className="mx-auto max-w-[1280px] px-8 py-10">
        <Button variant="outline" onClick={onBack} className="mb-6 h-11 rounded-xl px-5">
          <ArrowLeft className="h-4 w-4" />
          返回行程
        </Button>
        <article className="rounded-2xl border border-slate-200 bg-white p-8 shadow-sm">
          <h1 className="text-3xl font-black">Day {day.day}: {dayTitle(plan, day)}</h1>
          <p className="mt-6 text-base font-semibold leading-8 text-slate-600">{proseIntro(plan, day)}</p>
          <div className="mt-8 space-y-5">
            {(day.activities ?? []).slice(0, 4).map((activity, index) => (
              <p key={activity.id} className="text-base font-medium leading-8 text-slate-700">
                <span className="font-black text-slate-950">{timeLabels[index] ?? activity.time}（{proseTimes[index] ?? activity.duration}）：</span>
                <button onClick={() => onOpenPlace(activity)} className="font-black text-[#0b7f84] hover:underline">
                  {activity.name}
                </button>
                。{activity.description}
              </p>
            ))}
            {dinner && (
              <p className="text-base font-medium leading-8 text-slate-700">
                <span className="font-black text-slate-950">晚餐：</span>
                {dinner.name}，位置在{dinner.location}，适合把当天路线收在附近，少折返。
              </p>
            )}
          </div>
        </article>
      </div>
    </section>
  );
}
