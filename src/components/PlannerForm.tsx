import { useState } from "react";
import { CardHeader, CardTitle } from "./ui/card";
import { Button } from "./ui/button";
import { Input } from "./ui/input";

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
      <CardHeader className="text-center p-2 pb-6">
        <CardTitle className="text-2xl font-bold text-gray-900">
          AI Travel Agent Platform
        </CardTitle>
        <p className="text-sm text-gray-500 mt-1">
          Multi-Agent Intelligent Travel Decision System
        </p>
      </CardHeader>

      <form onSubmit={handleSubmit} className="space-y-2">
        <div className="flex gap-4 items-end">
          <div className="flex-1">
            <Input
              placeholder="Describe your travel plan..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              className="min-h-10 text-sm"
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
                <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white mr-2" />
                Agents Working...
              </>
            ) : (
              "Start Planning"
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
            View Report
          </Button>
        </div>
      </form>
    </div>
  );
}
