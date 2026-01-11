import { memo, useEffect, useState } from 'react';
import { cn } from '@/lib/utils/cn';

interface TimerProps {
  deadline: Date | null;
  warningThreshold?: number;
  criticalThreshold?: number;
  onTimeout?: () => void;
}

export const Timer = memo(function Timer({
  deadline,
  warningThreshold = 10,
  criticalThreshold = 5,
  onTimeout,
}: TimerProps) {
  const [timeLeft, setTimeLeft] = useState<number | null>(null);

  useEffect(() => {
    if (!deadline) {
      setTimeLeft(null);
      return;
    }

    const calculateTimeLeft = () => {
      const now = new Date();
      const diff = Math.max(0, Math.floor((deadline.getTime() - now.getTime()) / 1000));
      return diff;
    };

    setTimeLeft(calculateTimeLeft());

    const interval = setInterval(() => {
      const remaining = calculateTimeLeft();
      setTimeLeft(remaining);

      if (remaining === 0) {
        clearInterval(interval);
        onTimeout?.();
      }
    }, 1000);

    return () => clearInterval(interval);
  }, [deadline, onTimeout]);

  if (timeLeft === null) return null;

  const isWarning = timeLeft <= warningThreshold && timeLeft > criticalThreshold;
  const isCritical = timeLeft <= criticalThreshold;

  const minutes = Math.floor(timeLeft / 60);
  const seconds = timeLeft % 60;
  const displayTime = `${minutes}:${seconds.toString().padStart(2, '0')}`;

  // Calculate progress for circular timer
  const totalTime = 30; // Assume 30 second turns
  const progress = Math.min(100, (timeLeft / totalTime) * 100);

  return (
    <div
      className={cn(
        'relative w-14 h-14 flex items-center justify-center',
        isCritical && 'animate-pulse'
      )}
    >
      {/* Background circle */}
      <svg className="absolute inset-0 w-full h-full -rotate-90">
        <circle
          cx="28"
          cy="28"
          r="24"
          fill="none"
          stroke="currentColor"
          strokeWidth="4"
          className="text-surface"
        />
        <circle
          cx="28"
          cy="28"
          r="24"
          fill="none"
          stroke="currentColor"
          strokeWidth="4"
          strokeLinecap="round"
          strokeDasharray={`${(progress * 150.8) / 100} 150.8`}
          className={cn(
            'transition-all duration-200',
            isCritical ? 'text-danger' : isWarning ? 'text-warning' : 'text-success'
          )}
        />
      </svg>

      {/* Time display */}
      <span
        className={cn(
          'text-sm font-bold',
          isCritical ? 'text-danger' : isWarning ? 'text-warning' : 'text-text'
        )}
      >
        {displayTime}
      </span>
    </div>
  );
});
