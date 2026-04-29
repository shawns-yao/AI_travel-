import { useEffect, useMemo, useRef, useState } from "react";
import { MapPin } from "lucide-react";
import { Coordinate, MapData } from "@/types";

interface RouteMapMockProps {
  mapData?: MapData | null;
  muted?: boolean;
  previewLabel?: string;
}

declare global {
  interface Window {
    AMap?: AMapNamespace;
  }
}

let amapLoader: Promise<void> | null = null;

interface AMapInstance {
  setFitView: (overlays: AMapOverlay[], immediately?: boolean, avoid?: number[]) => void;
  destroy: () => void;
}

interface AMapOverlay {
  setMap: (map: AMapInstance) => void;
}

interface AMapNamespace {
  Map: new (
    container: HTMLElement,
    options: {
      zoom: number;
      center: [number, number];
      resizeEnable: boolean;
      mapStyle: string;
    },
  ) => AMapInstance;
  Marker: new (options: {
    position: [number, number];
    title: string;
    label: { content: string; direction: string };
  }) => AMapOverlay;
  Polyline: new (options: {
    path: [number, number][];
    strokeColor: string;
    strokeWeight: number;
    strokeStyle: string;
    lineJoin: string;
  }) => AMapOverlay;
}

const fallbackNames = ["灵隐寺", "断桥残雪", "河坊街", "南宋御街", "白堤"];
const fallbackCenter: Coordinate = { lng: 120.1551, lat: 30.2741 };

const loadApiSettings = () => {
  try {
    const saved = localStorage.getItem("ai-travel-api-settings");
    return saved ? JSON.parse(saved) as { amapApiKey?: string; amapJsUrl?: string } : {};
  } catch {
    return {};
  }
};

