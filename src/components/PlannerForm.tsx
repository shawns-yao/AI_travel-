import { useState } from "react";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Eye, Loader2, Sparkles } from "lucide-react";

interface PlannerFormProps {
  onSubmit: (input: string) => void;
  isLoading: boolean;
  onShowReport: () => void;
  hasReport: boolean;
}

export default function PlannerForm({
  onSubmit,
  isLoading,
  onShowReport,
  hasReport,
}: PlannerFormProps) {
  const [input, setInput] = useState("我想去成都玩三天，预算3000元，喜欢自然风光和美食");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim()) return;
    onSubmit(input);
  };

  return (
    <div className="w-full">
      <form onSubmit={handleSubmit} className="space-y-2">
        <div className="flex flex-col gap-3 md:flex-row md:items-center">
          <div className="flex-1">
            <Input
              placeholder="输入目的地、天数、预算和偏好"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              className="h-11 text-sm"
              disabled={isLoading}
            />
          </div>
          <Button
            type="submit"
            disabled={isLoading || !input.trim()}
            className="h-10 px-8 text-sm font-medium"
            size="sm"
          >
            {isLoading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                规划中
              </>
            ) : (
              <>
                <Sparkles className="mr-2 h-4 w-4" />
                开始规划
              </>
            )}
          </Button>
          <Button
            type="button"
            variant="outline"
            onClick={onShowReport}
            className="h-10 px-8 text-sm font-medium"
            size="sm"
            disabled={!hasReport}
          >
            <Eye className="mr-2 h-4 w-4" />
            查看方案
          </Button>
        </div>
      </form>
    </div>
  );
}
