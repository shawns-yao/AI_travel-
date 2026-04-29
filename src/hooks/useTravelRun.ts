import { useCallback, useRef, useState } from "react";
import { createTravelRun, subscribeRunEvents } from "@/services/travelApi";
import { useStore } from "@/model";

export function useTravelRun() {
  const sourceRef = useRef<EventSource | null>(null);
  const [error, setError] = useState<string | null>(null);

  const reset = useStore((s) => s.reset);
  const addEvent = useStore((s) => s.addEvent);
  const setRunId = useStore((s) => s.setRunId);
  const setIsRunning = useStore((s) => s.setIsRunning);
  const setTravelPlan = useStore((s) => s.setTravelPlan);
  const saveTravelPlan = useStore((s) => s.saveTravelPlan);

  const startRun = useCallback(
    async (query: string) => {
      sourceRef.current?.close();
      reset();
      setError(null);
      setIsRunning(true);

      try {
        const created = await createTravelRun(query);
        setRunId(created.run_id);

        sourceRef.current = subscribeRunEvents(created.run_id, {
          onEvent: addEvent,
          onCompleted: ({ result }) => {
            setTravelPlan(result);
            saveTravelPlan(result);
            setIsRunning(false);
          },
          onFailed: (message) => {
            setError(message);
            setIsRunning(false);
          },
        });
      } catch (e) {
        setError(e instanceof Error ? e.message : "创建规划任务失败");
        setIsRunning(false);
      }
    },
    [addEvent, reset, saveTravelPlan, setIsRunning, setRunId, setTravelPlan],
  );

  const stopRun = useCallback(() => {
    sourceRef.current?.close();
    sourceRef.current = null;
    setIsRunning(false);
  }, [setIsRunning]);

  return { startRun, stopRun, error };
}
