import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";
import { AuthProvider } from "@/services/auth";
import Index from "./pages/Index.tsx";
import AuthCallback from "./pages/AuthCallback.tsx";
import NotFound from "./pages/NotFound.tsx";

console.log('[DEBUG-APP] Sonner:', typeof Sonner);
console.log('[DEBUG-APP] Toaster:', typeof Toaster);
console.log('[DEBUG-APP] AuthProvider:', typeof AuthProvider);
console.log('[DEBUG-APP] Index:', typeof Index);
console.log('[DEBUG-APP] AuthCallback:', typeof AuthCallback);

const queryClient = new QueryClient();

const App = () => (
  <QueryClientProvider client={queryClient}>
    <AuthProvider>
      <TooltipProvider>
        <Toaster />
        <Sonner />
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<Index />} />
            <Route path="/auth/callback" element={<AuthCallback />} />
            {/* ADD ALL CUSTOM ROUTES ABOVE THE CATCH-ALL "*" ROUTE */}
            <Route path="*" element={<NotFound />} />
          </Routes>
        </BrowserRouter>
      </TooltipProvider>
    </AuthProvider>
  </QueryClientProvider>
);

export default App;
