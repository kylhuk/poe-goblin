import { useEffect } from 'react';

const AuthCallback = () => {
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const status = params.get('status') || 'success';
    if (window.opener) {
      window.opener.postMessage({ type: 'poe_auth_callback_complete', status }, window.location.origin);
      window.close();
    }
  }, []);

  return (
    <div className="min-h-screen bg-background flex items-center justify-center">
      <p className="text-muted-foreground text-sm font-mono">Completing secure login session...</p>
    </div>
  );
};

export default AuthCallback;
