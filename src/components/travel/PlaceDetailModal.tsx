import { useEffect, useMemo, useState } from "react";
import { Clock, MapPin, Navigation, Receipt, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Activity, MapData, POI, SpotNote, TravelPlanResult } from "@/types";
import { RouteMap } from "@/components/travel/RouteMap";

interface PlaceDetailModalProps {
  plan: TravelPlanResult;
  initialPoi: POI;
  onClose: () => void;
}

interface PlaceEntry {
  key: string;
  name: string;
  address: string;
  description: string;
  tip?: string;
  time?: string;
  duration?: string;
  cost?: number;
  source?: string;
  poi: POI | null;
}

const allPois = (plan: TravelPlanResult) => [
  ...(plan.map_data?.attractions ?? []),
  ...(plan.map_data?.food ?? []),
  ...(plan.map_data?.hotels ?? []),
];

const normalizeName = (value: string) =>
  value
    .replace(/[（）()·\s]/g, "")
    .replace(/鼓浪屿|风景名胜区|景区|沙滩|港仔后/g, "")
    .trim();

const nameAliases = (name: string) => {
  const aliases = new Set([name, normalizeName(name)]);
  const pairs = [
    ["八卦楼", "风琴博物馆"],
    ["风琴博物馆", "八卦楼"],
    ["港仔后", "鼓浪屿沙滩"],
    ["鼓浪屿沙滩", "港仔后"],
    ["龙头路", "街心公园"],
    ["中国电影音乐馆", "电影音乐"],
    ["电影音乐", "中国电影音乐馆"],
    ["菽庄", "菽庄花园"],
    ["日光岩", "港仔后"],
  ];

  for (const [needle, alias] of pairs) {
    if (name.includes(needle)) aliases.add(alias);
  }

  return [...aliases].filter(Boolean);
};

const matchesName = (sourceName: string, targetName: string) => {
  const sourceAliases = nameAliases(sourceName);
  const targetAliases = nameAliases(targetName);
  return sourceAliases.some((source) =>
    targetAliases.some((target) => source.includes(target) || target.includes(source)),
  );
};

const findPoi = (plan: TravelPlanResult, name: string, fallback?: POI | null) => {
  if (fallback?.location) return fallback;
  return allPois(plan).find((poi) => {
    if (!poi.name) return false;
    return matchesName(name, poi.name);
  }) ?? fallback ?? null;
};

const poiFromActivity = (activity: Activity): POI | null => {
  if (!activity.coordinate) return null;
  return {
    id: activity.id,
    name: activity.name,
    type: activity.type,
    address: activity.location,
    location: activity.coordinate,
    source: activity.source,
  };
};

const poiFromSpotNote = (note: SpotNote): POI | null => {
  if (!note.location) return null;
  return {
    id: note.poi_id || note.name,
    name: note.name,
    type: "spot_note",
    address: note.address || "",
    location: note.location,
    source: note.source,
  };
};

const focusMapData = (plan: TravelPlanResult, poi: POI): MapData => ({
  destination: plan.destination,
  display_destination: plan.map_data?.display_destination,
  resolved_city: plan.map_data?.resolved_city,
  center: {
    formatted_address: poi.address,
    city: plan.map_data?.resolved_city || plan.destination,
    location: poi.location ?? undefined,
    source: poi.source,
  },
  attractions: poi.location ? [poi] : [],
  food: [],
  hotels: [],
  routes: [],
});

