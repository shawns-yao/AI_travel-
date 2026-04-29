import {
  CalendarDays,
  Home,
  Lightbulb,
  MapPin,
  Settings,
  Sparkles,
  Star,
  UserCircle,
} from "lucide-react";
import { Brand } from "@/components/travel/Brand";
import { cn } from "@/lib/utils";

export type AppView = "home" | "generating" | "result" | "plans" | "preferences" | "compare" | "explore" | "edit";

interface AppShellProps {
  activeView: AppView;
  children: React.ReactNode;
  onNavigate: (view: AppView) => void;
}

const navItems: Array<{ key: AppView; label: string; icon: React.ComponentType<{ className?: string }> }> = [
  { key: "home", label: "首页", icon: Home },
  { key: "compare", label: "旅行规划", icon: Lightbulb },
  { key: "plans", label: "我的行程", icon: CalendarDays },
  { key: "explore", label: "探索目的地", icon: MapPin },
];

const mobileNavItems: Array<{ key: AppView; label: string; icon: React.ComponentType<{ className?: string }> }> = [
  ...navItems,
  { key: "preferences", label: "服务配置", icon: Settings },
];

export function AppShell({ activeView, children, onNavigate }: AppShellProps) {
  return (
    <div className="min-h-screen bg-[#f7fbfc] text-slate-950">
      <header className="fixed left-0 right-0 top-0 z-30 flex h-[68px] items-center justify-between border-b border-slate-200/80 bg-white/90 px-8 backdrop-blur">
        <Brand />
        <div className="flex items-center gap-8">
          <nav className="hidden items-center justify-end gap-12 text-sm font-medium text-slate-800 lg:flex">
            <button type="button" onClick={() => onNavigate("plans")} className="hover:text-[#0eaeb3]">
              我的行程
            </button>
            <button type="button" onClick={() => onNavigate("explore")} className="hover:text-[#0eaeb3]">
              探索目的地
            </button>
            <button type="button" onClick={() => onNavigate("compare")} className="hover:text-[#0eaeb3]">
              旅行规划
            </button>
          </nav>
          <button type="button" onClick={() => onNavigate("preferences")} className="flex items-center gap-3 rounded-full px-2 py-1">
            <img
              src="https://images.unsplash.com/photo-1494790108377-be9c29b29330?auto=format&fit=crop&w=80&q=80"
              alt="用户头像"
              className="h-10 w-10 rounded-full object-cover"
            />
          </button>
        </div>
      </header>

      <aside className="fixed bottom-0 left-0 top-[68px] z-20 hidden w-[250px] border-r border-slate-200/80 bg-white/78 backdrop-blur-xl lg:block">
        <div className="flex h-full flex-col justify-between px-4 py-8">
          <div className="space-y-2">
            {navItems.map((item, index) => {
              const Icon = item.icon;
              const active = item.key === activeView || (item.key === "compare" && activeView === "result");
              return (
                <button
                  key={`${item.label}-${index}`}
                  type="button"
                  onClick={() => onNavigate(item.key)}
                  className={cn(
                    "flex h-12 w-full items-center gap-3 rounded-xl px-4 text-left text-sm font-medium text-slate-600 transition",
                    active && "bg-[#e7f9fa] text-[#0da8ad]",
                  )}
                >
                  <Icon className="h-5 w-5" />
                  {item.label}
                </button>
              );
            })}
          </div>

          <div className="space-y-5">
            <div className="rounded-2xl border border-cyan-100 bg-cyan-50/80 p-4">
              <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-2xl bg-white text-[#11aeb4]">
                <Sparkles className="h-6 w-6" />
              </div>
              <div className="text-sm font-bold">你的 AI 旅行助手</div>
            <button type="button" onClick={() => onNavigate("home")} className="mt-4 h-10 w-full rounded-full bg-[#10b8bd] text-sm font-semibold text-white shadow-md shadow-cyan-200">
              去聊聊
            </button>
            </div>
            <button type="button" onClick={() => onNavigate("preferences")} className="flex items-center gap-3 px-4 text-sm text-slate-600">
              <Settings className="h-5 w-5" />
              服务配置
            </button>
            <div className="flex items-center gap-3 px-4 text-sm text-slate-600">
              <UserCircle className="h-5 w-5" />
              小旅人
              <Star className="ml-auto h-4 w-4 text-[#12b9bd]" />
            </div>
          </div>
        </div>
      </aside>

      <main className="min-h-screen pb-20 pt-[68px] lg:pb-0 lg:pl-[250px]">{children}</main>

      <nav className="fixed bottom-0 left-0 right-0 z-30 grid grid-cols-5 border-t border-slate-200 bg-white/95 px-2 py-2 backdrop-blur lg:hidden">
        {mobileNavItems.map((item, index) => {
          const Icon = item.icon;
          const active = item.key === activeView || (item.key === "compare" && activeView === "result");
          return (
            <button
              key={`${item.label}-mobile-${index}`}
              type="button"
              onClick={() => onNavigate(item.key)}
              className={cn(
                "flex min-h-[52px] flex-col items-center justify-center gap-1 rounded-xl text-xs font-semibold text-slate-500",
                active && "bg-[#e7f9fa] text-[#0da8ad]",
              )}
            >
              <Icon className="h-5 w-5" />
              {item.label}
            </button>
          );
        })}
      </nav>
    </div>
  );
}
