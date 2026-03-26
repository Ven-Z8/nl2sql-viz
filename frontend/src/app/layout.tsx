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
    <html lang="en">
      <body className="flex flex-col">{children}</body>
    </html>
  );
}
