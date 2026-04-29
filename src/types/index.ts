// SSE Event types from backend
export interface SSERunEvent {
  type: string;
  run_id: string;
  timestamp: number;
  data: Record<string, unknown>;
}

export type SSEEventType =
  | "run.created"
  | "plan.generated"
  | "step.started"
  | "tool.called"
  | "tool.completed"
  | "memory.hit"
  | "agent.completed"
  | "critic.issued"
  | "replan.started"
  | "run.completed"
  | "run.failed";

// Run status
export interface RunStatus {
  run_id: string;
  status: "pending" | "running" | "completed" | "failed" | "replanning";
  current_agent: string | null;
  completed_agents: string[];
  failed_agents: string[];
  events: SSERunEvent[];
  result: TravelPlanResult | null;
}

// Travel plan result
export interface TravelPlanResult {
  id?: string;
  source_run_id?: string;
  created_at?: string;
  updated_at?: string;
  status?: string;
  destination: string;
  duration: number;
  start_date: string;
  budget: number;
  preferences: string[];
  weather: WeatherResult | null;
  daily_plans: DailyPlan[];
  map_data: MapData | null;
  budget_breakdown: BudgetBreakdown | null;
  critic_report: CriticReport | null;
  memory_context: MemoryContext | null;
}

export interface WeatherResult {
  forecast: DailyWeather[];
  risk_analysis: string;
}

export interface DailyWeather {
  date: string;
  condition: string;
  temp_high: number;
  temp_low: number;
  humidity: number;
  recommendation: string;
  risk_level?: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
  source?: "qweather" | "fallback";
}

export interface DailyPlan {
  day: number;
  date: string;
  activities: Activity[];
  meals: Meal[];
  notes: string;
}

export interface Activity {
  id: string;
  name: string;
  type: "sightseeing" | "shopping" | "entertainment" | "outdoor" | "cultural" | "transport";
  description: string;
  location: string;
  duration: string;
  time: string;
  cost: number;
  source?: string; // RAG citation
  coordinate?: Coordinate | null;
}

export interface Meal {
  id: string;
  name: string;
  type: "breakfast" | "lunch" | "dinner" | "snack";
  cuisine: string;
  location: string;
  time: string;
  cost: number;
  source?: string;
  coordinate?: Coordinate | null;
}

export interface Coordinate {
  lng: number;
  lat: number;
}

export interface MapData {
  destination: string;
  center: {
    formatted_address?: string;
    city?: string;
    location?: Coordinate;
    source?: string;
  } | null;
  attractions: POI[];
  food: POI[];
  hotels: POI[];
  routes: RouteSummary[];
}

export interface POI {
  id: string;
  name: string;
  type: string;
  address: string;
  location: Coordinate | null;
  rating?: string;
  cost?: string;
  photo?: string;
  source?: string;
}

export interface RouteSummary {
  from: string;
  to: string;
  mode: "walking" | "driving" | "bicycling";
  distance_m: number;
  duration_min: number;
  strategy?: string;
  source?: string;
}

export interface BudgetBreakdown {
  total_budget: number;
  allocated: Record<string, number>;
  spent: number;
  warnings: string[];
}

export interface CriticReport {
  score: number;
  issues: CriticIssue[];
  suggestions: string[];
  needs_replan: boolean;
}

export interface CriticIssue {
  severity: "low" | "medium" | "high";
  category: "budget" | "route" | "weather" | "pace" | "preference";
  description: string;
  suggestion: string;
}

export interface MemoryContext {
  short_term: MemoryItem[];
  long_term: MemoryItem[];
}

export interface MemoryItem {
  memory_type: string;
  content: string;
  confidence: number;
  source: string;
}
