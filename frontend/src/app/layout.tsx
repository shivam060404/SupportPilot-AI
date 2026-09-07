import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "SupportPilot AI",
  description: "Grounded IT support assistance"
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
