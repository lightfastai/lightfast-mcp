import { z } from "zod";

import { env } from "@/env";

/**
 * Schema for validating URL suffixes.
 * - Must start with a forward slash if provided
 * - Cannot contain protocol or domain parts
 * - Allows alphanumeric characters, slashes, hyphens, and underscores
 */
const urlSuffixSchema = z
  .string()
  .regex(/^\/.*$/, "Suffix must start with '/' if provided")
  .regex(/^(?!https?:\/\/).*$/, "Suffix cannot contain protocol")
  .regex(
    /^[/a-zA-Z0-9-_]*$/,
    "Suffix can only contain alphanumeric characters, slashes, hyphens, and underscores",
  )
  .or(z.literal(""))
  .transform((suffix) => suffix.replace(/\/+/g, "/")); // normalize multiple slashes

type UrlSuffix = z.infer<typeof urlSuffixSchema>;

/**
 * Creates a base URL with optional path suffix based on the current environment.
 *
 * @param {UrlSuffix} [suffix] - Optional path suffix to append to the base URL (must start with '/' if provided)
 * @returns {string} The complete URL for the current environment
 * @throws {Error} If suffix validation fails
 * @private
 */
const createEnvironmentUrl = (suffix: UrlSuffix = ""): string => {
  // eslint-disable-next-line no-restricted-properties
  const port = process.env.PORT ?? 3000;

  // Parse and validate the suffix
  const parsedSuffix = urlSuffixSchema.parse(suffix);

  if (env.NODE_ENV === "production") {
    // Use custom domain if available, otherwise fall back to Vercel URL
    const host = env.NEXT_PUBLIC_SITE_URL 
      ? new URL(env.NEXT_PUBLIC_SITE_URL).host
      : env.VERCEL_URL ?? "mcp.lightfast.ai";
    return `https://${host}${parsedSuffix}`;
  }

  if (env.VERCEL_URL) {
    return `https://${env.VERCEL_URL}${parsedSuffix}`;
  }

  return `http://localhost:${port}${parsedSuffix}`;
};

/**
 * Gets the base URL for the application.
 *
 * @returns {string} The complete base URL for the current environment
 */
export const createBaseUrl = (): string => createEnvironmentUrl(); 