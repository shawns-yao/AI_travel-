import { CardContent, CardHeader, CardTitle } from "./ui/card";
import { ScrollArea } from "./ui/scroll-area";
import { Badge } from "./ui/badge";
import { SSERunEvent } from "@/types";
import { useMemo, useState } from "react";

interface AgentStatusProps {
  isPlanning: boolean;
  events: SSERunEvent[];
}

const EVENT_CONFIG: Record<string, { emoji: string; color: string; label: string }> = {
  "run.created": { emoji: "", color: "bg-green-100 text-green-800", label: "Run Created" },
  "plan.generated": { emoji: "", color: "bg-purple-100 text-purple-800", label: "Plan" },
  "step.started": { emoji: "", color: "bg-blue-100 text-blue-800", label: "Agent Start" },
  "tool.called": { emoji: "🔧", color: "bg-yellow-100 text-yellow-800", label: "Tool Call" },
  "tool.completed": { emoji: "✅", color: "bg-green-100 text-green-800", label: "Tool Done" },
  "memory.hit": { emoji: "🧠", color: "bg-pink-100 text-pink-800", label: "Memory" },
  "agent.completed": { emoji: "🤖", color: "bg-indigo-100 text-indigo-800", label: "Agent Done" },
  "critic.issued": { emoji: "🔍", color: "bg-orange-100 text-orange-800", label: "Critic" },
  "replan.started": { emoji: "🔄", color: "bg-red-100 text-red-800", label: "Replan" },
  "run.completed": { emoji: "✨", color: "bg-green-200 text-green-900", label: "Complete" },
  "run.failed": { emoji: "❌", color: "bg-red-200 text-red-900", label: "Failed" },
};

const formatTime = (timestamp: number) =>
  new Date(timestamp).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit", second: "2-digit" });

export default function AgentStatus({ isPlanning, events }: AgentStatusProps) {
  const [expanded, setExpanded] = useState<Set<number>>(new Set());

  const toggle = (idx: number) => {
    const next = new Set(expanded);
    next.has(idx) ? next.delete(idx) : next.add(idx);
    setExpanded(next);
  };

  const stats = useMemo(() => {
    const agentCompleted = events.filter((e) => e.type === "agent.completed").length;
    const toolCalls = events.filter((e) => e.type === "tool.called").length;
    const memoryHits = events.filter((e) => e.type === "memory.hit").length;
    return { agentCompleted, toolCalls, memoryHits };
  }, [events]);

  return (
    <div className="h-full flex flex-col">
      <CardHeader className="p-0 pb-3">
        <CardTitle className="text-lg flex items-center space-x-2">
          <span>Agent Execution Trace</span>
          {isPlanning && (
            <div className="animate-spin rounded-full h-3 w-3 border-b-2 border-blue-500" />
          )}
        </CardTitle>
        <div className="flex space-x-2 mt-2">
          <Badge variant="outline" className="text-xs"> Agents: {stats.agentCompleted}</Badge>
          <Badge variant="outline" className="text-xs">🔧 Tools: {stats.toolCalls}</Badge>
          <Badge variant="outline" className="text-xs">🧠 Memory: {stats.memoryHits}</Badge>
        </div>
      </CardHeader>

      <CardContent className="flex-1 p-0 overflow-hidden">
        <ScrollArea className="h-[calc(100vh-350px)]">
          {events.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-48 text-gray-500">
              <div className="text-4xl mb-3">🤖</div>
              <p className="text-base font-medium">Waiting for Agent execution...</p>
              <p className="text-xs text-gray-400 mt-1">Events will appear here in real-time</p>
            </div>
          ) : (
            <div className="relative">
              <div className="absolute left-6 top-0 bottom-0 w-0.5 bg-gradient-to-b from-blue-200 via-purple-200 to-green-200" />
              {events.map((event, idx) => {
                const config = EVENT_CONFIG[event.type] || { emoji: "📌", color: "bg-gray-100", label: event.type };
                const isExpanded = expanded.has(idx);
                const isLast = idx === events.length - 1;

                return (
                  <div
                    key={`${event.timestamp}-${idx}`}
                    className={`relative pl-12 pr-3 py-2 transition-all duration-300 hover:bg-gray-50/50 rounded-lg ${
                      isLast && isPlanning ? "animate-pulse bg-blue-50/50" : ""
                    }`}
                  >
                    <div
                      className={`absolute left-5 w-3 h-3 rounded-full border-2 border-white shadow-sm ${
                        isLast && isPlanning ? "bg-blue-400 animate-ping" : "bg-blue-300"
                      }`}
                    />
                    <div className="bg-white rounded-lg shadow-sm border p-3 ml-1">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center space-x-2">
                          <span>{config.emoji}</span>
                          <span className="font-medium text-sm">{config.label}</span>
                          <Badge variant="outline" className={`text-xs ${config.color}`}>
                            {event.type}
                          </Badge>
                        </div>
                        <div className="flex items-center space-x-2">
                          <span className="text-xs text-gray-400">{formatTime(event.timestamp)}</span>
                          <button
                            onClick={() => toggle(idx)}
                            className="text-xs text-blue-600 hover:underline"
                          >
                            {isExpanded ? "Hide" : "Detail"}
                          </button>
                        </div>
                      </div>
                      {isExpanded && (
                        <pre className="mt-2 text-xs text-gray-600 bg-gray-50 p-2 rounded max-h-40 overflow-auto">
                          {JSON.stringify(event.data, null, 2)}
                        </pre>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </ScrollArea>
      </CardContent>
    </div>
  );
}
