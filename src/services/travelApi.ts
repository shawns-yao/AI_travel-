import axios from "axios";
import { SSERunEvent, TravelPlanResult } from "@/types";

export interface CreateRunResponse {
  run_id: string;
  status: string;
  created_at?: string;
}

export interface RunCompletedPayload {
  result: TravelPlanResult;
  plan_id?: string | null;
}

export interface ApiSettingsPayload {
  llm_provider: "openai-compatible" | "anthropic";
  llm_base_url: string;
  llm_model: string;
  llm_api_key: string;
  qweather_api_key: string;
  qweather_host: string;
  qweather_location: string;
  qweather_adm: string;
  amap_api_key: string;
  amap_service_key: string;
  amap_js_url: string;
  backend_base_url: string;
}

export interface ConfigCheck {
  name: string;
  ok: boolean;
  message: string;
}

export interface ConfigTestResponse {
  status: string;
  checks: ConfigCheck[];
  models: string[];
}

export const apiClient = axios.create({
  baseURL: "/api",
  headers: {
    "Content-Type": "application/json",
  },
});

const loadApiSettings = (): ApiSettingsPayload | null => {
  try {
    const saved = localStorage.getItem("ai-travel-api-settings");
    if (!saved) return null;
    const parsed = JSON.parse(saved);
    return {
      llm_provider: parsed.llmProvider || "openai-compatible",
      llm_base_url: parsed.llmBaseUrl || "",
      llm_model: parsed.llmModel || "",
      llm_api_key: parsed.llmApiKey || "",
      qweather_api_key: parsed.qweatherApiKey || "",
      qweather_host: parsed.qweatherHost || "devapi.qweather.com",
      qweather_location: parsed.qweatherLocation || "杭州",
      qweather_adm: parsed.qweatherAdm || "",
      amap_api_key: parsed.amapApiKey || "",
      amap_service_key: parsed.amapServiceKey || parsed.amapApiKey || "",
      amap_js_url: parsed.amapJsUrl || "https://webapi.amap.com/maps?v=2.0&key={key}",
      backend_base_url: parsed.backendBaseUrl || "",
    };
  } catch {
    return null;
  }
};

export async function createTravelRun(query: string): Promise<CreateRunResponse> {
  const response = await apiClient.post<CreateRunResponse>("/runs", { query, api_settings: loadApiSettings() });
  return response.data;
}

export async function fetchSavedPlans(): Promise<TravelPlanResult[]> {
  const response = await apiClient.get<{ plans: TravelPlanResult[] }>("/plans");
  return response.data.plans;
}

export async function deleteSavedPlan(planId: string): Promise<void> {
  await apiClient.delete(`/plans/${planId}`);
}

export async function testApiSettings(settings: ApiSettingsPayload): Promise<ConfigTestResponse> {
  const response = await apiClient.post<ConfigTestResponse>("/config/test", settings);
  return response.data;
}

export async function fetchProviderModels(settings: ApiSettingsPayload): Promise<string[]> {
  const response = await apiClient.post<{ models: string[] }>("/config/models", settings);
  return response.data.models;
}

export function subscribeRunEvents(
  runId: string,
  handlers: {
    onEvent: (event: SSERunEvent) => void;
    onCompleted: (payload: RunCompletedPayload) => void;
    onFailed: (message: string) => void;
  },
): EventSource {
  const source = new EventSource(`/api/runs/${runId}/events`);

  source.onmessage = (message) => {
    const event = JSON.parse(message.data) as SSERunEvent;
    handlers.onEvent(event);

    if (event.type === "run.completed") {
      const payload = event.data as unknown as Partial<RunCompletedPayload>;
      if (payload.result) {
        const result = {
          ...payload.result,
          id: payload.result.id || payload.plan_id || payload.result.source_run_id || runId,
          source_run_id: payload.result.source_run_id || runId,
        };
        handlers.onCompleted({ result, plan_id: payload.plan_id ?? result.id });
        source.close();
      }
    }

    if (event.type === "run.failed") {
      const error = typeof event.data.error === "string" ? event.data.error : "规划失败";
      handlers.onFailed(error);
      source.close();
    }
  };

  source.onerror = () => {
    handlers.onFailed("SSE 连接中断");
    source.close();
  };

  return source;
}
