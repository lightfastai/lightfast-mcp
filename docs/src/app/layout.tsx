import { RootProvider } from "fumadocs-ui/provider";
import "./globals.css";
import type { Metadata } from "next";

import { cn } from "../libs/utils";
import { fonts } from "../libs/fonts";

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
