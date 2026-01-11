import { WifiOff, RefreshCw } from 'lucide-react';
import { cn } from '@/lib/utils/cn';
import { useUIStore } from '@/stores/uiStore';
import { Button } from '@/components/common/Button';

export function ConnectionBanner() {
  const connectionStatus = useUIStore((s) => s.connectionStatus);

  if (connectionStatus === 'connected') {
    return null;
  }

  const isReconnecting = connectionStatus === 'reconnecting';

  return (
    <div
      className={cn(
        'fixed top-16 left-0 right-0 z-30 py-2 px-4',
        'flex items-center justify-center gap-3 text-sm font-medium',
        isReconnecting ? 'bg-warning/90 text-black' : 'bg-danger/90 text-white'
      )}
      role="alert"
    >
      {isReconnecting ? (
        <>
          <RefreshCw className="w-4 h-4 animate-spin" />
          <span>재연결 중...</span>
        </>
      ) : (
        <>
          <WifiOff className="w-4 h-4" />
          <span>연결이 끊겼습니다</span>
          <Button
            variant="ghost"
            size="sm"
            className="ml-2 bg-white/20 hover:bg-white/30 text-white"
            onClick={() => window.location.reload()}
          >
            재시도
          </Button>
        </>
      )}
    </div>
  );
}
