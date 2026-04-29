import { TravelPlanResult } from "../types";
import { Dialog, DialogContent, DialogTitle } from "./ui/dialog";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import { ScrollArea } from "./ui/scroll-area";
import { Badge } from "./ui/badge";

interface PlanResultProps {
  plan: TravelPlanResult;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export default function PlanResult({ plan, open, onOpenChange }: PlanResultProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-6xl h-[85vh] p-0 overflow-hidden">
        <div className="relative bg-gradient-to-br from-purple-600 via-blue-600 to-teal-500 p-4 text-white">
          <DialogTitle className="text-xl font-bold mb-1 flex items-center gap-2">
            {plan.destination} Travel Plan
          </DialogTitle>
          <div className="mt-2 flex flex-wrap gap-1.5">
            <Badge variant="outline" className="bg-white/20 text-white border-0">
              {plan.destination}
            </Badge>
            <Badge variant="outline" className="bg-white/20 text-white border-0">
              {plan.duration} days
            </Badge>
            <Badge variant="outline" className="bg-white/20 text-white border-0">
              {plan.start_date}
            </Badge>
            <Badge variant="outline" className="bg-white/20 text-white border-0">
              {plan.budget} yuan
            </Badge>
            {plan.preferences?.map((p) => (
              <Badge key={p} variant="outline" className="bg-white/20 text-white border-0">
                {p}
              </Badge>
            ))}
          </div>
        </div>

        <ScrollArea className="flex-1 bg-gradient-to-b from-gray-50 to-white">
          <div className="p-3 space-y-3">
            {/* Weather */}
            {plan.weather && (
              <Card className="bg-gradient-to-br from-sky-50 to-blue-100 border-0 shadow-lg">
                <CardHeader className="pb-2">
                  <CardTitle className="text-base">Weather Forecast</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    {plan.weather.forecast.map((w, i) => (
                      <div key={i} className="bg-white/70 rounded-lg p-3 flex items-center justify-between">
                        <span className="font-medium">{w.date}</span>
                        <span>{w.condition}</span>
                        <span>{w.temp_low}C - {w.temp_high}C</span>
                        <span className="text-xs text-gray-500">{w.recommendation}</span>
                      </div>
                    ))}
                  </div>
                  {plan.weather.risk_analysis && (
                    <div className="mt-2 bg-amber-50 rounded-lg p-2 text-sm text-amber-800">
                      Risk: {plan.weather.risk_analysis}
                    </div>
                  )}
                </CardContent>
              </Card>
            )}

            {/* Daily Plans */}
            <Card className="bg-gradient-to-br from-white to-purple-50 border-0 shadow-lg">
              <CardHeader className="pb-2">
                <CardTitle className="text-base">Daily Itinerary</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {plan.daily_plans?.map((day, di) => (
                  <div key={di} className="bg-gradient-to-r from-gray-50 to-blue-50 rounded-xl p-3 border">
                    <div className="flex items-center gap-2 mb-2">
                      <div className="w-7 h-7 bg-purple-500 rounded-lg flex items-center justify-center text-white font-bold text-sm">
                        {day.day}
                      </div>
                      <h4 className="font-bold">Day {day.day}</h4>
                      <span className="text-xs text-gray-500">{day.date}</span>
                    </div>
                    <div className="space-y-2">
                      {day.activities?.map((a, ai) => (
                        <div key={ai} className="bg-white rounded-lg p-2">
                          <div className="flex items-center gap-2">
                            <Badge variant="outline" className="text-xs">{a.time}</Badge>
                            <span className="text-sm font-medium">{a.name}</span>
                            {a.source && (
                              <Badge variant="outline" className="text-xs text-green-600">RAG</Badge>
                            )}
                          </div>
                          <p className="text-xs text-gray-500 mt-1">{a.description}</p>
                          <div className="flex gap-2 mt-1 text-xs text-gray-400">
                            <span>{a.location}</span>
                            <span>{a.duration}</span>
                            {a.cost > 0 && <span>{a.cost} yuan</span>}
                          </div>
                        </div>
                      ))}
                    </div>
                    {day.notes && (
                      <div className="mt-2 bg-amber-50 rounded-lg p-2 text-xs text-amber-800">
                        {day.notes}
                      </div>
                    )}
                  </div>
                ))}
              </CardContent>
            </Card>

            {/* Budget */}
            {plan.budget_breakdown && (
              <Card className="bg-gradient-to-br from-green-50 to-emerald-100 border-0 shadow-lg">
                <CardHeader className="pb-2">
                  <CardTitle className="text-base">Budget Breakdown</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-1 text-sm">
                    <div className="flex justify-between font-bold">
                      <span>Total Budget</span>
                      <span>{plan.budget_breakdown.total_budget} yuan</span>
                    </div>
                    {Object.entries(plan.budget_breakdown.allocated).map(([k, v]) => (
                      <div key={k} className="flex justify-between">
                        <span className="text-gray-600 capitalize">{k}</span>
                        <span>{v} yuan</span>
                      </div>
                    ))}
                  </div>
                  {plan.budget_breakdown.warnings?.map((w, i) => (
                    <div key={i} className="mt-1 text-xs text-red-600">{w}</div>
                  ))}
                </CardContent>
              </Card>
            )}

            {/* Critic Report */}
            {plan.critic_report && (
              <Card className={`border-0 shadow-lg ${plan.critic_report.needs_replan ? "bg-red-50" : "bg-green-50"}`}>
                <CardHeader className="pb-2">
                  <CardTitle className="text-base">
                    Quality Review (Score: {plan.critic_report.score}/100)
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  {plan.critic_report.issues?.map((issue, i) => (
                    <div key={i} className="flex items-start gap-2 mb-1 text-sm">
                      <Badge variant="outline" className={
                        issue.severity === "high" ? "text-red-600" :
                        issue.severity === "medium" ? "text-yellow-600" : "text-blue-600"
                      }>
                        {issue.severity}
                      </Badge>
                      <span>{issue.description}</span>
                    </div>
                  ))}
                  {plan.critic_report.suggestions?.map((s, i) => (
                    <p key={i} className="text-xs text-gray-600 mt-1">{s}</p>
                  ))}
                </CardContent>
              </Card>
            )}

            {/* Memory Context */}
            {plan.memory_context && (
              <Card className="bg-gradient-to-br from-pink-50 to-rose-100 border-0 shadow-lg">
                <CardHeader className="pb-2">
                  <CardTitle className="text-base">Memory Used</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-xs space-y-1">
                    {plan.memory_context.long_term?.map((m, i) => (
                      <div key={i} className="flex items-center gap-2">
                        <Badge variant="outline" className="text-pink-600">Long-term</Badge>
                        <span>{m.content}</span>
                        <span className="text-gray-400">({(m.confidence * 100).toFixed(0)}%)</span>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}
          </div>
        </ScrollArea>
      </DialogContent>
    </Dialog>
  );
}
