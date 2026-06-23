import "./globals.css";

import type { Metadata } from "next";

import { Footer } from "@/components/footer";
import { Nav } from "@/components/nav";
import { Providers } from "@/app/providers";

export const metadata: Metadata = {
  title: "Flick — group movie nights, decided",
  description:
    "Find what to watch together. Real-time group voting with AI-powered consensus picks.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="min-h-screen">
        <Providers>
          <div className="min-h-screen flex flex-col">
            <Nav />
            <main className="container py-8 flex-1">{children}</main>
            <Footer />
          </div>
        </Providers>
      </body>
    </html>
  );
}
