"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { tablesApi } from "@/lib/api";
import { isAxiosError, type ApiErrorResponse } from "@/types/errors";

const springTransition = { type: "spring" as const, stiffness: 400, damping: 25 };

interface QuickJoinButtonProps {
  blindLevel?: string;
  className?: string;
}

export default function QuickJoinButton({ blindLevel, className }: QuickJoinButtonProps) {
  const router = useRouter();
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleQuickJoin = async () => {
    if (isLoading) return;
    
    setIsLoading(true);
    setError(null);

    try {
      const response = await tablesApi.quickJoin(blindLevel);
      const data = response.data;
      
      // Navigate to the table
      router.push(`/table/${data.roomId}`);
    } catch (err: unknown) {
      let errorCode = "UNKNOWN_ERROR";
      
      if (isAxiosError(err)) {
        const errorData = (err.response?.data as ApiErrorResponse)?.error;
        errorCode = errorData?.code || "UNKNOWN_ERROR";
      }
      
      // Map error codes to user-friendly messages
      const errorMessages: Record<string, string> = {
        NO_AVAILABLE_ROOM: "입장 가능한 방이 없습니다",
        INSUFFICIENT_BALANCE: "잔액이 부족합니다",
        ALREADY_SEATED: "이미 다른 방에 참여 중입니다",
        ROOM_FULL: "방이 가득 찼습니다",
        UNAUTHORIZED: "로그인이 필요합니다",
      };
      
      setError(errorMessages[errorCode] || "빠른 입장에 실패했습니다");
      
      // Clear error after 3 seconds
      setTimeout(() => setError(null), 3000);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className={className} style={{ position: "relative" }}>
      <motion.button
        onClick={handleQuickJoin}
        disabled={isLoading}
        whileHover={!isLoading ? {
          filter: "brightness(1.15)",
          boxShadow: "0 0 25px rgba(255, 193, 7, 0.5), 0 4px 15px rgba(0, 0, 0, 0.3)",
        } : undefined}
        whileTap={!isLoading ? { scale: 0.97 } : undefined}
        transition={springTransition}
        style={{
          width: "100%",
          minWidth: "160px",
          height: "48px",
          background: isLoading 
            ? "linear-gradient(135deg, #666 0%, #444 100%)"
            : "linear-gradient(135deg, #FFD700 0%, #FFA500 50%, #FF8C00 100%)",
          border: "2px solid rgba(255, 215, 0, 0.6)",
          borderRadius: "24px",
          boxShadow: "0 4px 15px rgba(255, 165, 0, 0.4), inset 0 1px 0 rgba(255, 255, 255, 0.3)",
          cursor: isLoading ? "not-allowed" : "pointer",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          gap: "8px",
          padding: "0 24px",
          opacity: isLoading ? 0.7 : 1,
        }}
      >
        {/* Loading spinner */}
        {isLoading && (
          <motion.div
            animate={{ rotate: 360 }}
            transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
            style={{
              width: "20px",
              height: "20px",
              border: "2px solid rgba(255, 255, 255, 0.3)",
              borderTopColor: "white",
              borderRadius: "50%",
            }}
          />
        )}
        
        {/* Button text */}
        <span
          style={{
            fontFamily: "Paperlogy, sans-serif",
            fontWeight: 700,
            fontSize: "16px",
            color: isLoading ? "#ccc" : "#1a1a1a",
            textShadow: "0 1px 0 rgba(255, 255, 255, 0.3)",
            letterSpacing: "0.5px",
          }}
        >
          {isLoading ? "입장 중..." : "⚡ 빠른 입장"}
        </span>
      </motion.button>

      {/* Error toast */}
      <AnimatePresence>
        {error && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            style={{
              position: "absolute",
              top: "calc(100% + 8px)",
              left: "50%",
              transform: "translateX(-50%)",
              background: "rgba(220, 53, 69, 0.95)",
              color: "white",
              padding: "8px 16px",
              borderRadius: "8px",
              fontSize: "13px",
              fontWeight: 500,
              whiteSpace: "nowrap",
              boxShadow: "0 4px 12px rgba(0, 0, 0, 0.3)",
              zIndex: 100,
            }}
          >
            {error}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
