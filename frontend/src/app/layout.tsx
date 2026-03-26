import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "DataLens AI",
  description: "Ask natural language questions about your database.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className="h-full">
      <body className="h-full flex flex-col overflow-hidden">{children}</body>
    </html>
  );
}
