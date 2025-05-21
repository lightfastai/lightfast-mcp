import { BaseLayoutProps } from "fumadocs-ui/layouts/shared";
import { DocsLayoutProps } from "fumadocs-ui/layouts/docs";
import { Icons } from "./icons";

export const baseOptions: BaseLayoutProps = {
  nav: {
    title: (
      <div className="flex items-center justify-center gap-2">
        <Icons.logo className="w-4 h-4" />{" "}
        <span className="text-sm font-medium">Lightfast</span>
      </div>
    ),
  },
};

// We'll add the tree property in the layout file using the source object
export const createDocsOptions = (tree: any): DocsLayoutProps => ({
  ...baseOptions,
  tree, // Add tree from source
});