const guideSections = (entry: PlaceEntry | undefined, plan: TravelPlanResult) => {
  const destination = plan.map_data?.display_destination || plan.destination || "目的地";
  const routeText = plan.map_data?.route_advice?.find((item) => entry?.name && item.includes(entry.name))
    || plan.map_data?.route_advice?.[0]
    || `按当天路线顺序游览，减少在${destination}内来回折返。`;
  const avoidText = plan.map_data?.travel_tips?.avoidance?.[0]
    || "热门时段人流较多，优先保留现场排队、安检和步行缓冲。";
  const usefulTip = entry?.tip && !/^Day\s+\d+\s+·/.test(entry.tip) ? entry.tip : avoidText;
  const stayText = [
    entry?.time ? `建议时段：${entry.time}` : "",
    entry?.duration ? `停留：${entry.duration}` : "",
    Number(entry?.cost) > 0 ? `预计花费：¥${Math.round(Number(entry?.cost))}` : "",
  ].filter(Boolean).join("，") || "建议按现场人流调整停留时间，核心体验优先，不要为了打卡硬赶路。";

  return [
    {
      title: "游玩重点",
      text: entry?.description || `${entry?.name || destination}是当前路线里的重点停留点，适合结合地图位置安排前后景点。`,
    },
    { title: "停留建议", text: stayText },
    { title: "路线衔接", text: routeText },
    { title: "注意事项", text: usefulTip },
  ];
};

const buildEntries = (plan: TravelPlanResult): PlaceEntry[] => {
  const entries: PlaceEntry[] = [];
  const seen = new Set<string>();

  for (const day of plan.daily_plans ?? []) {
    for (const activity of day.activities ?? []) {
      const basePoi = poiFromActivity(activity);
      const poi = findPoi(plan, activity.name, basePoi);
      const key = `activity-${day.day}-${activity.id}`;
      if (seen.has(activity.name)) continue;
      seen.add(activity.name);
      entries.push({
        key,
        name: activity.name,
        address: poi?.address || activity.location,
        description: activity.description,
        tip: `Day ${day.day} · ${activity.time}`,
        time: activity.time,
        duration: activity.duration,
        cost: activity.cost,
        source: activity.source || poi?.source,
        poi,
      });
    }
  }

  for (const note of plan.map_data?.spot_notes ?? []) {
    const basePoi = poiFromSpotNote(note);
    const poi = findPoi(plan, note.name, basePoi);
    if (seen.has(note.name)) continue;
    seen.add(note.name);
    entries.push({
      key: `spot-${note.name}`,
      name: note.name,
      address: poi?.address || note.address || plan.destination,
      description: note.guide || note.highlight,
      tip: note.tip,
      source: note.source || poi?.source,
      poi,
    });
  }

  return entries;
};

