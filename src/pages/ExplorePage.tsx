import { useState } from "react";
import { Calendar, MapPin, Sparkles, Users, Wallet } from "lucide-react";
import { Button } from "@/components/ui/button";

export interface DestinationPreset {
  city: string;
  province: string;
  budget: string;
  days: string;
  people: string;
  tags: string[];
  desc: string;
  image: string;
}

interface ExplorePageProps {
  onChooseDestination: (destination: DestinationPreset) => void;
}

const destinations: DestinationPreset[] = [
  {
    city: "杭州",
    province: "浙江",
    budget: "¥3,200",
    days: "3天",
    people: "2人",
    tags: ["西湖", "江南", "慢节奏"],
    desc: "西湖如画，诗意江南，适合放松身心的慢节奏旅行。",
    image: "https://images.unsplash.com/photo-1596176530529-78163a4f7af2?auto=format&fit=crop&w=900&q=80",
  },
  {
    city: "成都",
    province: "四川",
    budget: "¥2,800",
    days: "3天",
    people: "2人",
    tags: ["美食", "熊猫", "周末"],
    desc: "美食之都，慢生活节奏，熊猫基地不容错过。",
    image: "https://images.unsplash.com/photo-1532629345422-7515f3d16bb6?auto=format&fit=crop&w=900&q=80",
  },
  {
    city: "青岛",
    province: "山东",
    budget: "¥2,600",
    days: "4天",
    people: "3人",
    tags: ["海滨", "亲子", "啤酒"],
    desc: "海风拂面，红瓦绿树，啤酒与海鲜的完美搭配。",
    image: "https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?auto=format&fit=crop&w=900&q=80",
  },
  {
    city: "三亚",
    province: "海南",
    budget: "¥5,800",
    days: "5天",
    people: "2人",
    tags: ["海岛", "度假", "潜水"],
    desc: "阳光沙滩，海岛风情，适合完全放空的热带假期。",
    image: "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=900&q=80",
  },
  {
    city: "苏州",
    province: "江苏",
    budget: "¥3,100",
    days: "4天",
    people: "2人",
    tags: ["园林", "古镇", "慢游"],
    desc: "园林、古镇、评弹和水巷，适合安静的江南慢游。",
    image: "https://images.unsplash.com/photo-1506744038136-46273834b3fb?auto=format&fit=crop&w=900&q=80",
  },
  {
    city: "大理",
    province: "云南",
    budget: "¥4,900",
    days: "6天",
    people: "2人",
    tags: ["洱海", "雪山", "旅拍"],
    desc: "苍山洱海，古城与雪山，适合长线深度旅行。",
    image: "https://images.unsplash.com/photo-1500534314209-a25ddb2bd429?auto=format&fit=crop&w=900&q=80",
  },
];

const themes = ["海岛度假", "古镇漫游", "亲子时光", "赏花踏青", "City Walk", "避暑清凉"];
const themeTargets: Record<string, string> = {
  海岛度假: "三亚",
  古镇漫游: "苏州",
  亲子时光: "青岛",
  赏花踏青: "杭州",
  "City Walk": "成都",
  避暑清凉: "大理",
};

export function ExplorePage({ onChooseDestination }: ExplorePageProps) {
  const [selectedCity, setSelectedCity] = useState(destinations[0].city);
  const [selectedTheme, setSelectedTheme] = useState(themes[0]);
  const selected = destinations.find((item) => item.city === selectedCity) ?? destinations[0];

  return (
    <section className="relative min-h-[calc(100vh-68px)] overflow-hidden bg-gradient-to-br from-cyan-50 via-white to-white">
      <div className="mx-auto max-w-[1260px] px-8 py-10">
        <div className="mb-8 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <h1 className="text-4xl font-black tracking-normal text-slate-950">探索目的地</h1>
            <div className="mt-3 text-sm font-medium text-slate-500">目的地灵感</div>
          </div>
          <div className="flex flex-wrap gap-3">
            {themes.slice(0, 4).map((item) => (
              <button
                key={item}
                onClick={() => {
                  setSelectedTheme(item);
                  setSelectedCity(themeTargets[item] ?? selectedCity);
                }}
                className={`rounded-full border px-5 py-2 text-sm font-semibold shadow-sm ${selectedTheme === item ? "border-[#10b8bd] bg-[#10b8bd] text-white" : "border-cyan-100 bg-white text-[#0da8ad]"}`}
              >
                {item}
              </button>
            ))}
          </div>
        </div>

        <div className="mb-6 rounded-2xl border border-cyan-100 bg-cyan-50/70 p-5">
          <div className="grid gap-5 lg:grid-cols-[180px_1fr_220px] lg:items-center">
            <img src={selected.image} alt={selected.city} className="h-28 w-full rounded-xl object-cover" />
            <div>
              <div className="flex items-center gap-2 text-2xl font-black">{selected.city}<span className="text-sm font-bold text-[#0da8ad]">{selected.province}</span></div>
              <div className="mt-3 flex flex-wrap gap-2">
                {selected.tags.map((tag) => <span key={tag} className="rounded-full bg-white px-3 py-1 text-xs font-semibold text-slate-500">{tag}</span>)}
              </div>
              <div className="mt-3 text-sm leading-6 text-slate-600">{selected.desc}</div>
            </div>
            <Button onClick={() => onChooseDestination(selected)} className="h-12 rounded-xl bg-[#10b8bd] text-white hover:bg-[#0ca8ad]">
              <Sparkles className="h-4 w-4" />
              加入规划
            </Button>
          </div>
        </div>

        <div className="grid gap-6 xl:grid-cols-3">
          {destinations.map((item) => {
            const active = item.city === selectedCity;
            return (
              <button
                key={item.city}
                type="button"
                onClick={() => setSelectedCity(item.city)}
                className={`overflow-hidden rounded-2xl border bg-white text-left shadow-sm transition hover:-translate-y-1 hover:border-[#10b8bd] hover:shadow-xl hover:shadow-cyan-100 ${active ? "border-[#10b8bd] ring-2 ring-cyan-100" : "border-slate-200"}`}
              >
                <img src={item.image} alt={item.city} className="h-44 w-full object-cover" />
                <div className="p-5">
                  <div className="mb-3 flex items-center justify-between">
                    <div>
                      <h2 className="text-2xl font-black">{item.city}</h2>
                      <div className="mt-1 flex items-center gap-1 text-sm font-semibold text-[#0da8ad]">
                        <MapPin className="h-4 w-4" />
                        {item.province}
                      </div>
                    </div>
                    <span className="rounded-full bg-cyan-50 px-3 py-1 text-xs font-bold text-[#0da8ad]">{active ? "已选择" : "可选择"}</span>
                  </div>
                  <p className="min-h-[48px] text-sm leading-6 text-slate-600">{item.desc}</p>
                  <div className="mt-4 flex flex-wrap gap-2">
                    {item.tags.map((tag) => (
                      <span key={tag} className="rounded-full bg-slate-50 px-3 py-1 text-xs font-semibold text-slate-500">
                        {tag}
                      </span>
                    ))}
                  </div>
                  <div className="mt-5 flex items-center justify-between border-t border-slate-100 pt-4 text-sm font-medium text-slate-500">
                    <span className="flex items-center gap-1"><Calendar className="h-4 w-4" />{item.days}</span>
                    <span className="flex items-center gap-1"><Users className="h-4 w-4" />{item.people}</span>
                    <span className="flex items-center gap-1"><Wallet className="h-4 w-4" />{item.budget}</span>
                  </div>
                </div>
              </button>
            );
          })}
        </div>
      </div>
    </section>
  );
}
