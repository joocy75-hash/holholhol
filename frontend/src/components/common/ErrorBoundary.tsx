'use client';

import { Component, ReactNode } from 'react';

interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode;
  onError?: (error: Error, errorInfo: React.ErrorInfo) => void;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
  errorInfo: React.ErrorInfo | null;
}

/**
 * 에러 바운더리 컴포넌트
 * 
 * 자식 컴포넌트에서 발생하는 JavaScript 에러를 잡아서
 * 전체 앱이 크래시되지 않도록 보호합니다.
 * 
 * 사용 예시:
 * ```tsx
 * <ErrorBoundary fallback={<div>문제가 발생했습니다</div>}>
 *   <MyComponent />
 * </ErrorBoundary>
 * ```
 */
export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
    };
  }

  static getDerivedStateFromError(error: Error): Partial<ErrorBoundaryState> {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error('[ErrorBoundary] 에러 발생:', error);
    console.error('[ErrorBoundary] 에러 정보:', errorInfo);
    
    this.setState({ errorInfo });
    
    // 외부 에러 핸들러 호출
    this.props.onError?.(error, errorInfo);
  }

  handleRetry = () => {
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null,
    });
  };

  handleGoHome = () => {
    window.location.href = '/lobby';
  };

  render() {
    if (this.state.hasError) {
      // 커스텀 fallback이 제공된 경우
      if (this.props.fallback) {
        return this.props.fallback;
      }

      // 기본 에러 UI
      return (
        <div className="min-h-screen flex items-center justify-center bg-background p-4">
          <div className="max-w-md w-full bg-surface rounded-xl p-6 shadow-lg border border-border">
            <div className="text-center">
              {/* 에러 아이콘 */}
              <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-error/10 flex items-center justify-center">
                <svg
                  className="w-8 h-8 text-error"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                  />
                </svg>
              </div>

              <h2 className="text-xl font-bold text-text-primary mb-2">
                문제가 발생했습니다
              </h2>
              
              <p className="text-text-secondary mb-6">
                예기치 않은 오류가 발생했습니다. 잠시 후 다시 시도해주세요.
              </p>

              {/* 에러 상세 (개발 모드에서만) */}
              {process.env.NODE_ENV === 'development' && this.state.error && (
                <div className="mb-6 p-3 bg-error/10 rounded-lg text-left">
                  <p className="text-sm font-mono text-error break-all">
                    {this.state.error.message}
                  </p>
                  {this.state.errorInfo?.componentStack && (
                    <details className="mt-2">
                      <summary className="text-xs text-text-muted cursor-pointer">
                        스택 트레이스 보기
                      </summary>
                      <pre className="mt-2 text-xs text-text-muted overflow-auto max-h-40">
                        {this.state.errorInfo.componentStack}
                      </pre>
                    </details>
                  )}
                </div>
              )}

              {/* 액션 버튼들 */}
              <div className="flex gap-3 justify-center">
                <button
                  onClick={this.handleRetry}
                  className="btn btn-primary"
                >
                  다시 시도
                </button>
                <button
                  onClick={this.handleGoHome}
                  className="btn btn-secondary"
                >
                  로비로 이동
                </button>
              </div>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

/**
 * 테이블 페이지 전용 에러 바운더리
 * 게임 상태 복구 옵션 포함
 */
interface TableErrorBoundaryProps {
  children: ReactNode;
  tableId?: string;
  onReconnect?: () => void;
}

export function TableErrorBoundary({ 
  children, 
  tableId,
  onReconnect 
}: TableErrorBoundaryProps) {
  const handleError = (error: Error) => {
    // 에러 로깅 (추후 Sentry 등 연동 가능)
    console.error('[TableErrorBoundary] 테이블 에러:', {
      tableId,
      error: error.message,
      timestamp: new Date().toISOString(),
    });
  };

  return (
    <ErrorBoundary
      onError={handleError}
      fallback={
        <div className="min-h-screen flex items-center justify-center bg-black p-4">
          <div className="max-w-md w-full bg-surface/90 backdrop-blur rounded-xl p-6 shadow-lg border border-border">
            <div className="text-center">
              {/* 포커 아이콘 */}
              <div className="w-20 h-20 mx-auto mb-4 rounded-full bg-gradient-to-br from-primary/20 to-accent/20 flex items-center justify-center">
                <span className="text-4xl">🃏</span>
              </div>

              <h2 className="text-xl font-bold text-text-primary mb-2">
                게임 연결에 문제가 발생했습니다
              </h2>
              
              <p className="text-text-secondary mb-6">
                네트워크 상태를 확인하고 다시 시도해주세요.
                {tableId && (
                  <span className="block text-sm text-text-muted mt-1">
                    테이블 ID: {tableId.slice(0, 8)}...
                  </span>
                )}
              </p>

              <div className="flex flex-col gap-3">
                {onReconnect && (
                  <button
                    onClick={onReconnect}
                    className="btn btn-primary w-full"
                  >
                    🔄 재연결
                  </button>
                )}
                <button
                  onClick={() => window.location.reload()}
                  className="btn btn-secondary w-full"
                >
                  🔃 페이지 새로고침
                </button>
                <button
                  onClick={() => window.location.href = '/lobby'}
                  className="btn btn-secondary w-full"
                >
                  🏠 로비로 이동
                </button>
              </div>
            </div>
          </div>
        </div>
      }
    >
      {children}
    </ErrorBoundary>
  );
}

export default ErrorBoundary;
