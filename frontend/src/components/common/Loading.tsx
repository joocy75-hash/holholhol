import { Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils/cn';

interface LoadingProps {
  type?: 'spinner' | 'skeleton' | 'dots';
  size?: 'sm' | 'md' | 'lg';
  text?: string;
  className?: string;
}

const sizeMap = {
  sm: 'w-4 h-4',
  md: 'w-8 h-8',
  lg: 'w-12 h-12',
};

export function Loading({ type = 'spinner', size = 'md', text, className }: LoadingProps) {
  if (type === 'spinner') {
    return (
      <div className={cn('flex flex-col items-center justify-center gap-3', className)}>
        <Loader2 className={cn('animate-spin text-primary', sizeMap[size])} />
        {text && <p className="text-sm text-text-muted">{text}</p>}
      </div>
    );
  }

  if (type === 'dots') {
    return (
      <div className={cn('flex items-center justify-center gap-1', className)}>
        {[0, 1, 2].map((i) => (
          <div
            key={i}
            className="w-2 h-2 bg-primary rounded-full animate-bounce"
            style={{ animationDelay: `${i * 0.1}s` }}
          />
        ))}
        {text && <span className="ml-3 text-sm text-text-muted">{text}</span>}
      </div>
    );
  }

  // Skeleton
  return (
    <div className={cn('space-y-3', className)}>
      <div className="h-4 bg-surface animate-pulse rounded" />
      <div className="h-4 bg-surface animate-pulse rounded w-3/4" />
      <div className="h-4 bg-surface animate-pulse rounded w-1/2" />
    </div>
  );
}

// Skeleton card for room list
export function SkeletonCard() {
  return (
    <div className="card p-4 animate-pulse">
      <div className="flex justify-between items-start mb-4">
        <div className="h-5 bg-bg rounded w-1/3" />
        <div className="h-5 bg-bg rounded w-16" />
      </div>
      <div className="h-4 bg-bg rounded w-2/3 mb-2" />
      <div className="h-4 bg-bg rounded w-1/2" />
      <div className="flex justify-between mt-4">
        <div className="h-9 bg-bg rounded w-20" />
        <div className="h-9 bg-bg rounded w-24" />
      </div>
    </div>
  );
}
