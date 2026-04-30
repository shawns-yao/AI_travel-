import { useCallback, useEffect, useState } from "react";
import { AppShell, AppView } from "@/layout/AppShell";
import { useTravelRun } from "@/hooks/useTravelRun";
import { useStore } from "@/model";
import { deleteSavedPlan, fetchSavedPlans } from "@/services/travelApi";
import { HomePage } from "@/pages/HomePage";
import { GeneratingPage } from "@/pages/GeneratingPage";
import { ResultPage } from "@/pages/ResultPage";
import { PlansPage } from "@/pages/PlansPage";
import { PreferencesPage } from "@/pages/PreferencesPage";
import { ComparePage, PlanningDraft } from "@/pages/ComparePage";
import { DestinationPreset, ExplorePage } from "@/pages/ExplorePage";
import { EditPlanPage } from "@/pages/EditPlanPage";

function App() {
  const [view, setView] = useState<AppView>("home");
  const [query, setQuery] = useState("");
  const [editIntent, setEditIntent] = useState<{ changes: string[]; day: number }>({ changes: [], day: 0 });
  const [planningDraft, setPlanningDraft] = useState<PlanningDraft>({
    destination: "杭州",
    duration: "3",
    startDate: "",
    people: "3",
    budget: "",
    notes: "父母同行，轻松少走路",
  });
  const isRunning = useStore((s) => s.isRunning);
  const travelPlan = useStore((s) => s.travelPlan);
  const savedPlans = useStore((s) => s.savedPlans);
  const events = useStore((s) => s.events);
  const setTravelPlan = useStore((s) => s.setTravelPlan);
  const saveTravelPlan = useStore((s) => s.saveTravelPlan);
  const mergeSavedPlans = useStore((s) => s.mergeSavedPlans);
  const removeTravelPlan = useStore((s) => s.removeTravelPlan);
  const { startRun } = useTravelRun();

  useEffect(() => {
    fetchSavedPlans()
      .then((plans) => mergeSavedPlans(plans))
      .catch(() => undefined);
  }, [mergeSavedPlans]);

  const handleSubmit = useCallback((queryOverride?: string) => {
    const nextQuery = queryOverride?.trim() || query.trim();
    if (!nextQuery) return;
    setQuery(nextQuery);
    setView("generating");
    void startRun(nextQuery);
  }, [query, startRun]);

  const handlePlanQuery = useCallback(
    (nextQuery: string) => {
      if (!nextQuery.trim()) return;
      setQuery(nextQuery);
      setView("generating");
      void startRun(nextQuery);
    },
    [startRun],
  );

  const handleOpenPlan = useCallback(
    (plan: typeof travelPlan) => {
      if (!plan) return;
      setTravelPlan(plan);
      setView("result");
    },
    [setTravelPlan],
  );

  const openEditPage = useCallback((changes: string[] = [], day = 0) => {
    setEditIntent({ changes, day });
    setView("edit");
  }, []);

  const buildVariantQuery = useCallback((variant: string, draft: PlanningDraft) => {
    const variantRules = {
      舒适版: {
        transport: "打车和短距离步行结合，减少换乘",
        hotel: "住宿靠近核心区域或首日景点",
        pace: "每天2到3个精华景点，节奏轻松",
        budget: "预算优先给住宿和交通便利性",
      },
      省钱版: {
        transport: "公共交通优先，地铁/公交能到就不打车",
        hotel: "住宿选地铁沿线，避开核心景区高价酒店",
        pace: "每天3个景点，优先串联同一区域",
        budget: "免费或低价景点优先，本地平价美食",
      },
      深度游版: {
        transport: "允许更多步行和跨区移动",
        hotel: "住宿贴近次日路线起点",
        pace: "每天4到5个地点，加入小众文化点",
        budget: "预算优先给体验项目和深度游内容",
      },
    }[variant] ?? {
      transport: "按目的地选择合适交通",
      hotel: "住宿贴近主要路线",
      pace: "节奏适中",
      budget: "预算按行程均衡分配",
    };

    return [
      `请按${variant}生成旅行方案`,
      `方案类型：${variant}`,
      `目的地：${draft.destination || "杭州"}`,
      `天数：${draft.duration || "3"}天`,
      draft.startDate ? `出发日期：${draft.startDate}` : "",
      `人数：${draft.people || "2"}人`,
      draft.budget ? `预算：${draft.budget}元` : "预算：请根据目的地、人数和天数估算",
      `交通策略：${variantRules.transport}`,
      `住宿策略：${variantRules.hotel}`,
      `节奏策略：${variantRules.pace}`,
      `预算策略：${variantRules.budget}`,
      draft.notes ? `补充要求：${draft.notes}` : "",
    ].filter(Boolean).join("，");
  }, []);

  const handleGenerateVariant = useCallback(
    (variant: string, draft: PlanningDraft) => {
      handlePlanQuery(buildVariantQuery(variant, draft));
    },
    [buildVariantQuery, handlePlanQuery],
  );

  const handleChooseDestination = useCallback((destination: DestinationPreset) => {
    setPlanningDraft((current) => ({
      ...current,
      destination: destination.city,
      duration: destination.days.replace(/\D/g, "") || current.duration,
      people: destination.people.replace(/\D/g, "") || current.people,
      budget: destination.budget.replace(/[¥,]/g, ""),
      notes: destination.tags.join("，"),
    }));
    setView("compare");
  }, []);

  const handleDeletePlan = useCallback(
    async (plan: typeof travelPlan) => {
      if (!plan) return;
      if (plan.id) {
        await deleteSavedPlan(plan.id);
      }
      removeTravelPlan(plan);
    },
    [removeTravelPlan],
  );

  useEffect(() => {
    if (view === "generating" && travelPlan && !isRunning) {
      setView("result");
    }
  }, [isRunning, travelPlan, view]);

  return (
    <AppShell activeView={view} onNavigate={setView}>
      {view === "home" && (
        <HomePage
          query={query}
          isRunning={isRunning}
          onQueryChange={setQuery}
          onSubmit={handleSubmit}
          onQuickPlan={handlePlanQuery}
        />
      )}
      {view === "generating" && <GeneratingPage events={events} query={query} />}
      {view === "result" && travelPlan && (
        <ResultPage plan={travelPlan} onSave={saveTravelPlan} onEdit={openEditPage} />
      )}
      {view === "edit" && travelPlan && (
        <EditPlanPage
          plan={travelPlan}
          onSave={saveTravelPlan}
          onOptimize={handlePlanQuery}
          initialChanges={editIntent.changes}
          initialDay={editIntent.day}
        />
      )}
      {view === "plans" && (
        <PlansPage
          plans={savedPlans}
          onNew={() => setView("home")}
          onOpenPlan={(plan) => {
            handleOpenPlan(plan);
            setEditIntent({ changes: [], day: 0 });
            setView("edit");
          }}
          onDelete={handleDeletePlan}
        />
      )}
      {view === "preferences" && <PreferencesPage />}
      {view === "explore" && <ExplorePage onChooseDestination={handleChooseDestination} />}
      {view === "compare" && (
        <ComparePage
          plan={travelPlan}
          draft={planningDraft}
          onDraftChange={setPlanningDraft}
          onBack={() => setView("home")}
          onSaveDraft={travelPlan ? () => saveTravelPlan(travelPlan) : undefined}
          onGenerateVariant={handleGenerateVariant}
        />
      )}
    </AppShell>
  );
}

export default App;
