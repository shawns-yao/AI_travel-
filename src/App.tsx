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
  const [query, setQuery] = useState("我想去杭州玩三天，预算4000元，父母同行，轻松少走路");
  const [planningDraft, setPlanningDraft] = useState<PlanningDraft>({
    destination: "杭州",
    duration: "3",
    startDate: "",
    people: "3",
    budget: "4000",
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

  const buildVariantQuery = useCallback((variant: string, draft: PlanningDraft) => {
    const variantRules =
      variant === "舒适版"
        ? "少走路，住宿靠近核心区域，每天2到3个景点，节奏轻松"
        : variant === "省钱版"
          ? "公共交通优先，住宿选地铁沿线，免费或低价景点优先，本地平价美食"
          : "小众路线，文化体验，每天4到5个地点，行程更紧凑";

    return [
      `请按${variant}生成旅行方案`,
      `目的地：${draft.destination || "杭州"}`,
      `天数：${draft.duration || "3"}天`,
      draft.startDate ? `出发日期：${draft.startDate}` : "",
      `人数：${draft.people || "2"}人`,
      `预算：${draft.budget || "4000"}元`,
      `方案约束：${variantRules}`,
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
        <ResultPage plan={travelPlan} onSave={saveTravelPlan} onDuplicate={handlePlanQuery} />
      )}
      {view === "edit" && travelPlan && (
        <EditPlanPage plan={travelPlan} onSave={saveTravelPlan} onOptimize={handlePlanQuery} />
      )}
      {view === "plans" && (
        <PlansPage
          plans={savedPlans}
          onNew={() => setView("home")}
          onOpenPlan={(plan) => {
            handleOpenPlan(plan);
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
