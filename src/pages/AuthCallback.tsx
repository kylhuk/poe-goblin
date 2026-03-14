import { useEffect } from 'react';

const AuthCallback = () => {
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const token = params.get('token');
    const accountName = params.get('account_name') || params.get('accountName') || 'Exile';

    if (token && window.opener) {
      window.opener.postMessage(
        { type: 'poe_auth_callback', token, accountName },
        window.location.origin
      );
      window.close();
    }
  }, []);

  return (
    <div className="min-h-screen bg-background flex items-center justify-center">
      <p className="text-muted-foreground text-sm font-mono">Completing login…</p>
    </div>
  );
};

export default AuthCallback;
