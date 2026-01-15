/**
 * API 에러 타입 정의
 * 
 * 백엔드에서 반환하는 에러 형식과 일치합니다.
 */

import { AxiosError } from 'axios';

/**
 * 백엔드 API 에러 응답 구조
 */
export interface ApiErrorResponse {
  error?: {
    code?: string;
    message: string;
    details?: Record<string, unknown>;
  };
  detail?: string | { msg: string; type: string }[];
  message?: string;
}

/**
 * 구조화된 API 에러
 */
export interface ApiError {
  code: string;
  message: string;
  status?: number;
  details?: Record<string, unknown>;
}

/**
 * Axios 에러에서 사용자 친화적인 에러 메시지 추출
 */
export function extractErrorMessage(error: unknown, fallback: string = '오류가 발생했습니다.'): string {
  // Axios 에러인 경우
  if (isAxiosError(error)) {
    const response = error.response?.data as ApiErrorResponse | undefined;
    
    // error.message 형식
    if (response?.error?.message) {
      return response.error.message;
    }
    
    // detail 문자열 형식
    if (typeof response?.detail === 'string') {
      return response.detail;
    }
    
    // detail 배열 형식 (FastAPI 검증 에러)
    if (Array.isArray(response?.detail)) {
      return response.detail.map(d => d.msg).join(', ');
    }
    
    // message 형식
    if (response?.message) {
      return response.message;
    }
    
    // HTTP 상태 기반 메시지
    if (error.response?.status) {
      return getHttpErrorMessage(error.response.status);
    }
    
    // 네트워크 에러
    if (error.message === 'Network Error') {
      return '네트워크 연결을 확인해주세요.';
    }
  }
  
  // 일반 Error 인스턴스
  if (error instanceof Error) {
    return error.message;
  }
  
  return fallback;
}

/**
 * Axios 에러에서 구조화된 ApiError 추출
 */
export function extractApiError(error: unknown): ApiError {
  if (isAxiosError(error)) {
    const response = error.response?.data as ApiErrorResponse | undefined;
    
    return {
      code: response?.error?.code || `HTTP_${error.response?.status || 'UNKNOWN'}`,
      message: extractErrorMessage(error),
      status: error.response?.status,
      details: response?.error?.details,
    };
  }
  
  if (error instanceof Error) {
    return {
      code: 'UNKNOWN_ERROR',
      message: error.message,
    };
  }
  
  return {
    code: 'UNKNOWN_ERROR',
    message: '알 수 없는 오류가 발생했습니다.',
  };
}

/**
 * HTTP 상태 코드에 따른 사용자 친화적 메시지
 */
function getHttpErrorMessage(status: number): string {
  switch (status) {
    case 400:
      return '잘못된 요청입니다.';
    case 401:
      return '로그인이 필요합니다.';
    case 403:
      return '접근 권한이 없습니다.';
    case 404:
      return '요청한 리소스를 찾을 수 없습니다.';
    case 409:
      return '충돌이 발생했습니다. 다시 시도해주세요.';
    case 422:
      return '입력 데이터를 확인해주세요.';
    case 429:
      return '요청이 너무 많습니다. 잠시 후 다시 시도해주세요.';
    case 500:
      return '서버 오류가 발생했습니다.';
    case 502:
    case 503:
    case 504:
      return '서버가 일시적으로 이용 불가합니다.';
    default:
      return '오류가 발생했습니다.';
  }
}

/**
 * Axios 에러 타입 가드
 */
export function isAxiosError(error: unknown): error is AxiosError<ApiErrorResponse> {
  return (
    typeof error === 'object' &&
    error !== null &&
    'isAxiosError' in error &&
    (error as AxiosError).isAxiosError === true
  );
}

/**
 * 네트워크 에러 여부 확인
 */
export function isNetworkError(error: unknown): boolean {
  if (isAxiosError(error)) {
    return error.message === 'Network Error' || !error.response;
  }
  return false;
}

/**
 * 인증 에러 여부 확인
 */
export function isAuthError(error: unknown): boolean {
  if (isAxiosError(error)) {
    return error.response?.status === 401;
  }
  return false;
}
