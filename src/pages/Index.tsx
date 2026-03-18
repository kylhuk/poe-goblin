import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import DashboardTab from "@/components/tabs/DashboardTab";
import ServicesTab from "@/components/tabs/ServicesTab";
import AnalyticsTab from "@/components/tabs/AnalyticsTab";
import PriceCheckTab from "@/components/tabs/PriceCheckTab";
import StashViewerTab from "@/components/tabs/StashViewerTab";
import MessagesTab from "@/components/tabs/MessagesTab";
import OpportunitiesTab from "@/components/tabs/OpportunitiesTab";
import { LayoutDashboard, Server, BarChart3, Search, Grid3X3, MessageSquare, TrendingUp } from "lucide-react";
import UserMenu from "@/components/UserMenu";
import ApiErrorPanel from "@/components/ApiErrorPanel";
import { useAuth, type UserRole } from "@/services/auth";

type TabDef = {
  id: string;
  label: string;
  icon: React.ReactNode;
  content: React.ReactNode;
  roles: UserRole[];
};

const TABS: TabDef[] = [
  {
    id: "dashboard",
    label: "Dashboard",
    icon: <LayoutDashboard className="h-3.5 w-3.5" />,
    content: <DashboardTab />,
    roles: ["admin"],
  },
  {
    id: "opportunities",
    label: "Opportunities",
    icon: <TrendingUp className="h-3.5 w-3.5" />,
    content: <OpportunitiesTab />,
    roles: ["member", "admin"],
  },
  {
    id: "services",
    label: "Services",
    icon: <Server className="h-3.5 w-3.5" />,
    content: <ServicesTab />,
    roles: ["admin"],
  },
  {
    id: "analytics",
    label: "Analytics",
    icon: <BarChart3 className="h-3.5 w-3.5" />,
    content: <AnalyticsTab />,
    roles: ["member", "admin"],
  },
  {
    id: "pricecheck",
    label: "ML Price",
    icon: <Search className="h-3.5 w-3.5" />,
    content: <PriceCheckTab />,
    roles: ["public", "member", "admin"],
  },
  {
    id: "stash",
    label: "Stash Viewer",
    icon: <Grid3X3 className="h-3.5 w-3.5" />,
    content: <StashViewerTab />,
    roles: ["member", "admin"],
  },
  {
    id: "messages",
    label: "Messages",
    icon: <MessageSquare className="h-3.5 w-3.5" />,
    content: <MessagesTab />,
    roles: ["admin"],
  },
];

const DEFAULT_TAB: Record<UserRole, string> = {
  public: "pricecheck",
  member: "opportunities",
  admin: "dashboard",
};

const Index = () => {
  const { userRole } = useAuth();
  const visibleTabs = TABS.filter((t) => t.roles.includes(userRole));
  const defaultTab = DEFAULT_TAB[userRole] || "pricecheck";

  return (
    <div className="min-h-screen bg-background vignette">
      {/* Header */}
      <header className="border-b border-border bg-card/50 backdrop-blur sticky top-0 z-50 header-glow">
        <div className="container flex items-center justify-between h-12 px-4">
          <div className="flex items-center gap-2">
            <img src="/logo.png" alt="PoE Dashboard" className="h-7 w-7" />
            <h1 className="text-lg font-display tracking-wide gold-shimmer-text">PoE Dashboard</h1>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-xs text-muted-foreground font-mono hidden sm:inline"></span>
            <ApiErrorPanel />
            <UserMenu />
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className="container px-4 py-4">
        <Tabs defaultValue={defaultTab} className="space-y-4" data-testid="panel-shell-root">
          <TabsList className="w-full justify-start h-auto flex-wrap gap-1 bg-card border border-border p-1">
            {visibleTabs.map((tab) => (
              <TabsTrigger
                key={tab.id}
                data-testid={`tab-${tab.id}`}
                value={tab.id}
                className="tab-game gap-1.5 text-xs data-[state=active]:bg-primary data-[state=active]:text-primary-foreground"
              >
                {tab.icon} {tab.label}
              </TabsTrigger>
            ))}
          </TabsList>

          {visibleTabs.map((tab) => (
            <TabsContent key={tab.id} data-testid={`panel-${tab.id}`} value={tab.id}>
              {tab.content}
            </TabsContent>
          ))}
        </Tabs>
      </main>
    </div>
  );
};

export default Index;
