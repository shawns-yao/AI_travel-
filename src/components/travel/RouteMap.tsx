import { useEffect, useMemo, useRef, useState } from "react";
import { MapPin } from "lucide-react";
import { Coordinate, MapData } from "@/types";

interface RouteMapProps {
  mapData?: MapData | null;
  muted?: boolean;
  previewLabel?: string;
  heightClass?: string;
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

const routeRank = (name: string) => {
  const order = [
    ["三丘田", "电影音乐", "风琴博物馆", "八卦楼"],
    ["长寿园"],
    ["龙头路", "街心公园", "鼓浪屿风景名胜区"],
    ["港仔后", "沙滩", "日光岩", "菽庄"],
    ["皓月园"],
  ];
  const index = order.findIndex((keywords) => keywords.some((keyword) => name.includes(keyword)));
  return index >= 0 ? index : order.length;
};

const distance = (a: Coordinate, b: Coordinate) => {
  const latScale = 111_000;
  const lngScale = Math.cos(((a.lat + b.lat) / 2) * Math.PI / 180) * 111_000;
  const dx = (a.lng - b.lng) * lngScale;
  const dy = (a.lat - b.lat) * latScale;
  return Math.sqrt(dx * dx + dy * dy);
};

const optimizePointOrder = (points: { name: string; location: Coordinate }[]) => {
  if (points.length <= 2) return points;
  const remaining = [...points];
  const startIndex = remaining.reduce((bestIndex, point, index) => {
    const best = remaining[bestIndex];
    const rankDelta = routeRank(point.name) - routeRank(best.name);
    if (rankDelta !== 0) return rankDelta < 0 ? index : bestIndex;
    if (point.location.lng !== best.location.lng) return point.location.lng < best.location.lng ? index : bestIndex;
    return point.location.lat > best.location.lat ? index : bestIndex;
  }, 0);
  const ordered = [remaining.splice(startIndex, 1)[0]];

  while (remaining.length) {
    const current = ordered[ordered.length - 1];
    let nextIndex = 0;
    for (let index = 1; index < remaining.length; index += 1) {
      const candidateDistance = distance(current.location, remaining[index].location);
      const bestDistance = distance(current.location, remaining[nextIndex].location);
      if (candidateDistance < bestDistance) nextIndex = index;
    }
    ordered.push(remaining.splice(nextIndex, 1)[0]);
  }

  return ordered;
};

const getPoints = (mapData?: MapData | null) =>
  optimizePointOrder(
    [...(mapData?.attractions ?? [])]
      .filter((point) => point.location)
      .map((point) => ({
        name: point.name,
        location: point.location as Coordinate,
      })),
  );

const coordinateKey = (point?: Coordinate) =>
  point ? `${point.lng.toFixed(6)},${point.lat.toFixed(6)}` : "";

export function RouteMap({ mapData, muted = false, previewLabel, heightClass = "min-h-[330px]" }: RouteMapProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<AMapInstance | null>(null);
  const latestCenterRef = useRef<Coordinate | undefined>(undefined);
  const latestPointsRef = useRef<{ name: string; location: Coordinate }[]>([]);
  const [mapReady, setMapReady] = useState(false);
  const [mapFailed, setMapFailed] = useState(false);
  const apiSettings = useMemo(loadApiSettings, []);
  const realPoints = useMemo(() => getPoints(mapData), [mapData]);
  const center = mapData?.center?.location ?? realPoints[0]?.location;
  const pointSignature = useMemo(
    () => realPoints.map((point) => `${point.name}:${coordinateKey(point.location)}`).join("|"),
    [realPoints],
  );
  const centerSignature = coordinateKey(center);
  const shouldUseLiveMap = Boolean(apiSettings.amapApiKey && !muted && center && realPoints.length);
  const routeDistance = mapData?.routes?.[0]?.distance_m ? (mapData.routes[0].distance_m / 1000).toFixed(1) : "";

  latestCenterRef.current = center;
  latestPointsRef.current = realPoints;

  useEffect(() => {
    if (!shouldUseLiveMap || !containerRef.current || !centerSignature) return;
    let cancelled = false;

    loadAmap(apiSettings.amapApiKey || "", apiSettings.amapJsUrl)
      .then(() => {
        if (cancelled || !containerRef.current || !window.AMap) return;
        const AMap = window.AMap;
        const renderCenter = latestCenterRef.current;
        const renderPoints = latestPointsRef.current;
        if (!renderCenter || !renderPoints.length) return;
        containerRef.current.innerHTML = "";
        const map = new AMap.Map(containerRef.current, {
          zoom: 12,
          center: [renderCenter.lng, renderCenter.lat],
          resizeEnable: true,
          mapStyle: "amap://styles/normal",
        });

        const markers = renderPoints.map((point, index) => {
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

        if (renderPoints.length > 1) {
          const path = renderPoints.map((point): [number, number] => [point.location.lng, point.location.lat]);
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
  }, [apiSettings.amapApiKey, apiSettings.amapJsUrl, centerSignature, pointSignature, shouldUseLiveMap]);

  if (!realPoints.length) {
    return <EmptyMap label={previewLabel ? "等待地图数据" : "暂无地图数据"} muted={muted} heightClass={heightClass} />;
  }

  if (shouldUseLiveMap && !mapFailed) {
    return (
      <div className={`relative ${heightClass} overflow-hidden rounded-2xl border border-cyan-100 bg-[#eaf7f5] shadow-sm`}>
        <div ref={containerRef} className="absolute inset-0" />
        {!mapReady && <FallbackMap points={realPoints} routeDistance={routeDistance} muted={muted} label={previewLabel || "地图加载中"} heightClass={heightClass} />}
        <div className="absolute bottom-4 left-4 rounded-full bg-white/95 px-4 py-2 text-sm text-slate-700 shadow">
          <MapPin className="mr-2 inline h-4 w-4 text-[#0da8ad]" />
          实时高德地图
          {routeDistance && <span className="ml-2 font-semibold text-[#0da8ad]">约 {routeDistance} 公里</span>}
        </div>
      </div>
    );
  }

  return (
    <FallbackMap
      points={realPoints}
      routeDistance={routeDistance}
      muted={muted}
      label={previewLabel || (apiSettings.amapApiKey ? "地图预览" : "未配置高德 Key，显示路线预览")}
      heightClass={heightClass}
    />
  );
}

interface FallbackMapProps {
  points: { name: string; location: Coordinate }[];
  routeDistance: string;
  muted: boolean;
  label: string;
  heightClass: string;
}

function FallbackMap({ points, routeDistance, muted, label, heightClass }: FallbackMapProps) {
  const positionedPoints = useMemo(() => {
    if (!points.length) return [];
    if (points.length === 1) return [{ ...points[0], x: 50, y: 50 }];
    const lngs = points.map((point) => point.location.lng);
    const lats = points.map((point) => point.location.lat);
    const minLng = Math.min(...lngs);
    const maxLng = Math.max(...lngs);
    const minLat = Math.min(...lats);
    const maxLat = Math.max(...lats);
    const lngRange = Math.max(maxLng - minLng, 0.0008);
    const latRange = Math.max(maxLat - minLat, 0.0008);
    const clamp = (value: number) => Math.min(88, Math.max(12, value));

    return points.map((point) => ({
      ...point,
      x: clamp(12 + ((point.location.lng - minLng) / lngRange) * 76),
      y: clamp(88 - ((point.location.lat - minLat) / latRange) * 76),
    }));
  }, [points]);
  const pathPoints = positionedPoints.map((point) => `${point.x},${point.y}`).join(" ");

  return (
    <div className={`relative ${heightClass} overflow-hidden rounded-2xl border border-cyan-100 bg-[#eaf7f5] shadow-sm`}>
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_45%_45%,#bdebf1_0,#dff6f7_32%,#f5fbfb_70%)]" />
      <div className="absolute left-[28%] top-[28%] h-[125px] w-[230px] rounded-[45%] bg-cyan-200/55 blur-sm" />
      <div className="absolute inset-0 opacity-40 [background-image:linear-gradient(#cfe4e9_1px,transparent_1px),linear-gradient(90deg,#cfe4e9_1px,transparent_1px)] [background-size:26px_26px]" />
      <div className="absolute inset-0 bg-white/20" />
      {positionedPoints.length > 1 && (
        <svg className="absolute inset-0 h-full w-full" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
          <polyline points={pathPoints} fill="none" stroke="#16b7bd" strokeWidth="0.8" strokeDasharray="2 1.6" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      )}
      {positionedPoints.map((point, index) => (
        <div key={`${point.name}-${index}`} className="absolute -translate-x-1/2 -translate-y-1/2" style={{ left: `${point.x}%`, top: `${point.y}%` }}>
          <div className="flex max-w-[240px] items-center gap-2 rounded-full bg-white/90 px-2 py-1 text-xs font-bold text-slate-800 shadow">
            <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-[#12b9bd] text-white">{index + 1}</span>
            <span className="line-clamp-2">{point.name}</span>
          </div>
        </div>
      ))}
      <div className="absolute bottom-4 left-4 rounded-full bg-white/90 px-4 py-2 text-sm text-slate-700 shadow">
        <MapPin className="mr-2 inline h-4 w-4 text-[#0da8ad]" />
        {label}
        {routeDistance && <span className="ml-2 font-semibold text-[#0da8ad]">约 {routeDistance} 公里</span>}
      </div>
      {muted && <div className="absolute inset-0 bg-white/60 backdrop-blur-[1px]" />}
    </div>
  );
}

function EmptyMap({ label, muted, heightClass }: { label: string; muted: boolean; heightClass: string }) {
  return (
    <div className={`relative flex ${heightClass} items-center justify-center overflow-hidden rounded-2xl border border-slate-200 bg-slate-50 shadow-sm`}>
      <div className="absolute inset-0 opacity-45 [background-image:linear-gradient(#dbe6eb_1px,transparent_1px),linear-gradient(90deg,#dbe6eb_1px,transparent_1px)] [background-size:26px_26px]" />
      <div className="relative flex items-center gap-2 rounded-full bg-white px-4 py-2 text-sm font-semibold text-slate-500 shadow-sm">
        <MapPin className="h-4 w-4 text-slate-400" />
        {label}
      </div>
      {muted && <div className="absolute inset-0 bg-white/60 backdrop-blur-[1px]" />}
    </div>
  );
}
