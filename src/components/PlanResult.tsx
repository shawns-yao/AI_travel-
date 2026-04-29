import { TravelPlanResult } from "@/types";
import { ResultPage } from "@/pages/ResultPage";

interface PlanResultProps {
  plan: TravelPlanResult;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
}

export default function PlanResult({ plan }: PlanResultProps) {
  return <ResultPage plan={plan} />;
}
