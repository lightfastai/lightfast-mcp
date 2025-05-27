import { RootProvider } from "fumadocs-ui/provider";
import "./globals.css";
import type { Metadata, Viewport } from "next";
import { ThemeProvider } from "next-themes";

import { cn } from "../libs/utils";
import { fonts } from "../libs/fonts";
import { siteConfig } from "../libs/site-config";

export const metadata: Metadata = {
  title: {
    default: siteConfig.name,
    template: `%s - ${siteConfig.name}`,
  },
  metadataBase: new URL(siteConfig.url),
  description: siteConfig.description,
  keywords: [
    "Lightfast",
    "MCP",
    "Model Context Protocol",
    "AI",
    "Creative Applications",
    "Blender",
    "TouchDesigner",
    "Unreal Engine",
    "Adobe Creative Suite",
    "Automation",
    "3D Modeling",
    "Animation",
    "Creative Workflows",
  ],
  authors: [
    {
      name: siteConfig.name,
      url: siteConfig.url,
    },
  ],
  creator: siteConfig.name,
  openGraph: {
    type: "website",
    locale: "en_US",
    url: siteConfig.url,
    title: siteConfig.name,
    description: siteConfig.description,
    siteName: siteConfig.name,
    images: [
      {
        url: siteConfig.ogImage,
        width: 1200,
        height: 630,
        alt: siteConfig.name,
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: siteConfig.name,
    description: siteConfig.description,
    images: [siteConfig.ogImage],
    creator: "@lightfastai",
  },
  icons: {
    icon: "/favicon.ico",
    shortcut: "/favicon-16x16.png",
    apple: "/apple-touch-icon.png",
    other: [
      {
        rel: "icon",
        url: "/favicon-32x32.png",
      },
      {
        rel: "icon",
        url: "/android-chrome-192x192.png",
      },
      {
        rel: "icon",
        url: "/android-chrome-512x512.png",
      },
    ],
  },
  applicationName: siteConfig.name,
  appleWebApp: {
    capable: true,
    statusBarStyle: "default",
    title: siteConfig.name,
  },
  formatDetection: {
    telephone: false,
  },
};

export const viewport: Viewport = {
  themeColor: "#121212",
};

interface RootLayoutProperties {
  readonly children: React.ReactNode;
}

export default function RootLayout({ children }: RootLayoutProperties) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={cn(fonts, "text-foreground flex flex-col min-h-screen")}>
        <ThemeProvider attribute="class" defaultTheme="dark">
          <RootProvider
            search={{
              enabled: true,
            }}
          >
            {children}
          </RootProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
