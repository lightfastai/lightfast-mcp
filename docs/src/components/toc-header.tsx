import { Callout } from "fumadocs-ui/components/callout";
import Link from "next/link";

export function TOCHeader() {
  return (
    <Callout type="info" className="mb-4">
      Join us on{" "}
      <Link
        href="https://discord.gg/YqPDfcar2C"
        className="underline items-center gap-1 inline-flex text-blue-400"
        target="_blank"
        rel="noopener noreferrer"
      >
        Discord
      </Link>{" "}
      to chat with us and get help.
    </Callout>
  );
}
