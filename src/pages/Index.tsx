import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import DashboardTab from '@/components/tabs/DashboardTab';
import ServicesTab from '@/components/tabs/ServicesTab';
import AnalyticsTab from '@/components/tabs/AnalyticsTab';
import PriceCheckTab from '@/components/tabs/PriceCheckTab';
import StashViewerTab from '@/components/tabs/StashViewerTab';
import MessagesTab from '@/components/tabs/MessagesTab';
import { LayoutDashboard, Server, BarChart3, Search, Grid3X3, MessageSquare } from 'lucide-react';
import UserMenu from '@/components/UserMenu';
import ApiErrorPanel from '@/components/ApiErrorPanel';

console.log('[DEBUG] DashboardTab:', typeof DashboardTab, DashboardTab);
console.log('[DEBUG] ServicesTab:', typeof ServicesTab, ServicesTab);
console.log('[DEBUG] AnalyticsTab:', typeof AnalyticsTab, AnalyticsTab);
console.log('[DEBUG] PriceCheckTab:', typeof PriceCheckTab, PriceCheckTab);
console.log('[DEBUG] StashViewerTab:', typeof StashViewerTab, StashViewerTab);
console.log('[DEBUG] MessagesTab:', typeof MessagesTab, MessagesTab);
console.log('[DEBUG] UserMenu:', typeof UserMenu, UserMenu);
console.log('[DEBUG] ApiErrorPanel:', typeof ApiErrorPanel, ApiErrorPanel);

const Index = () => {
  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b border-border bg-card/50 backdrop-blur sticky top-0 z-50">
        <div className="container flex items-center justify-between h-12 px-4">
          <h1 className="text-lg font-display text-primary tracking-wide">PoE Dashboard</h1>
          <div className="flex items-center gap-3">
            <span className="text-xs text-muted-foreground font-mono hidden sm:inline">All data delayed · Not real-time</span>
            <ApiErrorPanel />
            <UserMenu />
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className="container px-4 py-4">
        <Tabs defaultValue="dashboard" className="space-y-4" data-testid="panel-shell-root">
          <TabsList className="w-full justify-start h-auto flex-wrap gap-1 bg-card border border-border p-1">
            <TabsTrigger data-testid="tab-dashboard" value="dashboard" className="gap-1.5 text-xs data-[state=active]:bg-primary data-[state=active]:text-primary-foreground">
              <LayoutDashboard className="h-3.5 w-3.5" /> Dashboard
            </TabsTrigger>
            <TabsTrigger data-testid="tab-services" value="services" className="gap-1.5 text-xs data-[state=active]:bg-primary data-[state=active]:text-primary-foreground">
              <Server className="h-3.5 w-3.5" /> Services
            </TabsTrigger>
            <TabsTrigger data-testid="tab-analytics" value="analytics" className="gap-1.5 text-xs data-[state=active]:bg-primary data-[state=active]:text-primary-foreground">
              <BarChart3 className="h-3.5 w-3.5" /> Analytics
            </TabsTrigger>
            <TabsTrigger data-testid="tab-pricecheck" value="pricecheck" className="gap-1.5 text-xs data-[state=active]:bg-primary data-[state=active]:text-primary-foreground">
              <Search className="h-3.5 w-3.5" /> Price Check
            </TabsTrigger>
            <TabsTrigger data-testid="tab-stash" value="stash" className="gap-1.5 text-xs data-[state=active]:bg-primary data-[state=active]:text-primary-foreground">
              <Grid3X3 className="h-3.5 w-3.5" /> Stash Viewer
            </TabsTrigger>
            <TabsTrigger data-testid="tab-messages" value="messages" className="gap-1.5 text-xs data-[state=active]:bg-primary data-[state=active]:text-primary-foreground">
              <MessageSquare className="h-3.5 w-3.5" /> Messages
            </TabsTrigger>
          </TabsList>

          <TabsContent data-testid="panel-dashboard" value="dashboard"><DashboardTab /></TabsContent>
          <TabsContent data-testid="panel-services" value="services"><ServicesTab /></TabsContent>
          <TabsContent data-testid="panel-analytics" value="analytics"><AnalyticsTab /></TabsContent>
          <TabsContent data-testid="panel-pricecheck" value="pricecheck"><PriceCheckTab /></TabsContent>
          <TabsContent data-testid="panel-stash" value="stash"><StashViewerTab /></TabsContent>
          <TabsContent data-testid="panel-messages" value="messages"><MessagesTab /></TabsContent>
        </Tabs>
      </main>
    </div>
  );
};

export default Index;
