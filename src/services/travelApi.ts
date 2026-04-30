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
  web_search_provider: string;
  web_search_api_key: string;
  web_search_base_url: string;
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

export interface RunStatusResponse {
  run_id: string;
  status: string;
  result?: TravelPlanResult | null;
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
      web_search_provider: parsed.webSearchProvider || "baidu",
      web_search_api_key: parsed.webSearchApiKey || "",
      web_search_base_url: parsed.webSearchBaseUrl || "https://qianfan.baidubce.com/v2/ai_search/web_search",
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

export async function fetchRunStatus(runId: string): Promise<RunStatusResponse> {
  const response = await apiClient.get<RunStatusResponse>(`/runs/${runId}`);
  return response.data;
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
  let settled = false;
  let pollTimer: number | null = null;

  const completeWithResult = (payload: Partial<RunCompletedPayload>) => {
    if (!payload.result || settled) return false;
    const result = {
      ...payload.result,
      id: payload.result.id || payload.plan_id || payload.result.source_run_id || runId,
      source_run_id: payload.result.source_run_id || runId,
    };
    settled = true;
    if (pollTimer) window.clearInterval(pollTimer);
    handlers.onCompleted({ result, plan_id: payload.plan_id ?? result.id });
    source.close();
    return true;
  };

  source.onmessage = (message) => {
    const event = JSON.parse(message.data) as SSERunEvent;
    handlers.onEvent(event);

    if (event.type === "run.completed") {
      const payload = event.data as unknown as Partial<RunCompletedPayload>;
      completeWithResult(payload);
    }

    if (event.type === "run.failed") {
      const error = typeof event.data.error === "string" ? event.data.error : "规划失败";
      settled = true;
      if (pollTimer) window.clearInterval(pollTimer);
      handlers.onFailed(error);
      source.close();
    }
  };

  pollTimer = window.setInterval(async () => {
    if (settled) return;
    try {
      const status = await fetchRunStatus(runId);
      if (status.status === "completed" && status.result) {
        completeWithResult({ result: status.result, plan_id: status.result.id });
      }
      if (status.status === "failed") {
        settled = true;
        if (pollTimer) window.clearInterval(pollTimer);
        handlers.onFailed("规划失败");
        source.close();
      }
    } catch {
      // SSE is still the primary channel; polling only prevents a completed run from being stranded.
    }
  }, 2500);

  source.onerror = async () => {
    if (settled) return;
    source.close();
    for (let attempt = 0; attempt < 6; attempt += 1) {
      try {
        const status = await fetchRunStatus(runId);
        if (status.status === "completed" && status.result) {
          completeWithResult({ result: status.result, plan_id: status.result.id });
          return;
        }
        if (status.status === "failed") {
          settled = true;
          if (pollTimer) window.clearInterval(pollTimer);
          handlers.onFailed("规划失败");
          return;
        }
      } catch {
        // keep polling; the run result may not be committed yet
      }
      await new Promise((resolve) => window.setTimeout(resolve, 1200));
    }
    settled = true;
    if (pollTimer) window.clearInterval(pollTimer);
    handlers.onFailed("规划结果连接中断，请在我的行程中查看是否已保存");
  };

  const originalClose = source.close.bind(source);
  source.close = () => {
    if (pollTimer) window.clearInterval(pollTimer);
    originalClose();
  };

  return source;
}
