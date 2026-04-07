import type { Metadata } from "next";
import "./globals.css";
import { ToastContainer } from "@/components/ui/toast";

export const metadata: Metadata = {
  title: "Analyst Pro — AI-Powered Data Analytics",
  description: "Upload data, get instant AI insights, charts, and reports. Built for analysts.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className="bg-[#0a0a0b] text-white antialiased">
        {children}
        <ToastContainer />
      </body>
    </html>
  );
}