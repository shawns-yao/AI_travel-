import { Activity, POI, TravelPlanResult } from "@/types";

const sourceKeywords = [
  "三丘田", "内厝澳", "龙头路", "街心公园", "老别墅", "港仔后", "日光岩", "菽庄",
  "皓月园", "长寿园", "风琴博物馆", "八卦楼", "钢琴博物馆", "电影音乐馆", "中山路",
  "沙坡尾", "南普陀", "集美学村", "十里长堤", "关岳庙", "承天寺", "开元寺", "西街",
  "府文庙", "清净寺", "天后宫", "德济门",
];

const normalize = (value: string) =>
  value.replace(/[（）()·\s]/g, "").replace(/鼓浪屿|风景名胜区|景区|景点|旅游|攻略|推荐|图片/g, "");

const allPois = (plan: TravelPlanResult) => [
  ...(plan.map_data?.attractions ?? []),
  ...(plan.map_data?.food ?? []),
  ...(plan.map_data?.hotels ?? []),
];

const matchesPoi = (activity: Activity, poi: POI) => {
  const text = normalize(`${activity.name}${activity.location}${activity.description}`);
  const poiName = normalize(poi.name || "");
  if (!poiName) return false;
  return text.includes(poiName) || poiName.includes(normalize(activity.name));
};

const isTransportFallbackUrl = (url?: string) => /1474487548417|train|rail|station/i.test(url || "");
const isGenericImageUrl = (url?: string) => /images\.unsplash\.com|source\.unsplash\.com|picsum\.photos/i.test(url || "");

const imageCandidates = (plan: TravelPlanResult, activity: Activity) => {
  const text = `${activity.name}${activity.location}${activity.description}`;
  const candidates = [
    normalize(activity.name),
    normalize(activity.location),
    ...sourceKeywords.filter((keyword) => text.includes(keyword)).map(normalize),
    ...allPois(plan).filter((poi) => matchesPoi(activity, poi)).map((poi) => normalize(poi.name || "")),
  ];
  return Array.from(new Set(candidates.filter((item) => item.length >= 2)));
};

const matchingWebImage = (plan: TravelPlanResult, activity: Activity) => {
  const candidates = imageCandidates(plan, activity);
  return plan.map_data?.guide_context?.sources?.find((source) => {
    if (!source.image || isGenericImageUrl(source.image)) return false;
    const sourceText = normalize(`${source.title}${source.snippet}`);
    return candidates.some((keyword) => sourceText.includes(keyword));
  })?.image;
};

export const activityImage = (plan: TravelPlanResult, activity?: Activity, _index = 0) => {
  void _index;
  if (activity) {
    const poiPhoto = allPois(plan).find((poi) => poi.photo && !isGenericImageUrl(poi.photo) && matchesPoi(activity, poi))?.photo;
    if (poiPhoto) return poiPhoto;
    const webImage = matchingWebImage(plan, activity);
    if (webImage) return webImage;
    if (activity.photo && !isTransportFallbackUrl(activity.photo) && !isGenericImageUrl(activity.photo)) return activity.photo;
  }
  return "";
};

export const hotelImage = (plan: TravelPlanResult, hotel?: POI) => {
  if (hotel?.photo && !isGenericImageUrl(hotel.photo)) return hotel.photo;

  const text = `${hotel?.name ?? ""}${hotel?.address ?? ""}${plan.destination ?? ""}住宿酒店民宿`;
  const hotelName = hotel?.name ?? "";
  const webImage = plan.map_data?.guide_context?.sources?.find((source) => {
    if (!source.image || isGenericImageUrl(source.image)) return false;
    const sourceText = `${source.title}${source.snippet}`;
    return (hotelName ? sourceText.includes(hotelName) : false)
      || ["酒店", "民宿", "住宿", "客栈"].some((keyword) => text.includes(keyword) && sourceText.includes(keyword));
  })?.image;
  if (webImage) return webImage;

  return "";
};
