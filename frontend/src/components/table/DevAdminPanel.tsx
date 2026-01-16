'use client';

import { useState } from 'react';

interface DevAdminPanelProps {
  tableId: string;
  onReset: () => void;
  onAddBot: () => void;
  onStartBotLoop: () => void;
  isResetting: boolean;
  isAddingBot: boolean;
  isStartingLoop: boolean;
}

export function DevAdminPanel({
  tableId,
  onReset,
  onAddBot,
  onStartBotLoop,
  isResetting,
  isAddingBot,
  isStartingLoop,
}: DevAdminPanelProps) {
  const [isOpen, setIsOpen] = useState(true); // 기본 펼침

  return (
    <div className="fixed bottom-4 right-4 z-[150]">
      {/* 패널 (기본 펼침) */}
      {isOpen ? (
        <div className="w-64 bg-gray-900 border border-gray-700 rounded-lg shadow-xl p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              <span>🛠</span> DEV 패널
            </h3>
            <button
              onClick={() => setIsOpen(false)}
              className="text-gray-400 hover:text-white transition-colors"
            >
              ✕
            </button>
          </div>

          <div className="space-y-2">
            {/* 봇 자동 루프 시작 */}
            <button
              onClick={onStartBotLoop}
              disabled={isStartingLoop}
              className="w-full px-3 py-2 bg-green-600 hover:bg-green-700 disabled:bg-green-900 disabled:opacity-50 text-white text-sm rounded transition-colors flex items-center justify-center gap-2"
            >
              {isStartingLoop ? (
                <>
                  <span className="animate-spin">⏳</span> 시작 중...
                </>
              ) : (
                <>
                  <span>🤖</span> 봇 자동 루프 시작
                </>
              )}
            </button>

            {/* 봇 추가 */}
            <button
              onClick={onAddBot}
              disabled={isAddingBot}
              className="w-full px-3 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-900 disabled:opacity-50 text-white text-sm rounded transition-colors flex items-center justify-center gap-2"
            >
              {isAddingBot ? (
                <>
                  <span className="animate-spin">⏳</span> 추가 중...
                </>
              ) : (
                <>
                  <span>🤖</span> 봇 1개 추가
                </>
              )}
            </button>

            {/* 전체 리셋 (봇 제거 + 테이블 리셋 통합) */}
            <button
              onClick={onReset}
              disabled={isResetting}
              className="w-full px-3 py-2 bg-red-600 hover:bg-red-700 disabled:bg-red-900 disabled:opacity-50 text-white text-sm rounded transition-colors flex items-center justify-center gap-2"
            >
              {isResetting ? (
                <>
                  <span className="animate-spin">⏳</span> 리셋 중...
                </>
              ) : (
                <>
                  <span>🔄</span> 전체 리셋
                </>
              )}
            </button>

            {/* 테이블 ID 표시 */}
            <div className="mt-3 pt-3 border-t border-gray-700">
              <p className="text-xs text-gray-500">Table ID:</p>
              <p className="text-xs text-gray-400 font-mono truncate">{tableId}</p>
            </div>
          </div>
        </div>
      ) : (
        /* 토글 버튼 (접힘 상태) */
        <button
          onClick={() => setIsOpen(true)}
          className="w-12 h-12 rounded-full bg-gray-800 border border-gray-600 text-white flex items-center justify-center shadow-lg hover:bg-gray-700 transition-colors"
          title="개발자 도구"
        >
          ⚙
        </button>
      )}
    </div>
  );
}
