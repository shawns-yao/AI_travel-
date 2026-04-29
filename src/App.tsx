import { useCallback, useState } from "react";
import { Card } from "./components/ui/card";
import { useStore } from "./model";
import PlannerForm from "./components/PlannerForm";
import AgentStatus from "./components/AgentStatus";
import PlanResult from "./components/PlanResult";

function App() {
  const isRunning = useStore((s) => s.isRunning);
  const travelPlan = useStore((s) => s.travelPlan);
  const events = useStore((s) => s.events);
  const setIsRunning = useStore((s) => s.setIsRunning);
  const setTravelPlan = useStore((s) => s.setTravelPlan);
  const setRunId = useStore((s) => s.setRunId);
  const addEvent = useStore((s) => s.addEvent);
  const reset = useStore((s) => s.reset);

  const [showReport, setShowReport] = useState(false);

  const handleSubmit = useCallback(async (input: string) => {
    reset();
    setIsRunning(true);
    setShowReport(false);

    try {
      const response = await fetch("/api/runs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: input }),
      });

      if (!response.ok) throw new Error("Failed to create run");

      const { run_id } = await response.json();
      setRunId(run_id);

      // Connect SSE stream
      const eventSource = new EventSource(`/api/runs/${run_id}/events`);

      eventSource.onmessage = (event) => {
        const parsed = JSON.parse(event.data);
        addEvent(parsed);

        if (parsed.type === "run.completed") {
          setTravelPlan(parsed.data.result);
          setIsRunning(false);
          eventSource.close();
        } else if (parsed.type === "run.failed") {
          setIsRunning(false);
          eventSource.close();
        }
      };

      eventSource.onerror = () => {
        setIsRunning(false);
        eventSource.close();
      };
    } catch (error) {
      console.error("Run failed:", error);
      setIsRunning(false);
    }
  }, [reset, setIsRunning, setShowReport, setRunId, addEvent, setTravelPlan]);

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-purple-50">
      <div className="container mx-auto px-4 py-8 max-w-6xl">
        <div className="mb-8">
          <Card className="p-4 shadow-lg border-0 bg-white/80 backdrop-blur-sm">
            <PlannerForm
              onSubmit={handleSubmit}
              isLoading={isRunning}
              onShowReport={() => setShowReport(true)}
              hasReport={!!travelPlan}
            />
          </Card>
        </div>

        <div>
          <Card className="p-6 shadow-lg border-0 bg-white/80 backdrop-blur-sm min-h-[500px]">
            <AgentStatus isPlanning={isRunning} events={events} />
          </Card>
        </div>

        {showReport && travelPlan && (
          <PlanResult
            plan={travelPlan}
            open={showReport}
            onOpenChange={setShowReport}
          />
        )}
      </div>
    </div>
  );
}

export default App;
