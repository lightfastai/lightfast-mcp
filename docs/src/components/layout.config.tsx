import { BaseLayoutProps } from "fumadocs-ui/layouts/shared";
import { DocsLayoutProps } from "fumadocs-ui/layouts/docs";
import { Icons } from "./icons";

export const baseOptions: BaseLayoutProps = {
  nav: {
    title: <Icons.logo className="text-white w-28" />,
    url: "https://lightfast.ai",
  },
  themeSwitch: {
    enabled: false,
    mode: "light-dark-system",
  },
};

// We'll add the tree property in the layout file using the source object
export const createDocsOptions = (tree: any): DocsLayoutProps => ({
  ...baseOptions,
  tree, // Add tree from source
});
