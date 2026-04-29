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

  // Actions
  setRunId: (id: string) => void;
  addEvent: (event: SSERunEvent) => void;
  setRunStatus: (status: RunStatus) => void;
  setTravelPlan: (plan: TravelPlanResult) => void;
  setIsRunning: (running: boolean) => void;
  reset: () => void;
}

export const useStore = create<AppState>((set) => ({
  currentRunId: null,
  runStatus: null,
  events: [],
  isRunning: false,
  travelPlan: null,

  setRunId: (id) => set({ currentRunId: id }),
  addEvent: (event) =>
    set((state) => ({ events: [...state.events, event] })),
  setRunStatus: (status) => set({ runStatus: status }),
  setTravelPlan: (plan) => set({ travelPlan: plan }),
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
