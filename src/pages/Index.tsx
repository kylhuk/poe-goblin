import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import DashboardTab from '@/components/tabs/DashboardTab';
import ServicesTab from '@/components/tabs/ServicesTab';
import AnalyticsTab from '@/components/tabs/AnalyticsTab';
import PriceCheckTab from '@/components/tabs/PriceCheckTab';
import StashViewerTab from '@/components/tabs/StashViewerTab';
import MessagesTab from '@/components/tabs/MessagesTab';
import { LayoutDashboard, Server, BarChart3, Search, Grid3X3, MessageSquare } from 'lucide-react';
import UserMenu from '@/components/UserMenu';

const Index = () => {
  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b border-border bg-card/50 backdrop-blur sticky top-0 z-50">
        <div className="container flex items-center justify-between h-12 px-4">
          <h1 className="text-lg font-display text-primary tracking-wide">PoE Dashboard</h1>
          <div className="flex items-center gap-3">
            <span className="text-xs text-muted-foreground font-mono hidden sm:inline">All data delayed · Not real-time</span>
            <UserMenu />
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className="container px-4 py-4">
        <Tabs defaultValue="dashboard" className="space-y-4">
          <TabsList className="w-full justify-start h-auto flex-wrap gap-1 bg-card border border-border p-1">
            <TabsTrigger value="dashboard" className="gap-1.5 text-xs data-[state=active]:bg-primary data-[state=active]:text-primary-foreground">
              <LayoutDashboard className="h-3.5 w-3.5" /> Dashboard
            </TabsTrigger>
            <TabsTrigger value="services" className="gap-1.5 text-xs data-[state=active]:bg-primary data-[state=active]:text-primary-foreground">
              <Server className="h-3.5 w-3.5" /> Services
            </TabsTrigger>
            <TabsTrigger value="analytics" className="gap-1.5 text-xs data-[state=active]:bg-primary data-[state=active]:text-primary-foreground">
              <BarChart3 className="h-3.5 w-3.5" /> Analytics
            </TabsTrigger>
            <TabsTrigger value="pricecheck" className="gap-1.5 text-xs data-[state=active]:bg-primary data-[state=active]:text-primary-foreground">
              <Search className="h-3.5 w-3.5" /> Price Check
            </TabsTrigger>
            <TabsTrigger value="stash" className="gap-1.5 text-xs data-[state=active]:bg-primary data-[state=active]:text-primary-foreground">
              <Grid3X3 className="h-3.5 w-3.5" /> Stash Viewer
            </TabsTrigger>
            <TabsTrigger value="messages" className="gap-1.5 text-xs data-[state=active]:bg-primary data-[state=active]:text-primary-foreground">
              <MessageSquare className="h-3.5 w-3.5" /> Messages
            </TabsTrigger>
          </TabsList>

          <TabsContent value="dashboard"><DashboardTab /></TabsContent>
          <TabsContent value="services"><ServicesTab /></TabsContent>
          <TabsContent value="analytics"><AnalyticsTab /></TabsContent>
          <TabsContent value="pricecheck"><PriceCheckTab /></TabsContent>
          <TabsContent value="stash"><StashViewerTab /></TabsContent>
          <TabsContent value="messages"><MessagesTab /></TabsContent>
        </Tabs>
      </main>
    </div>
  );
};

export default Index;
