import Link from "next/link";
import { Icons } from "./icons";

export function SiteHeader() {
  return (
    <div className="w-full flex justify-between items-center py-3 px-6 border-b">
      <div className="flex-1">
        {/* Left side - could add logo or title here */}
      </div>
      <div className="flex items-center gap-6">
        <Link
          href="https://github.com/lightfastai/lightfast-mcp"
          target="_blank"
          className="transition-transform duration-200 hover:scale-110"
        >
          <Icons.gitHub className="size-4" />
        </Link>
        <Link
          target="_blank"
          href="https://x.com/lightfastai"
          aria-label="Twitter"
          className="transition-transform duration-200 hover:scale-110"
        >
          <Icons.twitter className="size-3" />
        </Link>
        <Link
          target="_blank"
          href="https://discord.gg/YqPDfcar2C"
          aria-label="Discord"
          className="transition-transform duration-200 hover:scale-110"
        >
          <Icons.discord className="size-4" />
        </Link>
      </div>
    </div>
  );
}
