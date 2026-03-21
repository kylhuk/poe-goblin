import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Route, Routes, Navigate } from "react-router-dom";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";
import { AuthProvider, useAuth } from "@/services/auth";
import Index from "./pages/Index.tsx";
import AuthCallback from "./pages/AuthCallback.tsx";
import NotFound from "./pages/NotFound.tsx";
import Login from "./pages/Login.tsx";

const queryClient = new QueryClient();

const DEFAULT_TAB: Record<string, string> = {
  public: "pricecheck",
  member: "opportunities",
  admin: "dashboard",
};

const PendingApproval = () => {
  const { signOut, supabaseUser } = useAuth();
  return (
    <div className="min-h-screen flex items-center justify-center bg-background p-4">
      <div className="text-center space-y-4 max-w-sm">
        <h1 className="text-lg font-semibold text-foreground">Pending Approval</h1>
        <p className="text-sm text-muted-foreground">
          Your account <strong className="text-foreground">{supabaseUser?.email}</strong> has been created but is not yet approved. Contact an administrator to get access.
        </p>
        <button onClick={signOut} className="text-xs text-muted-foreground hover:text-foreground underline transition-colors">
          Sign Out
        </button>
      </div>
    </div>
  );
};

const AppGate = () => {
  const { isAuthenticated, isApproved, isLoading, userRole } = useAuth();

  if (isLoading) {
    return <div className="min-h-screen flex items-center justify-center bg-background text-muted-foreground text-sm">Loading…</div>;
  }

  const defaultTab = DEFAULT_TAB[userRole] || "pricecheck";

  // Public users: show Index with limited tabs (ML Price only)
  if (!isAuthenticated) {
    return (
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/auth/callback" element={<AuthCallback />} />
          <Route path="/:tab/:subtab?" element={<Index />} />
          <Route path="/" element={<Navigate to={`/${defaultTab}`} replace />} />
          <Route path="*" element={<Navigate to={`/${defaultTab}`} replace />} />
        </Routes>
      </BrowserRouter>
    );
  }

  if (!isApproved) {
    return <PendingApproval />;
  }

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/auth/callback" element={<AuthCallback />} />
        <Route path="/:tab/:subtab?" element={<Index />} />
        <Route path="/" element={<Navigate to={`/${defaultTab}`} replace />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </BrowserRouter>
  );
};

const App = () => (
  <QueryClientProvider client={queryClient}>
    <AuthProvider>
      <TooltipProvider>
        <Toaster />
        <Sonner />
        <AppGate />
      </TooltipProvider>
    </AuthProvider>
  </QueryClientProvider>
);

export default App;
