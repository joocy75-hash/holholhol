const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001';

interface RequestOptions extends RequestInit {
  token?: string;
  skipRetry?: boolean;
  skipAuthRefresh?: boolean;
}

// Convert snake_case to camelCase
function toCamelCase(obj: unknown): unknown {
  if (Array.isArray(obj)) {
    return obj.map(toCamelCase);
  }
  if (obj !== null && typeof obj === 'object') {
    return Object.keys(obj).reduce((result, key) => {
      const camelKey = key.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase());
      (result as Record<string, unknown>)[camelKey] = toCamelCase((obj as Record<string, unknown>)[key]);
      return result;
    }, {} as Record<string, unknown>);
  }
  return obj;
}

// Retry configuration
const RETRY_CONFIG = {
  maxRetries: 3,
  baseDelay: 1000, // 1 second
  maxDelay: 10000, // 10 seconds
  retryableStatuses: [408, 429, 500, 502, 503, 504],
};

// Sleep utility for retry delays
const sleep = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

// Calculate exponential backoff delay
function getRetryDelay(attempt: number): number {
  const delay = Math.min(
    RETRY_CONFIG.baseDelay * Math.pow(2, attempt),
    RETRY_CONFIG.maxDelay
  );
  // Add jitter (random 0-25% of delay)
  return delay + Math.random() * delay * 0.25;
}

// Check if error is retryable
function isRetryableError(status: number): boolean {
  return RETRY_CONFIG.retryableStatuses.includes(status);
}

// Auth event emitter for 401 handling
type AuthEventCallback = () => void;
const authEventListeners: AuthEventCallback[] = [];

export function onAuthError(callback: AuthEventCallback) {
  authEventListeners.push(callback);
  return () => {
    const index = authEventListeners.indexOf(callback);
    if (index > -1) authEventListeners.splice(index, 1);
  };
}

function emitAuthError() {
  authEventListeners.forEach(cb => cb());
}

class ApiClient {
  private baseUrl: string;
  private isRefreshing = false;
  private refreshPromise: Promise<boolean> | null = null;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
  }

  private async request<T>(
    endpoint: string,
    options: RequestOptions = {}
  ): Promise<T> {
    const { token, skipRetry = false, skipAuthRefresh = false, ...fetchOptions } = options;

    const headers: HeadersInit = {
      'Content-Type': 'application/json',
      ...options.headers,
    };

    if (token) {
      (headers as Record<string, string>)['Authorization'] = `Bearer ${token}`;
    }

    let lastError: Error | null = null;
    const maxAttempts = skipRetry ? 1 : RETRY_CONFIG.maxRetries + 1;

    for (let attempt = 0; attempt < maxAttempts; attempt++) {
      try {
        const response = await fetch(`${this.baseUrl}${endpoint}`, {
          ...fetchOptions,
          headers,
        });

        // Handle 401 Unauthorized
        if (response.status === 401 && !skipAuthRefresh) {
          console.warn('[API] 401 Unauthorized - 세션 만료');
          emitAuthError();
          throw new Error('세션이 만료되었습니다. 다시 로그인해주세요.');
        }

        // Handle other errors
        if (!response.ok) {
          const errorStatus = response.status;

          // Check if we should retry
          if (!skipRetry && isRetryableError(errorStatus) && attempt < RETRY_CONFIG.maxRetries) {
            const delay = getRetryDelay(attempt);
            console.warn(`[API] ${errorStatus} 에러 발생, ${delay}ms 후 재시도 (${attempt + 1}/${RETRY_CONFIG.maxRetries})`);
            await sleep(delay);
            continue;
          }

          const error = await response.json().catch(() => ({
            message: 'An error occurred',
          }));
          throw new Error(error.detail || error.message || `HTTP ${response.status}`);
        }

        // Handle empty responses (204 No Content)
        if (response.status === 204) {
          return undefined as T;
        }

        const data = await response.json();
        return toCamelCase(data) as T;

      } catch (error) {
        lastError = error instanceof Error ? error : new Error(String(error));

        // Network error - retry if possible
        if (
          !skipRetry &&
          attempt < RETRY_CONFIG.maxRetries &&
          (error instanceof TypeError || // Network error
           lastError.message.includes('fetch') ||
           lastError.message.includes('network'))
        ) {
          const delay = getRetryDelay(attempt);
          console.warn(`[API] 네트워크 에러, ${delay}ms 후 재시도 (${attempt + 1}/${RETRY_CONFIG.maxRetries})`);
          await sleep(delay);
          continue;
        }

        // Don't retry auth errors or other non-retryable errors
        throw lastError;
      }
    }

    throw lastError || new Error('요청에 실패했습니다.');
  }

  get<T>(endpoint: string, options?: RequestOptions): Promise<T> {
    return this.request<T>(endpoint, { ...options, method: 'GET' });
  }

  post<T>(endpoint: string, data?: unknown, options?: RequestOptions): Promise<T> {
    return this.request<T>(endpoint, {
      ...options,
      method: 'POST',
      body: data ? JSON.stringify(data) : undefined,
    });
  }

  put<T>(endpoint: string, data?: unknown, options?: RequestOptions): Promise<T> {
    return this.request<T>(endpoint, {
      ...options,
      method: 'PUT',
      body: data ? JSON.stringify(data) : undefined,
    });
  }

  patch<T>(endpoint: string, data?: unknown, options?: RequestOptions): Promise<T> {
    return this.request<T>(endpoint, {
      ...options,
      method: 'PATCH',
      body: data ? JSON.stringify(data) : undefined,
    });
  }

  delete<T>(endpoint: string, options?: RequestOptions): Promise<T> {
    return this.request<T>(endpoint, { ...options, method: 'DELETE' });
  }

  // Health check method
  async healthCheck(): Promise<boolean> {
    try {
      const response = await fetch(`${this.baseUrl}/health`, {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' },
      });
      return response.ok;
    } catch {
      return false;
    }
  }
}

export const api = new ApiClient(API_BASE_URL);

// Main Backend API (for partner/settlement routes)
const MAIN_API_BASE_URL = process.env.NEXT_PUBLIC_MAIN_API_URL || 'http://localhost:8000';
export const mainApi = new ApiClient(MAIN_API_BASE_URL);
