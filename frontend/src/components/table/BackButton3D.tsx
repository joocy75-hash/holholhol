'use client';

import { useState, useCallback } from 'react';

interface BackButton3DProps {
  onClick: () => void;
  disabled?: boolean;
  children?: React.ReactNode;
  className?: string;
}

/**
 * 3D 스타일 뒤로가기 버튼
 * Figma 디자인 기반: https://www.figma.com/design/xeHxaQYIt8eUfVHSbqi7aJ/3D-Interactive-Button
 */
export function BackButton3D({ onClick, disabled = false, children, className = '' }: BackButton3DProps) {
  const [isPressed, setIsPressed] = useState(false);

  const handleMouseDown = useCallback(() => {
    if (!disabled) setIsPressed(true);
  }, [disabled]);

  const handleMouseUp = useCallback(() => {
    setIsPressed(false);
  }, []);

  const handleMouseLeave = useCallback(() => {
    setIsPressed(false);
  }, []);

  const handleClick = useCallback(() => {
    if (!disabled) onClick();
  }, [disabled, onClick]);

  return (
    <button
      onClick={handleClick}
      onMouseDown={handleMouseDown}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseLeave}
      onTouchStart={handleMouseDown}
      onTouchEnd={handleMouseUp}
      disabled={disabled}
      className={`
        relative block cursor-pointer select-none
        transition-all duration-100 ease-out
        ${disabled ? 'opacity-50 cursor-not-allowed' : ''}
        ${className}
      `}
      style={{
        width: 120,
        height: 48,
      }}
    >
      {/* 배경 그림자 (버튼 뒤 어두운 영역) */}
      <div
        className="absolute rounded-[14px] transition-all duration-100"
        style={{
          inset: isPressed ? '12% -0.85% -8% -0.85%' : '10% -0.85% -15% -0.85%',
          backgroundColor: 'rgba(0, 0, 0, 0.24)',
          boxShadow: 'inset 0px 0px 2px 2px rgba(0, 0, 0, 0.24)',
        }}
      />

      {/* 바닥 그림자 (흐릿한 그림자) */}
      {!isPressed && (
        <div
          className="absolute rounded-[12px] transition-opacity duration-100"
          style={{
            inset: '61.25% 1.71% -30% 1.71%',
            backgroundColor: 'rgba(0, 0, 0, 0.4)',
            filter: 'blur(8px)',
          }}
        />
      )}

      {/* 버튼 측면 (3D 깊이감) */}
      <div
        className="absolute rounded-[12px] transition-all duration-100"
        style={{
          inset: isPressed ? '12% 0 -6% 0' : '10% 0 -10% 0',
          backgroundColor: '#107283',
        }}
      />

      {/* 메인 버튼 표면 */}
      <div
        className="absolute rounded-[12px] overflow-hidden transition-all duration-100 flex items-center justify-center"
        style={{
          inset: '0',
          top: isPressed ? 6 : 0,
          background: 'linear-gradient(180deg, #56CCD3 0%, #45B3B2 100%)',
          boxShadow: isPressed
            ? 'inset 0px -1px 1px 1px #107283'
            : 'inset 0px -2px 2px 1px #107283',
        }}
      >
        {/* 버튼 텍스트 */}
        <span
          className="relative text-sm font-bold uppercase tracking-wide"
          style={{
            color: '#3B9294',
            textShadow: '0 1px 0 rgba(255, 255, 255, 0.3)',
            filter: 'blur(0.3px)',
          }}
        >
          {children || '← 나가기'}
        </span>
      </div>
    </button>
  );
}

/**
 * 청록색 버전의 3D 버튼 (원본 Figma 디자인)
 */
export function Button3DTeal({
  onClick,
  disabled = false,
  children,
  className = ''
}: BackButton3DProps) {
  const [isPressed, setIsPressed] = useState(false);

  const handleMouseDown = useCallback(() => {
    if (!disabled) setIsPressed(true);
  }, [disabled]);

  const handleMouseUp = useCallback(() => {
    setIsPressed(false);
  }, []);

  const handleMouseLeave = useCallback(() => {
    setIsPressed(false);
  }, []);

  const handleClick = useCallback(() => {
    if (!disabled) onClick();
  }, [disabled, onClick]);

  return (
    <button
      onClick={handleClick}
      onMouseDown={handleMouseDown}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseLeave}
      onTouchStart={handleMouseDown}
      onTouchEnd={handleMouseUp}
      disabled={disabled}
      className={`
        relative block cursor-pointer select-none
        transition-all duration-100 ease-out
        ${disabled ? 'opacity-50 cursor-not-allowed' : ''}
        ${className}
      `}
      style={{
        width: 140,
        height: 52,
      }}
    >
      {/* 배경 그림자 */}
      <div
        className="absolute rounded-[14px] transition-all duration-100"
        style={{
          inset: isPressed ? '12% -0.85% -8% -0.85%' : '10% -0.85% -15% -0.85%',
          backgroundColor: 'rgba(0, 0, 0, 0.24)',
          boxShadow: 'inset 0px 0px 2px 2px rgba(0, 0, 0, 0.24)',
        }}
      />

      {/* 바닥 그림자 */}
      {!isPressed && (
        <div
          className="absolute rounded-[12px]"
          style={{
            inset: '61.25% 1.71% -30% 1.71%',
            backgroundColor: 'rgba(0, 0, 0, 0.4)',
            filter: 'blur(8px)',
          }}
        />
      )}

      {/* 버튼 측면 */}
      <div
        className="absolute rounded-[12px] transition-all duration-100"
        style={{
          inset: isPressed ? '12% 0 -6% 0' : '10% 0 -10% 0',
          backgroundColor: '#107283',
        }}
      />

      {/* 메인 버튼 표면 */}
      <div
        className="absolute rounded-[12px] overflow-hidden transition-all duration-100 flex items-center justify-center"
        style={{
          inset: '0',
          top: isPressed ? 6 : 0,
          background: 'linear-gradient(180deg, #56CCD3 0%, #45B3B2 100%)',
          boxShadow: isPressed
            ? 'inset 0px -1px 1px 1px #107283'
            : 'inset 0px -2px 2px 1px #107283',
        }}
      >
        <span
          className="relative text-sm font-bold uppercase tracking-wide"
          style={{
            color: '#3B9294',
            textShadow: '0 1px 0 rgba(255, 255, 255, 0.3)',
            filter: 'blur(0.3px)',
          }}
        >
          {children || 'CLICK ME'}
        </span>
      </div>
    </button>
  );
}

export default BackButton3D;
