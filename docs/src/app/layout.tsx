import { RootProvider } from "fumadocs-ui/provider";
import "./globals.css";
import type { Metadata } from "next";

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

interface RootLayoutProperties {
  readonly children: React.ReactNode;
}

export default function RootLayout({ children }: RootLayoutProperties) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={cn(fonts, "text-foreground flex flex-col min-h-screen")}>
        <RootProvider>{children}</RootProvider>
      </body>
    </html>
  );
}
