// @ts-check
import { defineConfig } from "astro/config";
import mdx from "@astrojs/mdx";
import tailwindcss from "@tailwindcss/vite";

import { SITE_URL } from "./src/config.ts";

// TRD.md §2.1: Astro 5 in SSG mode, MDX for producer bodies, Tailwind v4 through
// the Vite plugin. There is NO tailwind.config.js and none is to be created —
// v4 is CSS-first and the theme lives in an @theme block in global.css.
export default defineConfig({
  output: "static",
  site: SITE_URL,
  integrations: [mdx()],
  vite: {
    plugins: [tailwindcss()],
  },
  build: {
    // Trailing-slash directory output, so /producer/example-wines/ is a real
    // directory with an index.html. Matches the route table in TRD.md §4.2.
    format: "directory",
  },
  trailingSlash: "always",
});
