import { createDocsOptions } from "@/components/layout.config";
import { source } from "@/libs/source";
import { DocsLayout } from "fumadocs-ui/layouts/docs";
import type { ReactNode } from "react";

export default function Layout({ children }: { children: ReactNode }) {
  // Create the docs options with the page tree from source
  const docsOptions = createDocsOptions(source.pageTree);

  return <DocsLayout {...docsOptions}>{children}</DocsLayout>;
}