export function PlaceDetailModal({ plan, initialPoi, onClose }: PlaceDetailModalProps) {
  const entries = useMemo(() => buildEntries(plan), [plan]);
  const initialEntry = useMemo(
    () => entries.find((item) => matchesName(item.name, initialPoi.name) || item.poi?.id === initialPoi.id) ?? entries[0],
    [entries, initialPoi],
  );
  const [selectedKey, setSelectedKey] = useState(initialEntry?.key ?? "");

  useEffect(() => {
    setSelectedKey(initialEntry?.key ?? "");
  }, [initialEntry]);

  const selected = entries.find((item) => item.key === selectedKey) ?? initialEntry;
  const selectedPoi = findPoi(plan, selected?.name ?? initialPoi.name, selected?.poi ?? initialPoi) ?? initialPoi;
  const canMap = Boolean(selectedPoi?.location);
  const sections = guideSections(selected, plan);

  return (
    <div className="fixed inset-0 z-50 bg-slate-950/55 p-4">
      <div className="mx-auto flex h-full max-w-[1480px] flex-col overflow-hidden rounded-2xl bg-white shadow-2xl">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 px-5 py-4">
          <div>
            <div className="flex items-center gap-2 text-2xl font-black">
              <MapPin className="h-6 w-6 text-[#0da8ad]" />
              {selected?.name || selectedPoi.name}
            </div>
            <div className="mt-1 text-sm font-medium text-slate-500">{selected?.address || selectedPoi.address || plan.destination}</div>
          </div>
          <Button variant="outline" onClick={onClose} className="h-10 rounded-xl px-4">
            <X className="h-4 w-4" />
            关闭
          </Button>
        </div>

        <div className="grid min-h-0 flex-1 gap-0 lg:grid-cols-[320px_minmax(0,1fr)_minmax(420px,0.9fr)]">
          <aside className="min-h-0 overflow-y-auto border-b border-slate-100 p-4 lg:border-b-0 lg:border-r">
            <div className="flex gap-2 overflow-x-auto pb-2 lg:block lg:space-y-2 lg:overflow-visible lg:pb-0">
              {entries.map((entry, index) => {
                const active = entry.key === selectedKey;
                return (
                  <button
                    key={entry.key}
                    onClick={() => setSelectedKey(entry.key)}
                    className={`min-w-[220px] rounded-xl border px-4 py-3 text-left transition lg:min-w-0 lg:w-full ${active ? "border-[#10b8bd] bg-cyan-50 text-[#0b7f84]" : "border-slate-200 bg-white text-slate-700 hover:border-[#10b8bd]"}`}
                  >
                    <div className="text-xs font-black text-slate-400">#{index + 1}</div>
                    <div className="mt-1 line-clamp-1 text-sm font-black">{entry.name}</div>
                    <div className="mt-1 line-clamp-1 text-xs font-semibold text-slate-500">{entry.address}</div>
                  </button>
                );
              })}
            </div>
          </aside>

          <main className="min-h-0 overflow-y-auto p-6">
            <div className="mb-4 flex flex-wrap gap-2">
              {selected?.time && <InfoPill icon={Clock} text={selected.time} />}
              {selected?.duration && <InfoPill icon={Navigation} text={selected.duration} />}
              {Number(selected?.cost) > 0 && <InfoPill icon={Receipt} text={`预计 ¥${Math.round(Number(selected?.cost))}`} />}
              <InfoPill icon={MapPin} text={canMap ? "高德定位可用" : "等待坐标回填"} />
            </div>

            <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
              <h3 className="text-xl font-black">{selected?.name || selectedPoi.name}</h3>
              <p className="mt-4 text-sm font-semibold leading-7 text-slate-700">{selected?.description || "暂无攻略正文。"}</p>
              {selected?.tip && (
                <p className="mt-4 rounded-xl bg-cyan-50 px-4 py-3 text-sm font-semibold leading-7 text-[#0b7f84]">{selected.tip}</p>
              )}
              <div className="mt-5 grid gap-3 text-sm font-semibold text-slate-600 sm:grid-cols-2">
                <div className="rounded-xl bg-slate-50 px-4 py-3">地址：{selected?.address || selectedPoi.address || plan.destination}</div>
                <div className="rounded-xl bg-slate-50 px-4 py-3">来源：{selected?.source || selectedPoi.source || "行程规划"}</div>
              </div>
            </article>

            <section className="mt-5 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
              <h3 className="text-xl font-black">正文攻略</h3>
              <div className="mt-4 grid gap-3 md:grid-cols-2">
                {sections.map((item) => (
                  <div key={item.title} className="rounded-xl bg-slate-50 px-4 py-3">
                    <div className="text-sm font-black text-slate-950">{item.title}</div>
                    <div className="mt-2 text-sm font-semibold leading-7 text-slate-600">{item.text}</div>
                  </div>
                ))}
              </div>
              {!!plan.map_data?.route_advice?.length && (
                <div className="mt-4 flex flex-wrap gap-2">
                  {plan.map_data.route_advice.slice(0, 4).map((item) => (
                    <span key={item} className="rounded-full bg-cyan-50 px-4 py-2 text-sm font-semibold leading-6 text-[#0b7f84]">
                      {item}
                    </span>
                  ))}
                </div>
              )}
            </section>
          </main>

          <aside className="min-h-[420px] border-t border-slate-100 p-4 lg:border-l lg:border-t-0">
            <RouteMap mapData={focusMapData(plan, selectedPoi)} heightClass="h-full min-h-[560px]" previewLabel="地点地图" />
          </aside>
        </div>
      </div>
    </div>
  );
}

function InfoPill({ icon: Icon, text }: { icon: typeof Clock; text: string }) {
  return (
    <span className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-2 text-sm font-bold text-slate-600">
      <Icon className="h-4 w-4 text-[#0da8ad]" />
      {text}
    </span>
  );
}
