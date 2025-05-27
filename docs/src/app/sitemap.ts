import type { MetadataRoute } from "next";

import { createBaseUrl } from "@/libs/base-url";
import { source } from "@/libs/source";

/**
 * Generates the sitemap for the application.
 *
 * Includes:
 * - Homepage (highest priority, monthly updates)
 * - All documentation pages from the source
 * - Static pages with appropriate priorities
 *
 * @returns {MetadataRoute.Sitemap} Next.js compatible sitemap configuration
 */
export default function sitemap(): MetadataRoute.Sitemap {
  const baseUrl = createBaseUrl();
  
  // Start with the homepage
  const routes: MetadataRoute.Sitemap = [
    {
      url: baseUrl,
      lastModified: new Date(),
      changeFrequency: "monthly",
      priority: 1,
    },
  ];

  // Add all documentation pages
  const pages = source.getPages();
  for (const page of pages) {
    routes.push({
      url: `${baseUrl}/docs/${page.slugs.join("/")}`,
      lastModified: new Date(),
      changeFrequency: "weekly",
      priority: 0.8,
    });
  }

  // Add any additional static pages
  const staticPages = [
    {
      path: "/docs",
      priority: 0.9,
      changeFrequency: "weekly" as const,
    },
  ];

  for (const staticPage of staticPages) {
    routes.push({
      url: `${baseUrl}${staticPage.path}`,
      lastModified: new Date(),
      changeFrequency: staticPage.changeFrequency,
      priority: staticPage.priority,
    });
  }

  return routes;
} 