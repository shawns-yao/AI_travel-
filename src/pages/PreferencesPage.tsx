import { useState } from "react";
import { Check, CloudSun, KeyRound, ListRestart, MapPin, Save, Server, Sparkles, TestTube2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ConfigCheck, fetchProviderModels, testApiSettings } from "@/services/travelApi";

type ServiceStatus = "connected" | "missing" | "local";
type LLMProvider = "openai-compatible" | "anthropic";

interface ApiSettings {
  llmProvider: LLMProvider;
  llmBaseUrl: string;
  llmModel: string;
  llmApiKey: string;
  qweatherApiKey: string;
  qweatherHost: string;
  qweatherLocation: string;
  qweatherAdm: string;
  amapApiKey: string;
  amapServiceKey: string;
  amapJsUrl: string;
  backendBaseUrl: string;
}

const storageKey = "ai-travel-api-settings";

const defaultSettings: ApiSettings = {
  llmProvider: "openai-compatible",
  llmBaseUrl: "https://api.openai.com/v1",
  llmModel: "",
  llmApiKey: "",
  qweatherApiKey: "",
  qweatherHost: "devapi.qweather.com",
  qweatherLocation: "杭州",
  qweatherAdm: "",
  amapApiKey: "",
  amapServiceKey: "",
  amapJsUrl: "https://webapi.amap.com/maps?v=2.0&key={key}",
  backendBaseUrl: "http://127.0.0.1:8001",
};

const loadSettings = (): ApiSettings => {
  try {
    const saved = localStorage.getItem(storageKey);
    const merged = saved ? { ...defaultSettings, ...(JSON.parse(saved) as Partial<ApiSettings>) } : defaultSettings;
    if (["gpt-4o-mini", "claude-sonnet-4-5"].includes(merged.llmModel)) {
      return { ...merged, llmModel: "" };
    }
    return merged;
  } catch {
    return defaultSettings;
  }
};

const maskKey = (value: string) => {
  if (!value) return "未配置";
  if (value.length <= 8) return "********";
  return `${value.slice(0, 4)}****${value.slice(-4)}`;
};

const statusText: Record<ServiceStatus, string> = {
  connected: "已配置",
  missing: "待配置",
  local: "本地代理",
};

const toPayload = (settings: ApiSettings) => ({
  llm_provider: settings.llmProvider,
  llm_base_url: settings.llmBaseUrl,
  llm_model: settings.llmModel,
  llm_api_key: settings.llmApiKey,
  qweather_api_key: settings.qweatherApiKey,
  qweather_host: settings.qweatherHost,
  qweather_location: settings.qweatherLocation,
  qweather_adm: settings.qweatherAdm,
  amap_api_key: settings.amapApiKey,
  amap_service_key: settings.amapServiceKey || settings.amapApiKey,
  amap_js_url: settings.amapJsUrl,
  backend_base_url: settings.backendBaseUrl,
});

