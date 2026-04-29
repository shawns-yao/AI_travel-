import { CalendarCheck, CloudSun, Hotel, ListChecks, MapPin, Wallet } from "lucide-react";
import { SSERunEvent } from "@/types";
import { RouteMapMock } from "@/components/travel/RouteMapMock";

interface GeneratingPageProps {
  events: SSERunEvent[];
  query: string;
}

const steps = [
  { label: "理解旅行需求", desc: "分析目的地、预算和特殊需求", icon: ListChecks },
  { label: "查看天气和出行条件", desc: "匹配天气、日期和出行风险", icon: CloudSun },
  { label: "筛选景点和美食", desc: "检索景点、餐厅和周边信息", icon: MapPin },
  { label: "规划每日路线", desc: "组合每日路线和时间段", icon: CalendarCheck },
  { label: "核算预算", desc: "拆分交通、住宿、餐饮和活动", icon: Wallet },
  { label: "优化行程节奏", desc: "根据强度和约束做二次调整", icon: Hotel },
  { label: "生成最终方案", desc: "输出可编辑的结构化行程", icon: ListChecks },
];

const deriveDestination = (query: string) => {
  const structured = query.match(/目的地[:：]\s*([^，,。.；;\s]+)/);
  if (structured?.[1]) return structured[1];
  const match = query.match(/去([^，,。.\s]+?)(?:玩|旅游|旅行|出行|度假)/);
  if (match?.[1]) return match[1];
  return ["杭州", "成都", "青岛", "上海", "北京", "三亚"].find((city) => query.includes(city)) || "目的地";
};

const deriveDuration = (query: string) => {
  const structured = query.match(/天数[:：]\s*(\d+)/);
  if (structured?.[1]) return Number(structured[1]);
  const digit = query.match(/(\d+)\s*天/);
  if (digit?.[1]) return Number(digit[1]);
  const cnDays: Record<string, number> = { 一: 1, 二: 2, 两: 2, 三: 3, 四: 4, 五: 5, 六: 6, 七: 7 };
  const found = Object.entries(cnDays).find(([word]) => query.includes(`${word}天`));
  return found?.[1] ?? 3;
};

const agentOutput = (events: SSERunEvent[], agentName: string) => {
  const event = [...events].reverse().find((item) => item.type === "agent.completed" && item.data.agent_name === agentName);
  return event?.data.output as Record<string, unknown> | undefined;
};

const listNames = (items: unknown, limit = 3) =>
  Array.isArray(items)
    ? items
        .slice(0, limit)
        .map((item) => (typeof item === "object" && item ? String((item as Record<string, unknown>).name || "") : ""))
        .filter(Boolean)
    : [];

const budgetSummary = (output?: Record<string, unknown>) => {
  const allocated = output?.allocated;
  if (!allocated || typeof allocated !== "object") return "";
  return Object.entries(allocated as Record<string, unknown>)
    .slice(0, 4)
    .map(([key, value]) => `${key} ¥${Math.round(Number(value) || 0)}`)
    .join(" · ");
};

const routeSummary = (output?: Record<string, unknown>) => {
  const dailyPlans = output?.daily_plans;
  if (!Array.isArray(dailyPlans)) return "";
  const first = dailyPlans[0];
  if (!first || typeof first !== "object") return "";
  const activities = (first as Record<string, unknown>).activities;
  const names = listNames(activities, 3);
  return names.join(" → ");
};

const latestToolItems = (events: SSERunEvent[], category: string, limit = 3) => {
  const event = [...events]
    .reverse()
    .find((item) => item.type === "tool.completed" && item.data.category === category);
  const output = event?.data.output as Record<string, unknown> | undefined;
  return listNames(output?.items, limit);
};

const latestToolSummary = (events: SSERunEvent[]) =>
  events
    .filter((event) => event.type === "tool.completed" || event.type === "memory.hit")
    .slice(-5)
    .map((event) => String(event.data.summary || event.data.tool_name || event.type))
    .filter(Boolean);

