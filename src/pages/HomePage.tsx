import { ComponentType, useEffect, useState } from "react";
import { Calendar, MapPin, Sparkles, Users, Wallet, Utensils, Mountain, Footprints, Building2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScenicBackdrop } from "@/components/travel/ScenicBackdrop";

interface HomePageProps {
  query: string;
  isRunning: boolean;
  onQueryChange: (value: string) => void;
  onSubmit: (queryOverride?: string) => void;
  onQuickPlan: (query: string) => void;
}

const chips = [
  { label: "轻松游", icon: Sparkles },
  { label: "美食优先", icon: Utensils },
  { label: "父母同行", icon: Users },
  { label: "自然风光", icon: Mountain },
  { label: "少走路", icon: Footprints },
  { label: "博物馆", icon: Building2 },
];

const destinations = [
  {
    city: "杭州",
    province: "浙江",
    budget: "¥3,200",
    desc: "西湖如画，诗意江南，适合放松身心的慢节奏旅行。",
    image: "https://images.unsplash.com/photo-1596176530529-78163a4f7af2?auto=format&fit=crop&w=900&q=80",
  },
  {
    city: "成都",
    province: "四川",
    budget: "¥2,800",
    desc: "美食之都，慢生活节奏，熊猫基地不容错过。",
    image: "https://images.unsplash.com/photo-1532629345422-7515f3d16bb6?auto=format&fit=crop&w=900&q=80",
  },
  {
    city: "青岛",
    province: "山东",
    budget: "¥2,600",
    desc: "海风拂面，红瓦绿树，啤酒与海鲜的完美搭配。",
    image: "https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?auto=format&fit=crop&w=900&q=80",
  },
];

const cityNames = [
  "北京", "上海", "广州", "深圳", "杭州", "成都", "重庆", "西安", "南京", "苏州", "厦门", "青岛", "大理", "丽江", "三亚",
  "长沙", "武汉", "天津", "石家庄", "洛阳", "郑州", "昆明", "贵阳", "哈尔滨", "长春", "沈阳", "呼和浩特", "银川", "兰州",
  "西宁", "拉萨", "乌鲁木齐", "桂林", "南宁", "福州", "泉州", "宁波", "无锡", "扬州", "黄山", "婺源", "张家界",
];

const placeNames = ["鼓浪屿", ...cityNames];
const cnNumbers: Record<string, string> = { 一: "1", 二: "2", 两: "2", 三: "3", 四: "4", 五: "5", 六: "6", 七: "7", 八: "8", 九: "9", 十: "10" };

