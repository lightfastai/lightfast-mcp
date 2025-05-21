import { RootProvider } from "fumadocs-ui/provider";
import "./globals.css";
import type { Metadata } from "next";
import type { ReactNode } from "react";

import { GeistMono } from "geist/font/mono";
import { GeistSans } from "geist/font/sans";
import { cn } from "../libs/utils";

export const fonts = cn(
  GeistSans.variable,
  GeistMono.variable,
  "touch-manipulation font-sans antialiased"
);

export const metadata: Metadata = {
  title: "Lightfast MCP Documentation",
  description: "Documentation for Lightfast MCP",
};

export default function Layout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body
        className={cn(
          fonts,
          "bg-background text-foreground flex flex-col min-h-screen"
        )}
      >
        <RootProvider>{children}</RootProvider>
      </body>
    </html>
  );
}