export function GeneratingPage({ events, query }: GeneratingPageProps) {
  const completedAgents = events.filter((event) => event.type === "agent.completed").length;
  const completed = Math.min(completedAgents + 1, steps.length);
  const progress = Math.round((completed / steps.length) * 100);
  const destination = deriveDestination(query);
  const duration = deriveDuration(query);
  const plannerOutput = agentOutput(events, "PlannerAgent");
  const budgetOutput = agentOutput(events, "BudgetAgent");
  const hotels = listNames(plannerOutput?.hotels, 3);
  const liveHotels = hotels.length ? hotels : latestToolItems(events, "酒店", 3);
  const liveAttractions = latestToolItems(events, "景点", 4);
  const liveFood = latestToolItems(events, "餐饮", 1);
  const budgetText = budgetSummary(budgetOutput);
  const routeText = routeSummary(plannerOutput);
  const toolSummaries = latestToolSummary(events);
  const liveCards = [
    {
      title: "住宿区域推荐",
      value: liveHotels.length ? liveHotels.join("、") : "",
      fallback: "正在检索酒店和住宿区域",
    },
    {
      title: "预算估算",
      value: budgetText,
      fallback: "正在拆分交通、住宿、餐饮、门票",
    },
    {
      title: "景点与路线",
      value: routeText || liveAttractions.join(" → "),
      fallback: `D1 / D2 / D${duration} 时间轴生成中`,
    },
  ];

  return (
    <section className="relative min-h-[calc(100vh-68px)] overflow-hidden bg-gradient-to-br from-cyan-50 via-white to-white">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_70%_20%,rgba(16,184,189,0.12),transparent_34%),linear-gradient(180deg,rgba(255,255,255,0)_0%,#fff_100%)]" />
      <div className="relative mx-auto max-w-[1320px] px-8 py-12">
        <div className="mb-7">
          <h1 className="text-4xl font-black tracking-normal text-slate-950">正在为你规划{destination} {duration} 日轻松游</h1>
          <div className="mt-3 text-lg font-medium text-slate-500">天气、预算、路线、住宿正在并行生成</div>
        </div>

        <div className="grid gap-8 xl:grid-cols-[0.85fr_1.15fr]">
          <div className="rounded-2xl border border-slate-200 bg-white/92 p-5 shadow-sm">
            <div className="mb-5 flex items-center justify-between">
              <div className="text-sm font-bold text-slate-500">Agent 进度</div>
              <div className="text-sm font-black text-[#0da8ad]">{progress}%</div>
            </div>
            <div className="mb-2 h-2 rounded-full bg-slate-100">
              <div className="h-2 rounded-full bg-[#10b8bd] transition-all" style={{ width: `${progress}%` }} />
            </div>

            <div className="mt-5">
              {steps.map((step, index) => {
                const Icon = step.icon;
                const active = index + 1 === completed;
                const done = index + 1 < completed;
                return (
                  <div key={step.label} className="grid grid-cols-[42px_1fr_72px] items-center gap-4 border-b border-slate-100 py-4 last:border-0">
                    <div className={`flex h-10 w-10 items-center justify-center rounded-full text-sm font-bold ${done || active ? "bg-[#11b8bd] text-white" : "bg-slate-100 text-slate-400"}`}>
                      {index + 1}
                    </div>
                    <div className="flex items-center gap-3">
                      <Icon className={`h-5 w-5 ${done || active ? "text-[#0da8ad]" : "text-slate-400"}`} />
                      <div>
                        <div className={`font-bold ${done || active ? "text-slate-900" : "text-slate-500"}`}>{step.label}</div>
                        <div className="mt-1 text-xs text-slate-400">{step.desc}</div>
                      </div>
                    </div>
                    <span className={`text-right text-sm font-semibold ${active ? "text-[#0da8ad]" : done ? "text-emerald-600" : "text-slate-400"}`}>{active ? "进行中" : done ? "完成" : "等待中"}</span>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="relative overflow-hidden rounded-2xl">
            <RouteMapMock muted previewLabel="推荐路线" />
          </div>
        </div>

        <div className="mt-6 grid gap-4 md:grid-cols-3">
          {liveCards.map((card, index) => (
            <div key={card.title} className="rounded-2xl border border-slate-200 bg-white/90 p-5 shadow-sm">
              <div className="mb-5 text-lg font-black">{card.title}</div>
              <div className="space-y-3">
                <div className={`flex min-h-24 items-center rounded-xl px-5 text-sm font-semibold leading-7 ${card.value ? "bg-cyan-50 text-slate-700" : index === 1 ? "bg-[conic-gradient(from_160deg,#8fe7e7,#eef6f7,#b7edf0,#eef6f7)] text-slate-500" : "bg-gradient-to-r from-cyan-50 to-slate-50 text-slate-500"}`}>
                  {card.value || card.fallback}
                </div>
                <div className={`h-3 rounded ${card.value ? "bg-[#10b8bd]/25" : "bg-slate-100"}`} />
                <div className={`h-3 w-4/5 rounded ${card.value ? "bg-[#10b8bd]/15" : "bg-slate-100"}`} />
                <div className={`pt-1 text-sm font-medium ${card.value ? "text-[#0da8ad]" : "text-slate-400"}`}>
                  {card.value ? "已获取，正在合成方案" : card.fallback}
                </div>
              </div>
            </div>
          ))}
        </div>

        <div className="mt-6 rounded-2xl border border-slate-200 bg-white/92 p-5 shadow-sm">
          <div className="mb-4 flex items-center justify-between">
            <div className="text-lg font-black">实时检索结果</div>
            <div className="text-sm font-bold text-[#0da8ad]">{toolSummaries.length ? "已接入工具链" : "等待工具返回"}</div>
          </div>
          <div className="grid gap-4 md:grid-cols-3">
            <div className="rounded-xl bg-cyan-50 p-4">
              <div className="mb-2 text-sm font-black text-slate-500">景点</div>
              <div className="text-sm font-semibold leading-7 text-slate-700">{liveAttractions.join("、") || "检索中"}</div>
            </div>
            <div className="rounded-xl bg-slate-50 p-4">
              <div className="mb-2 text-sm font-black text-slate-500">餐饮</div>
              <div className="text-sm font-semibold leading-7 text-slate-700">{liveFood.join("、") || "检索中"}</div>
            </div>
            <div className="rounded-xl bg-slate-50 p-4">
              <div className="mb-2 text-sm font-black text-slate-500">执行事件</div>
              <div className="text-sm font-semibold leading-7 text-slate-700">{toolSummaries.join(" · ") || "Agent 正在启动"}</div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
