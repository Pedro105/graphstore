import type { Metadata } from "next";
import {
  Cormorant_Garamond,
  Geist_Mono,
  Inter,
  Quicksand,
} from "next/font/google";
import "./globals.css";

const quicksand = Quicksand({
  variable: "--font-sans",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

// Dashboard default typeface. "Google Sans" is a proprietary Google UI font and
// isn't served by Google Fonts / next/font/google, so per spec we use Inter --
// visually close, variable, and a clean fit for a developer tool. Scoped to the
// dashboard via --font-inter (the landing keeps Quicksand on --font-sans).
const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

const cormorant = Cormorant_Garamond({
  variable: "--font-serif",
  subsets: ["latin"],
  weight: ["300", "400", "500", "600"],
  style: ["normal", "italic"],
});

export const metadata: Metadata = {
  title: "ContextStore — GraphRAG memory for AI workflows",
  description:
    "A GraphRAG-based memory layer for AI workflows. Agents, scheduled jobs, and AI features write structured knowledge to a shared graph and query it together.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${quicksand.variable} ${inter.variable} ${geistMono.variable} ${cormorant.variable} antialiased`}
      >
        {children}
      </body>
    </html>
  );
}
