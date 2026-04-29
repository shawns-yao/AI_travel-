import { create } from "zustand";
import { SSERunEvent, RunStatus, TravelPlanResult } from "@/types";

interface AppState {
  // Run state
  currentRunId: string | null;
  runStatus: RunStatus | null;
  events: SSERunEvent[];
  isRunning: boolean;

  // Results
  travelPlan: TravelPlanResult | null;
  savedPlans: TravelPlanResult[];

  // Actions
  setRunId: (id: string) => void;
  addEvent: (event: SSERunEvent) => void;
  setRunStatus: (status: RunStatus) => void;
  setTravelPlan: (plan: TravelPlanResult) => void;
  saveTravelPlan: (plan: TravelPlanResult) => void;
  mergeSavedPlans: (plans: TravelPlanResult[]) => void;
  removeTravelPlan: (plan: TravelPlanResult) => void;
  setIsRunning: (running: boolean) => void;
  reset: () => void;
}

const loadSavedPlans = (): TravelPlanResult[] => {
  try {
    return JSON.parse(localStorage.getItem("ai-travel-plans") || "[]") as TravelPlanResult[];
  } catch {
    return [];
  }
};

const planKey = (plan: TravelPlanResult) =>
  plan.id ||
  plan.source_run_id ||
  `${plan.destination || "unknown"}-${plan.start_date || "unknown"}-${plan.duration || 0}-${plan.created_at || ""}`;

const persistSavedPlans = (plans: TravelPlanResult[]) => {
  localStorage.setItem("ai-travel-plans", JSON.stringify(plans.slice(0, 12)));
};

export const useStore = create<AppState>((set) => ({
  currentRunId: null,
  runStatus: null,
  events: [],
  isRunning: false,
  travelPlan: null,
  savedPlans: loadSavedPlans(),

  setRunId: (id) => set({ currentRunId: id }),
  addEvent: (event) =>
    set((state) => ({ events: [...state.events, event] })),
  setRunStatus: (status) => set({ runStatus: status }),
  setTravelPlan: (plan) => set({ travelPlan: plan }),
  saveTravelPlan: (plan) =>
    set((state) => {
      const next = [plan, ...state.savedPlans.filter((item) => planKey(item) !== planKey(plan))];
      persistSavedPlans(next);
      return { savedPlans: next };
    }),
  mergeSavedPlans: (plans) =>
    set((state) => {
      const seen = new Set<string>();
      const next = [...plans, ...state.savedPlans].filter((plan) => {
        const key = planKey(plan);
        if (seen.has(key)) return false;
        seen.add(key);
        return true;
      });
      persistSavedPlans(next);
      return { savedPlans: next };
    }),
  removeTravelPlan: (plan) =>
    set((state) => {
      const next = state.savedPlans.filter((item) => planKey(item) !== planKey(plan));
      persistSavedPlans(next);
      return { savedPlans: next };
    }),
  setIsRunning: (running) => set({ isRunning: running }),
  reset: () =>
    set({
      currentRunId: null,
      runStatus: null,
      events: [],
      isRunning: false,
      travelPlan: null,
    }),
}));
