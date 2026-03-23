import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@/services/auth';
import { authProxyFetch, POE_OAUTH_MESSAGE } from '@/services/authProxy';

type CallbackState = 'loading' | 'success' | 'error';

const AuthCallback = () => {
  const [state, setState] = useState<CallbackState>('loading');
  const [message, setMessage] = useState('Completing PoE login…');
  const navigate = useNavigate();
  const { refreshSession } = useAuth();

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const code = params.get('code');
    const stateParam = params.get('state');
    const error = params.get('error');
    const errorDescription = params.get('error_description');

    window.history.replaceState({}, '', window.location.pathname);

    const notifyOpener = (status: 'success' | 'error', detailMessage?: string) => {
      if (window.opener && !window.opener.closed) {
        window.opener.postMessage({ type: POE_OAUTH_MESSAGE, status, message: detailMessage }, window.location.origin);
      }
    };

    if (error) {
      setState('error');
      setMessage(errorDescription || error);
      notifyOpener('error', errorDescription || error);
      return;
    }

    if (!code || !stateParam) {
      setState('error');
      setMessage('Missing OAuth parameters');
      notifyOpener('error', 'Missing OAuth parameters');
      return;
    }

    const relay = async () => {
      try {
        const response = await authProxyFetch(`/callback?code=${encodeURIComponent(code)}&state=${encodeURIComponent(stateParam)}`);
        if (!response.ok) {
          const body = await response.json().catch(() => ({}));
          throw new Error(body.message || body.error || `Callback failed (${response.status})`);
        }

        await refreshSession();
        setState('success');
        setMessage('Path of Exile connected. Closing window…');
        notifyOpener('success');

        window.setTimeout(() => {
          window.close();
          navigate('/', { replace: true });
        }, 400);
      } catch (err) {
        const detail = err instanceof Error ? err.message : 'Login failed';
        setState('error');
        setMessage(detail);
        notifyOpener('error', detail);
      }
    };

    void relay();
  }, [navigate, refreshSession]);

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4">
      <div className="max-w-sm text-center space-y-3">
        {state === 'loading' && (
          <div className="flex items-center justify-center gap-2">
            <div className="h-4 w-4 border-2 border-primary border-t-transparent rounded-full animate-spin" />
            <p className="text-muted-foreground text-sm font-mono">{message}</p>
          </div>
        )}
        {state === 'success' && <p className="text-primary text-sm font-mono">{message}</p>}
        {state === 'error' && (
          <>
            <p className="text-destructive text-sm font-mono">{message}</p>
            <button
              onClick={() => navigate('/', { replace: true })}
              className="text-xs text-muted-foreground hover:text-foreground underline transition-colors"
            >
              Return to app
            </button>
          </>
        )}
      </div>
    </div>
  );
};

export default AuthCallback;