const nextHolidayDate = (month: number, day: number) => {
  const now = new Date();
  let year = now.getFullYear();
  const cutoff = new Date(year, month - 1, day + 7);
  if (now > cutoff) year += 1;
  return `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
};

const cleanPlace = (value: string) =>
  value
    .replace(/^(去|到|玩|游|主要|重点|主打|核心|最想|必须|一定)+/, "")
    .replace(/[玩旅游旅行出行度假]/g, "")
    .trim();

const findKnownPlace = (value: string) => placeNames.find((name) => value.includes(name));

const parseTripQuery = (text: string) => {
  const patch: Partial<{ departure: string; destination: string; startDate: string; duration: string; people: string; budget: string }> = {};
  const routeMatch = text.match(/([^，,。.；;\s（）()]+)\s*(?:-|—|–|到|至|→)\s*([^，,。.；;\s（）()]+)(?:[（(]|，|,|。|；|;|\s|$)/);
  if (routeMatch) {
    const departure = findKnownPlace(routeMatch[1]) || cleanPlace(routeMatch[1]);
    const destination = findKnownPlace(routeMatch[2]) || cleanPlace(routeMatch[2]);
    if (departure) patch.departure = departure;
    if (destination && destination !== departure) patch.destination = destination;
  }

  const focusMatch = text.match(/[（(][^）)]*(?:主要|重点|主打|核心|最想|必须|一定)(?:去|玩|游)?([^）)，,。.；;\s]+)[）)]/)
    || text.match(/(?:主要|重点|主打|核心|最想|必须|一定)(?:去|玩|游)?([^，,。.；;\s）)]+)/);
  if (focusMatch?.[1]) {
    const focused = findKnownPlace(focusMatch[1]) || cleanPlace(focusMatch[1]);
    if (focused) patch.destination = focused;
  }

  const destinationMatch = text.match(/(?:去|到)([^，,。.；;\s]+?)(?:玩|旅游|旅行|出行|度假|三天|两天|一天|\d+\s*天|[一二两三四五六七八九十]天|$)/);
  if (!patch.destination && destinationMatch?.[1]) {
    const city = findKnownPlace(destinationMatch[1]) || destinationMatch[1];
    patch.destination = cleanPlace(city);
  } else if (!patch.destination) {
    const city = placeNames.find((name) => text.includes(name));
    if (city) patch.destination = city;
  }

  const departureMatch = text.match(/(?:从|出发地[:：]?)([^，,。.；;\s]+?)(?:出发|到|去|$)/);
  if (departureMatch?.[1]) {
    const city = findKnownPlace(departureMatch[1]) || departureMatch[1];
    if (city && city !== patch.destination) patch.departure = city;
  }

  const digitDays = text.match(/(\d+)\s*[天日]/);
  const cnDays = Object.entries(cnNumbers).find(([word]) => text.includes(`${word}天`) || text.includes(`${word}日`));
  if (digitDays?.[1]) patch.duration = digitDays[1];
  else if (cnDays) patch.duration = cnDays[1];

  const peopleMatch = text.match(/(\d+)\s*(?:人|位|个大人|个朋友)/);
  if (peopleMatch?.[1]) {
    patch.people = peopleMatch[1];
  } else if (/父母同行|爸妈|父母/.test(text)) {
    patch.people = "3";
  } else if (/情侣|两个人|两人/.test(text)) {
    patch.people = "2";
  }

  const budgetMatch = text.match(/预算\s*(?:约|大概|共)?\s*(\d+(?:\.\d+)?)\s*(万|千|k|K)?/);
  if (budgetMatch?.[1]) {
    const raw = Number(budgetMatch[1]);
    const unit = budgetMatch[2];
    patch.budget = String(Math.round(unit === "万" ? raw * 10000 : unit === "千" || unit === "k" || unit === "K" ? raw * 1000 : raw));
  }

  const dateMatch = text.match(/(20\d{2})[-/.年](\d{1,2})[-/.月](\d{1,2})日?/);
  if (dateMatch) {
    const [, year, month, day] = dateMatch;
    patch.startDate = `${year}-${month.padStart(2, "0")}-${day.padStart(2, "0")}`;
  } else if (/五一|劳动节/.test(text)) {
    patch.startDate = nextHolidayDate(5, 1);
  }

  return patch;
};

export function HomePage({ query, isRunning, onQueryChange, onSubmit, onQuickPlan }: HomePageProps) {
  const [draft, setDraft] = useState({
    departure: "北京",
    destination: "杭州",
    startDate: "",
    duration: "3",
    people: "1",
    budget: "",
  });

  useEffect(() => {
    if (!query.trim()) return;
    const patch = parseTripQuery(query);
    if (Object.keys(patch).length) {
      setDraft((current) => ({ ...current, ...patch }));
    }
  }, [query]);

  const updateDraft = (key: keyof typeof draft, value: string) => {
    setDraft((current) => ({ ...current, [key]: value }));
  };

  const updateQuery = (value: string) => {
    onQueryChange(value);
    const patch = parseTripQuery(value);
    if (Object.keys(patch).length) {
      setDraft((current) => ({ ...current, ...patch }));
    }
  };

  const composeQuery = () =>
    [
      query.trim(),
      draft.departure ? `出发地：${draft.departure}` : "",
      draft.destination ? `目的地：${draft.destination}` : "",
      draft.startDate ? `出发日期：${draft.startDate}` : "",
      draft.duration ? `天数：${draft.duration}天` : "",
      draft.people ? `人数：${draft.people}人` : "",
      draft.budget ? `预算：${draft.budget}元` : "预算：未填写，请根据目的地、人数和天数估算",
    ].filter(Boolean).join("，");

  const submit = () => onSubmit(composeQuery());

  return (
    <section className="relative min-h-[calc(100vh-68px)] overflow-hidden">
      <ScenicBackdrop />
      <div className="relative mx-auto max-w-[1320px] px-8 py-10">
        <div className="mx-auto max-w-4xl text-center">
          <h1 className="text-[58px] font-black leading-tight tracking-normal text-slate-950">想去哪玩？</h1>
          <p className="mt-3 text-xl font-medium text-slate-600">一句话生成你的专属旅行计划</p>
        </div>

        <div className="mx-auto mt-10 max-w-[840px] rounded-2xl border border-slate-200 bg-white/88 p-3 shadow-xl shadow-cyan-100/50 backdrop-blur">
          <div className="flex gap-3">
            <Input
              value={query}
              onChange={(e) => updateQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") submit();
              }}
              className="h-14 flex-1 border-0 bg-transparent px-5 text-base shadow-none focus-visible:ring-0"
              placeholder="比如：我和爸妈五一去杭州三天，不想太累，预算 4000"
            />
            <Button
              onClick={submit}
              disabled={isRunning || !composeQuery().trim()}
              className="h-14 rounded-full bg-[#10b8bd] px-9 text-base font-bold text-white shadow-lg shadow-cyan-200 hover:bg-[#0ca8ad]"
            >
              <Sparkles className="h-5 w-5" />
              开始规划
            </Button>
          </div>
        </div>

        <div className="mx-auto mt-5 grid max-w-[1220px] grid-cols-2 gap-3 rounded-2xl border border-slate-200 bg-white/80 p-2 shadow-lg shadow-cyan-100/40 backdrop-blur md:grid-cols-3 xl:grid-cols-6">
          <FilterField label="出发地" icon={MapPin} value={draft.departure} onChange={(value) => updateDraft("departure", value)} />
          <FilterField label="目的地" icon={MapPin} value={draft.destination} onChange={(value) => updateDraft("destination", value)} />
          <FilterField label="日期" icon={Calendar} type="date" value={draft.startDate} onChange={(value) => updateDraft("startDate", value)} />
          <FilterField label="天数" icon={Calendar} value={draft.duration} suffix="天" onChange={(value) => updateDraft("duration", value.replace(/\D/g, ""))} />
          <FilterField label="人数" icon={Users} value={draft.people} suffix="人" onChange={(value) => updateDraft("people", value.replace(/\D/g, ""))} />
          <FilterField label="预算" icon={Wallet} value={draft.budget} suffix="元" placeholder="可不填" onChange={(value) => updateDraft("budget", value.replace(/\D/g, ""))} />
        </div>

        <div className="mx-auto mt-5 flex max-w-4xl flex-wrap justify-center gap-3">
          {chips.map((chip) => {
            const Icon = chip.icon;
            return (
              <button
                key={chip.label}
                type="button"
                onClick={() => updateQuery(query.includes(chip.label) ? query : `${query}，${chip.label}`)}
                className="flex h-11 items-center gap-2 rounded-full border border-cyan-100 bg-white/75 px-5 text-sm font-semibold text-[#07888d] shadow-sm transition hover:border-[#10b8bd] hover:bg-cyan-50"
              >
                <Icon className="h-4 w-4" />
                {chip.label}
              </button>
            );
          })}
        </div>

        <div className="mt-12">
          <h2 className="mb-5 text-xl font-bold text-slate-950">为你推荐的目的地</h2>
          <div className="grid gap-5 lg:grid-cols-3">
            {destinations.map((item) => (
              <div key={item.city} className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
                <img src={item.image} alt={item.city} className="h-40 w-full object-cover" />
                <div className="p-4">
                  <div className="flex items-center gap-2">
                    <h3 className="text-xl font-bold">{item.city}</h3>
                    <span className="text-sm text-[#0da8ad]">{item.province}</span>
                  </div>
                  <p className="mt-2 min-h-[42px] text-sm leading-6 text-slate-600">{item.desc}</p>
                  <div className="mt-4 flex items-center justify-between">
                    <div className="text-sm text-slate-500">
                      预计预算 <span className="text-lg font-bold text-[#0da8ad]">{item.budget}</span> 起/人
                    </div>
                    <Button
                      size="sm"
                      onClick={() => onQuickPlan(`我想去${item.city}玩三天，预算${item.budget.replace(/[¥,]/g, "")}元，轻松游，美食优先`)}
                      className="rounded-full bg-[#10b8bd] px-5 text-white hover:bg-[#0ca8ad]"
                    >
                      一键规划
                    </Button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

interface FilterFieldProps {
  label: string;
  value: string;
  icon: ComponentType<{ className?: string }>;
  type?: string;
  suffix?: string;
  placeholder?: string;
  onChange: (value: string) => void;
}

function FilterField({ label, value, icon: Icon, type = "text", suffix, placeholder, onChange }: FilterFieldProps) {
  return (
    <label className="rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm transition focus-within:border-[#10b8bd]">
      <span className="flex items-center gap-2 text-xs font-medium text-slate-500">
        <Icon className="h-4 w-4 text-[#11aeb4]" />
        {label}
      </span>
      <span className="mt-1 flex items-center gap-1">
        <Input
          type={type}
          value={value}
          placeholder={placeholder}
          onChange={(event) => onChange(event.target.value)}
          className="h-7 border-0 bg-transparent p-0 text-base font-black text-slate-950 shadow-none focus-visible:ring-0"
        />
        {suffix && <span className="text-sm font-black text-slate-950">{suffix}</span>}
      </span>
    </label>
  );
}
