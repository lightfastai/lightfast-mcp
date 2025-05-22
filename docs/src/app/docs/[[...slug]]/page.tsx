import { getMDXComponents } from "@/components/mdx-components";
import { source } from "@/libs/source";
import {
  DocsBody,
  DocsDescription,
  DocsPage,
  DocsTitle,
} from "fumadocs-ui/page";
import { notFound } from "next/navigation";
import Link from "next/link";
import { Icons } from "@/components/icons";

// Title bar component with GitHub and Lightfast links
function TitleBar() {
  return (
    <div className="w-full flex justify-between items-center py-3 px-6 border-b">
      <div className="flex-1">
        {/* Left side - could add logo or title here */}
      </div>
      <div className="flex items-center gap-6">
        <Link
          href="https://github.com/lightfastai/lightfast-mcp"
          target="_blank"
          className="text-sm font-medium text-white flex items-center gap-2"
        >
          <Icons.gitHub className="w-4 h-4" />
        </Link>
        <Link
          href="https://x.com/lightfastai"
          target="_blank"
          className="text-sm font-medium text-white flex items-center gap-2"
        >
          <Icons.twitter className="w-4 h-4" />
        </Link>
      </div>
    </div>
  );
}

export default async function Page(props: {
  params: Promise<{ slug?: string[] }>;
}) {
  const params = await props.params;
  const page = source.getPage(params.slug);
  if (!page) notFound();

  const MDX = page.data.body;

  return (
    <div className="flex flex-col w-full">
      <TitleBar />
      <div className="flex flex-row w-full">
        <DocsPage toc={page.data.toc} full={page.data.full}>
          <DocsTitle>{page.data.title}</DocsTitle>
          <DocsDescription>{page.data.description}</DocsDescription>
          <DocsBody>
            <MDX components={getMDXComponents()} />
          </DocsBody>
        </DocsPage>
      </div>
    </div>
  );
}

export async function generateStaticParams() {
  return source.generateParams();
}

export async function generateMetadata(props: {
  params: Promise<{ slug?: string[] }>;
}) {
  const params = await props.params;
  const page = source.getPage(params.slug);
  if (!page) notFound();

  return {
    title: page.data.title,
    description: page.data.description,
  };
}
