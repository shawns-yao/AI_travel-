import { Activity } from "@/types";

const transferNamePattern = /抵达|到达|离开|返程|返回|出发|前往|换乘|乘坐|高铁|动车|火车|航班|机场|车站|北站|南站|东站|西站|轮渡|码头|登岛|离岛/;
const transferSentencePattern = /抵达|到达|离开|返程|返回|出发|换乘|乘坐|高铁|动车|火车|航班|机场|车站|轮渡|码头|登岛|离岛/;

export const isTransferActivity = (activity: Activity) => {
  const name = `${activity.name || ""}${activity.location || ""}`.replace(/\s+/g, "");
  return activity.type === "transport" || transferNamePattern.test(name);
};

export const activityDescriptionForCard = (activity: Activity) => {
  const description = String(activity.description || "").trim();
  if (!description) return "";

  const sentences = description
    .split(/(?<=[。！？!?])/)
    .map((item) => item.trim())
    .filter(Boolean);

  const useful = sentences.filter((sentence, index) => {
    if (index > 0) return true;
    return !transferSentencePattern.test(sentence);
  });

  return useful.join("") || description;
};
