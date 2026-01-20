"use client";

import { useEffect, useRef } from "react";
import { usePathname } from "next/navigation";
import { useSettingsStore } from "@/stores/settings";

// BGM 볼륨 설정
const TARGET_VOLUME = 0.3;

export default function LobbyBGM() {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const fadeIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const pathname = usePathname();
  const bgmEnabled = useSettingsStore((state) => state.bgmEnabled);

  // 게임방(/table/*), 로그인 페이지에서는 BGM 비활성화
  const isPageMuted = pathname?.startsWith("/table/") || pathname === "/login";
  const shouldMute = isPageMuted || !bgmEnabled;

  useEffect(() => {
    if (!audioRef.current) {
      audioRef.current = new Audio("/sounds/bgm/lobby_bgm.webm");
      audioRef.current.loop = true;
      audioRef.current.volume = TARGET_VOLUME;
    }

    const audio = audioRef.current;

    if (fadeIntervalRef.current) {
      clearInterval(fadeIntervalRef.current);
      fadeIntervalRef.current = null;
    }

    if (shouldMute) {
      // 즉시 정지
      audio.volume = 0;
      audio.pause();
    } else {
      audio.volume = TARGET_VOLUME;
      const playAudio = () => {
        audio.play().catch(() => {
          const handleClick = () => {
            audio.play();
            document.removeEventListener("click", handleClick);
          };
          document.addEventListener("click", handleClick);
        });
      };
      playAudio();
    }

    return () => {};
  }, [shouldMute]);

  useEffect(() => {
    return () => {
      if (fadeIntervalRef.current) {
        clearInterval(fadeIntervalRef.current);
        fadeIntervalRef.current = null;
      }
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current = null;
      }
    };
  }, []);

  return null;
}