const buildAmapUrl = (key: string, urlTemplate?: string) => {
  const clean = (urlTemplate || "https://webapi.amap.com/maps?v=2.0&key={key}")
    .replace(/[^\x20-\x7E]/g, "")
    .replace("您的密钥", "{key}")
    .replace("YOUR_KEY", "{key}")
    .trim()
    .replace(/^<script[^>]*src=["']?/i, "")
    .replace(/["']?\s*>?$/i, "");
  const template = clean || "https://webapi.amap.com/maps?v=2.0&key={key}";
  if (template.includes("{key}")) return template.replace("{key}", encodeURIComponent(key));
  if (template.includes("key=")) return template;
  const joiner = template.includes("?") ? "&" : "?";
  return `${template}${joiner}key=${encodeURIComponent(key)}`;
};

const loadAmap = (key: string, urlTemplate?: string) => {
  if (window.AMap) return Promise.resolve();
  if (!amapLoader) {
    amapLoader = new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = buildAmapUrl(key, urlTemplate);
      script.async = true;
      script.onload = () => resolve();
      script.onerror = () => reject(new Error("AMap load failed"));
      document.head.appendChild(script);
    });
  }
  return amapLoader;
};

const getPoints = (mapData?: MapData | null) =>
  (mapData?.attractions ?? [])
    .filter((point) => point.location)
    .slice(0, 5)
    .map((point) => ({
      name: point.name,
      location: point.location as Coordinate,
    }));

export function RouteMapMock({ mapData, muted = false, previewLabel }: RouteMapMockProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<AMapInstance | null>(null);
  const [mapReady, setMapReady] = useState(false);
  const [mapFailed, setMapFailed] = useState(false);
  const apiSettings = useMemo(loadApiSettings, []);
  const realPoints = useMemo(() => getPoints(mapData), [mapData]);
  const center = mapData?.center?.location ?? realPoints[0]?.location ?? fallbackCenter;
  const shouldUseLiveMap = Boolean(apiSettings.amapApiKey && !muted);
  const fallbackPointNames = useMemo(
    () => (mapData?.attractions?.length ? mapData.attractions.map((p) => p.name) : fallbackNames).slice(0, 5),
    [mapData],
  );
  const routeDistance = mapData?.routes?.[0]?.distance_m ? (mapData.routes[0].distance_m / 1000).toFixed(1) : realPoints.length ? "0.7" : "8.6";

  useEffect(() => {
    if (!shouldUseLiveMap || !containerRef.current) return;
    let cancelled = false;

    loadAmap(apiSettings.amapApiKey || "", apiSettings.amapJsUrl)
      .then(() => {
        if (cancelled || !containerRef.current || !window.AMap) return;
        const AMap = window.AMap;
        containerRef.current.innerHTML = "";
        const map = new AMap.Map(containerRef.current, {
          zoom: 12,
          center: [center.lng, center.lat],
          resizeEnable: true,
          mapStyle: "amap://styles/normal",
        });

        const points = realPoints.length
          ? realPoints
          : fallbackPointNames.map((name, index) => ({
              name,
              location: { lng: fallbackCenter.lng + index * 0.012, lat: fallbackCenter.lat + (index % 2) * 0.01 },
            }));

        const markers = points.map((point, index) => {
          const marker = new AMap.Marker({
            position: [point.location.lng, point.location.lat],
            title: point.name,
            label: {
              content: `<div style="padding:4px 8px;border-radius:999px;background:white;box-shadow:0 6px 18px rgba(15,23,42,.16);font-weight:700;color:#0f172a;">${index + 1} ${point.name}</div>`,
              direction: "right",
            },
          });
          marker.setMap(map);
          return marker;
        });

        if (points.length > 1) {
          const path = points.map((point): [number, number] => [point.location.lng, point.location.lat]);
          const polyline = new AMap.Polyline({
            path,
            strokeColor: "#10b8bd",
            strokeWeight: 5,
            strokeStyle: "dashed",
            lineJoin: "round",
          });
          polyline.setMap(map);
        }

        if (markers.length) map.setFitView(markers, false, [40, 40, 40, 40]);
        mapRef.current = map;
        setMapReady(true);
        setMapFailed(false);
      })
      .catch(() => {
        setMapFailed(true);
        setMapReady(false);
      });

    return () => {
      cancelled = true;
      if (mapRef.current) {
        mapRef.current.destroy();
        mapRef.current = null;
      }
    };
  }, [apiSettings.amapApiKey, apiSettings.amapJsUrl, center.lat, center.lng, fallbackPointNames, realPoints, shouldUseLiveMap]);

  if (shouldUseLiveMap && !mapFailed) {
    return (
      <div className="relative min-h-[330px] overflow-hidden rounded-2xl border border-cyan-100 bg-[#eaf7f5] shadow-sm">
        <div ref={containerRef} className="absolute inset-0" />
        {!mapReady && <FallbackMap points={fallbackPointNames} routeDistance={routeDistance} muted={muted} label={previewLabel || "地图加载中"} />}
        <div className="absolute bottom-4 left-4 rounded-full bg-white/95 px-4 py-2 text-sm text-slate-700 shadow">
          <MapPin className="mr-2 inline h-4 w-4 text-[#0da8ad]" />
          实时高德地图
          <span className="ml-2 font-semibold text-[#0da8ad]">约 {routeDistance} 公里</span>
        </div>
      </div>
    );
  }

  return (
    <FallbackMap
      points={fallbackPointNames}
      routeDistance={routeDistance}
      muted={muted}
      label={previewLabel || (apiSettings.amapApiKey ? "地图预览" : "未配置高德 Key，显示路线预览")}
    />
  );
}

interface FallbackMapProps {
  points: string[];
  routeDistance: string;
  muted: boolean;
  label: string;
}

function FallbackMap({ points, routeDistance, muted, label }: FallbackMapProps) {
  return (
    <div className="relative min-h-[330px] overflow-hidden rounded-2xl border border-cyan-100 bg-[#eaf7f5] shadow-sm">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_45%_45%,#bdebf1_0,#dff6f7_32%,#f5fbfb_70%)]" />
      <div className="absolute left-[10%] top-[18%] h-[220px] w-[72%] rounded-[50%] border-2 border-dashed border-[#16b7bd]" />
      <div className="absolute left-[28%] top-[28%] h-[125px] w-[230px] rounded-[45%] bg-cyan-200/55 blur-sm" />
      <div className="absolute inset-0 opacity-40 [background-image:linear-gradient(#cfe4e9_1px,transparent_1px),linear-gradient(90deg,#cfe4e9_1px,transparent_1px)] [background-size:26px_26px]" />
      <div className="absolute inset-0 bg-white/20" />
      {points.slice(0, 5).map((name, index) => {
        const positions = [
          ["63%", "68%"],
          ["51%", "31%"],
          ["72%", "36%"],
          ["78%", "62%"],
          ["57%", "77%"],
        ][index] ?? ["50%", "50%"];
        return (
          <div key={`${name}-${index}`} className="absolute -translate-x-1/2 -translate-y-1/2" style={{ left: positions[0], top: positions[1] }}>
            <div className="flex items-center gap-2 rounded-full bg-white/90 px-2 py-1 text-xs font-bold text-slate-800 shadow">
              <span className="flex h-7 w-7 items-center justify-center rounded-full bg-[#12b9bd] text-white">{index + 1}</span>
              {name}
            </div>
          </div>
        );
      })}
      <div className="absolute bottom-4 left-4 rounded-full bg-white/90 px-4 py-2 text-sm text-slate-700 shadow">
        <MapPin className="mr-2 inline h-4 w-4 text-[#0da8ad]" />
        {label}
        <span className="ml-2 font-semibold text-[#0da8ad]">约 {routeDistance} 公里</span>
      </div>
      {muted && <div className="absolute inset-0 bg-white/60 backdrop-blur-[1px]" />}
    </div>
  );
}