export function PreferencesPage() {
  const [settings, setSettings] = useState<ApiSettings>(loadSettings);
  const [saved, setSaved] = useState(false);
  const [testState, setTestState] = useState("未测试");
  const [checks, setChecks] = useState<ConfigCheck[]>([]);
  const [models, setModels] = useState<string[]>([]);
  const [modelState, setModelState] = useState("未获取");

  const update = (key: keyof ApiSettings, value: string) => {
    setSaved(false);
    setTestState("未测试");
    setChecks([]);
    setSettings((current) => ({ ...current, [key]: value }));
  };

  const selectProvider = (provider: LLMProvider) => {
    setSaved(false);
    setModels([]);
    setModelState("未获取");
    setTestState("未测试");
    setChecks([]);
    setSettings((current) => ({
      ...current,
      llmProvider: provider,
      llmBaseUrl: provider === "anthropic" ? "https://api.anthropic.com/v1" : "https://api.openai.com/v1",
      llmModel: "",
    }));
  };

  const save = () => {
    localStorage.setItem(storageKey, JSON.stringify(settings));
    setSaved(true);
  };

  const testConnection = async () => {
    setTestState("测试中...");
    setChecks([]);
    try {
      const result = await testApiSettings(toPayload(settings));
      setChecks(result.checks);
      if (result.models.length) setModels(result.models);
      setTestState(result.status === "ok" ? "全部可用" : "部分可用");
    } catch {
      setTestState("后端不可用");
    }
  };

  const fetchModels = async () => {
    if (!settings.llmApiKey) {
      setModelState("请先填写 API Key");
      return;
    }
    setModelState("获取中...");
    try {
      const list = await fetchProviderModels(toPayload(settings));
      setModels(list.slice(0, 12));
      if (list.length && !settings.llmModel) update("llmModel", list[0]);
      setModelState(list.length ? `已获取 ${list.length} 个模型` : "没有返回模型");
    } catch {
      setModelState("获取失败");
    }
  };

  const cards: Array<{ title: string; value: string; status: ServiceStatus; icon: typeof Sparkles }> = [
    { title: "LLM", value: settings.llmModel || "未选择模型", status: settings.llmApiKey ? "connected" : "missing", icon: Sparkles },
    { title: "和风天气", value: maskKey(settings.qweatherApiKey), status: settings.qweatherApiKey ? "connected" : "missing", icon: CloudSun },
    { title: "高德地图", value: maskKey(settings.amapApiKey), status: settings.amapApiKey ? "connected" : "missing", icon: MapPin },
    { title: "FastAPI", value: settings.backendBaseUrl, status: "local", icon: Server },
  ];
  const modelOptions = Array.from(new Set([settings.llmModel, ...models].filter(Boolean)));

  return (
    <section className="min-h-[calc(100vh-68px)] bg-gradient-to-br from-cyan-50 via-white to-white">
      <div className="mx-auto max-w-[1240px] px-8 py-10">
        <div className="mb-8 flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <h1 className="text-4xl font-black tracking-normal text-slate-950">服务配置</h1>
            <div className="mt-3 text-sm font-medium text-slate-500">LLM、天气、地图、本地后端</div>
          </div>
          <div className="flex flex-wrap gap-3">
            <Button variant="outline" onClick={testConnection} className="h-12 rounded-xl px-6 text-[#0da8ad]">
              <TestTube2 className="h-4 w-4" />
              测试配置
            </Button>
            <Button onClick={save} className="h-12 rounded-xl bg-[#10b8bd] px-7 text-white shadow-lg shadow-cyan-200 hover:bg-[#0ca8ad]">
              {saved ? <Check className="h-4 w-4" /> : <Save className="h-4 w-4" />}
              {saved ? "已保存" : "保存配置"}
            </Button>
          </div>
        </div>

        <div className="mb-6 grid gap-4 lg:grid-cols-4">
          {cards.map((card) => {
            const Icon = card.icon;
            const active = card.status !== "missing";
            return (
              <div key={card.title} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
                <div className="mb-4 flex items-center justify-between">
                  <div className={`flex h-11 w-11 items-center justify-center rounded-2xl ${active ? "bg-cyan-50 text-[#0da8ad]" : "bg-slate-100 text-slate-400"}`}>
                    <Icon className="h-5 w-5" />
                  </div>
                  <span className={`rounded-full px-3 py-1 text-xs font-semibold ${active ? "bg-emerald-50 text-emerald-600" : "bg-amber-50 text-amber-600"}`}>
                    {statusText[card.status]}
                  </span>
                </div>
                <div className="text-lg font-black">{card.title}</div>
                <div className="mt-2 truncate text-sm text-slate-500">{card.value}</div>
              </div>
            );
          })}
        </div>

        <div className="grid gap-6 xl:grid-cols-[1fr_340px]">
          <div className="space-y-6">
            <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
              <div className="mb-5 flex items-center gap-3">
                <Sparkles className="h-5 w-5 text-[#0da8ad]" />
                <h2 className="text-xl font-black">LLM</h2>
              </div>
              <div className="grid gap-4">
                <div>
                  <div className="mb-2 text-sm font-bold text-slate-700">Provider</div>
                  <Select value={settings.llmProvider} onValueChange={(value) => selectProvider(value as LLMProvider)}>
                    <SelectTrigger className="h-12 rounded-xl border-slate-200 bg-white text-sm font-bold shadow-none focus:ring-[#10b8bd]">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="openai-compatible">OpenAI 兼容</SelectItem>
                      <SelectItem value="anthropic">Anthropic</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <div className="mb-2 flex items-center justify-between">
                    <span className="text-sm font-bold text-slate-700">Model</span>
                    <button type="button" onClick={fetchModels} className="text-xs font-bold text-[#0da8ad]">
                      <ListRestart className="mr-1 inline h-3.5 w-3.5" />
                      获取模型
                    </button>
                  </div>
                  <Select value={settings.llmModel || undefined} onValueChange={(value) => update("llmModel", value)} disabled={!modelOptions.length}>
                    <SelectTrigger className="h-12 rounded-xl border-slate-200 bg-white text-sm font-bold shadow-none focus:ring-[#10b8bd]">
                      <SelectValue placeholder="先获取模型" />
                    </SelectTrigger>
                    <SelectContent>
                      {modelOptions.map((model) => (
                        <SelectItem key={model} value={model}>{model}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <div className="mt-2 text-xs font-medium text-slate-400">{modelState}</div>
                </div>
                <Field label="Base URL" value={settings.llmBaseUrl} onChange={(value) => update("llmBaseUrl", value)} />
                <Field label="API Key" type="password" value={settings.llmApiKey} onChange={(value) => update("llmApiKey", value)} />
              </div>
            </section>

            <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
              <div className="mb-5 flex items-center gap-3">
                <CloudSun className="h-5 w-5 text-[#0da8ad]" />
                <h2 className="text-xl font-black">和风天气</h2>
              </div>
              <div className="grid gap-4">
                <Field label="API Host" value={settings.qweatherHost} onChange={(value) => update("qweatherHost", value)} />
                <Field label="查询地区" value={settings.qweatherLocation} onChange={(value) => update("qweatherLocation", value)} />
                <Field label="上级行政区" value={settings.qweatherAdm} onChange={(value) => update("qweatherAdm", value)} />
                <Field label="API Key" type="password" value={settings.qweatherApiKey} onChange={(value) => update("qweatherApiKey", value)} />
              </div>
            </section>

            <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
              <div className="mb-5 flex items-center gap-3">
                <MapPin className="h-5 w-5 text-[#0da8ad]" />
                <h2 className="text-xl font-black">高德地图</h2>
              </div>
              <div className="grid gap-4">
                <Field label="Web / JS API Key" type="password" value={settings.amapApiKey} onChange={(value) => update("amapApiKey", value)} />
                <Field label="Web 服务 API Key" type="password" value={settings.amapServiceKey} onChange={(value) => update("amapServiceKey", value)} />
                <Field label="JS API URL" value={settings.amapJsUrl} onChange={(value) => update("amapJsUrl", value)} />
              </div>
            </section>
          </div>

          <aside className="space-y-6">
            <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
              <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-cyan-50 text-[#0da8ad]">
                <KeyRound className="h-7 w-7" />
              </div>
              <h2 className="text-xl font-black">配置状态</h2>
              <div className="mt-5 space-y-3 text-sm">
                {[
                  ["LLM Key", settings.llmApiKey],
                  ["和风天气 Key", settings.qweatherApiKey],
                  ["高德 API Key", settings.amapApiKey],
                  ["高德服务 Key", settings.amapServiceKey || settings.amapApiKey],
                  ["后端地址", settings.backendBaseUrl],
                ].map(([label, value]) => (
                  <div key={label} className="flex items-center justify-between rounded-xl bg-slate-50 px-4 py-3">
                    <span className="font-medium text-slate-600">{label}</span>
                    <span className={value ? "font-bold text-[#0da8ad]" : "font-bold text-amber-600"}>{value ? "OK" : "缺失"}</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-2xl border border-cyan-100 bg-cyan-50/80 p-6 shadow-sm">
              <div className="text-sm font-semibold text-slate-500">测试结果</div>
              <div className="mt-2 text-2xl font-black text-slate-950">{testState}</div>
              <div className="mt-5 space-y-3">
                {checks.length ? checks.map((item) => (
                  <div key={item.name} className="rounded-xl bg-white/85 px-4 py-3 text-sm">
                    <div className="flex items-center justify-between gap-3">
                      <span className="font-bold text-slate-800">{item.name}</span>
                      <span className={item.ok ? "font-black text-[#0da8ad]" : "font-black text-amber-600"}>
                        {item.ok ? "OK" : "失败"}
                      </span>
                    </div>
                    <div className="mt-1 line-clamp-2 text-slate-500">{item.message}</div>
                  </div>
                )) : (
                  <div className="rounded-xl bg-white/85 px-4 py-3 text-sm font-medium text-slate-500">等待测试</div>
                )}
              </div>
            </div>
          </aside>
        </div>
      </div>
    </section>
  );
}

interface FieldProps {
  label: string;
  value: string;
  type?: "text" | "password";
  onChange: (value: string) => void;
}

function Field({ label, value, type = "text", onChange }: FieldProps) {
  return (
    <label className="block">
      <span className="mb-2 block text-sm font-bold text-slate-700">{label}</span>
      <Input
        type={type}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="h-12 rounded-xl border-slate-200 bg-white text-sm shadow-none focus-visible:ring-[#10b8bd]"
      />
    </label>
  );
}
