import type { Metadata } from "next";
import "./globals.css";
import { AnnouncementProvider } from "@/components/announcements";

export const metadata: Metadata = {
  title: "Poker Holdem - 온라인 텍사스 홀덤",
  description: "실시간 온라인 텍사스 홀덤 포커 게임",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ko">
      <body className="antialiased">
        <AnnouncementProvider />
        {children}
      </body>
    </html>
  );
}
