import { SSERunEvent } from "@/types";
import { Badge } from "./ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";

interface Props {
  events: SSERunEvent[];
  isRunning: boolean;
}

interface TraceNode {
  type: string;
  label: string;
  agentName?: string;
  toolName?: string;
  durationMs?: number;
  success?: boolean;
  details?: string;
  children: TraceNode[];
}

function buildTraceTree(events: SSERunEvent[]): TraceNode[] {
  const roots: TraceNode[] = [];
  const agentNodes: Map<string, TraceNode> = new Map();

  for (const event of events) {
    switch (event.type) {
      case "run.created":
        roots.push({ type: "run", label: `Run #${String(event.data.run_id).slice(0, 8)}`, children: [] });
        break;

      case "plan.generated": {
        const node: TraceNode = {
          type: "plan",
          label: "DAG Plan Generated",
          details: `${event.data.total_agents || "?"} agents planned`,
          children: [],
        };
        roots[0]?.children.push(node);
        break;
      }

      case "step.started": {
        const name = String(event.data.agent_name || "unknown");
        const node: TraceNode = {
          type: "agent",
          label: name,
          agentName: name,
          children: [],
        };
        agentNodes.set(name, node);
        roots[0]?.children.push(node);
        break;
      }

      case "tool.called": {
        const agentName = String(event.data.agent_name || "");
        const parent = agentNodes.get(agentName);
        const toolNode: TraceNode = {
          type: "tool",
          label: String(event.data.tool_name || "tool"),
          toolName: String(event.data.tool_name || ""),
          children: [],
        };
        if (parent) {
          parent.children.push(toolNode);
          parent.label = "";
        }
        break;
      }

      case "memory.hit": {
        const agentName = String(event.data.agent_name || "");
        const parent = agentNodes.get(agentName);
        const memNode: TraceNode = {
          type: "memory",
          label: "Memory",
          details: `${event.data.count || 0} hits`,
          children: [],
        };
        if (parent) parent.children.push(memNode);
        break;
      }

      case "agent.completed": {
        const name = String(event.data.agent_name || "");
        const node = agentNodes.get(name);
        if (node) {
          node.durationMs = Number(event.data.duration_ms) || 0;
          node.success = true;
          node.details = String(event.data.summary || "");
        }
        break;
      }

      case "critic.issued": {
        const node: TraceNode = {
          type: "critic",
          label: "CriticAgent",
          details: `Score: ${event.data.score || "?"}, Issues: ${event.data.issue_count || 0}`,
          success: event.data.needs_replan ? undefined : true,
          durationMs: Number(event.data.duration_ms) || 0,
          children: [],
        };
        roots[0]?.children.push(node);
        break;
      }

      case "replan.started":
        roots[0]?.children.push({ type: "replan", label: "Replanning...", children: [] });
        break;

      case "run.completed":
      case "run.failed":
        if (roots[0]) {
          roots[0].label += event.type === "run.failed" ? " (FAILED)" : " (DONE)";
          roots[0].success = event.type === "run.completed";
        }
        break;
    }
  }

  return roots;
}

const ICON_MAP: Record<string, string> = {
  run: "🚀",
  plan: "📋",
  agent: "🤖",
  tool: "🔧",
  memory: "🧠",
  critic: "🔍",
  replan: "🔄",
};

const STATUS_COLOR = (node: TraceNode): string => {
  if (node.success === true) return "text-green-600";
  if (node.success === false) return "text-red-600";
  return "text-blue-500 animate-pulse";
};

function TraceRow({ node, depth = 0 }: { node: TraceNode; depth?: number }) {
  const icon = ICON_MAP[node.type] || "📌";
  const indent = depth * 24;

  return (
    <>
      <div
        className="flex items-center gap-2 py-1.5 px-2 hover:bg-gray-50 rounded text-sm"
        style={{ paddingLeft: 12 + indent }}
      >
        <span className="text-base flex-shrink-0">{icon}</span>
        <span className={`font-medium ${STATUS_COLOR(node)}`}>
          {node.agentName || node.toolName || node.label || node.type}
        </span>
        {node.durationMs != null && node.durationMs > 0 && (
          <span className="text-xs text-gray-400 ml-auto flex-shrink-0">{node.durationMs}ms</span>
        )}
        {node.details && (
          <span className="text-xs text-gray-500 truncate max-w-[300px]">{node.details}</span>
        )}
        {node.type === "memory" && (
          <Badge variant="outline" className="text-xs bg-pink-50 text-pink-700 flex-shrink-0">
            {node.details}
          </Badge>
        )}
        {node.type === "critic" && (
          <Badge
            variant="outline"
            className={`text-xs flex-shrink-0 ${
              node.success === true ? "bg-green-50 text-green-700" : "bg-orange-50 text-orange-700"
            }`}
          >
            {node.success === true ? "PASS" : "REPLAN"}
          </Badge>
        )}
      </div>
      {node.children.map((child, i) => (
        <TraceRow key={i} node={child} depth={depth + 1} />
      ))}
    </>
  );
}

export default function AgentTraceTree({ events, isRunning }: Props) {
  const tree = buildTraceTree(events);

  return (
    <Card className="bg-white border shadow-sm">
      <CardHeader className="pb-2">
        <CardTitle className="text-base flex items-center gap-2">
          <span>🧭 Agent Execution Trace</span>
          {isRunning && (
            <Badge variant="outline" className="text-xs animate-pulse bg-blue-50">
              LIVE
            </Badge>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent className="pt-0">
        {tree.length === 0 ? (
          <p className="text-sm text-gray-400 text-center py-6">Waiting for agent execution...</p>
        ) : (
          <div className="font-mono text-sm border rounded-lg p-2 bg-gray-50 max-h-[600px] overflow-auto">
            {tree.map((node, i) => (
              <TraceRow key={i} node={node} />
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
