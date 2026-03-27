import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Analyst Pro",
  description: "AI analytics SaaS for startups and small teams",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className="bg-[#0a0a0b] text-white antialiased">{children}</body>
    </html>
  );
}