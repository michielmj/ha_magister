import { defineConfig, type Plugin } from "vite";

const banner = `/*!
 * Magister Homework planner card
 * Copyright (c) the ha_magister contributors. MIT License.
 * https://github.com/michielmj/ha_magister
 * Includes Lit (c) Google LLC, BSD-3-Clause License: https://lit.dev
 */`;

/** Put the license header in front of the minified bundle (the minifier drops banners). */
const licenseHeader: Plugin = {
  name: "magister-license-header",
  enforce: "post",
  generateBundle(_options, bundle) {
    for (const file of Object.values(bundle)) {
      if (file.type === "chunk") file.code = `${banner}\n${file.code}`;
    }
  },
};

export default defineConfig({
  plugins: [licenseHeader],
  define: { "process.env.NODE_ENV": JSON.stringify("production") },
  build: {
    target: "es2022",
    outDir: "../custom_components/magister/frontend",
    emptyOutDir: true,
    minify: true,
    sourcemap: false,
    cssCodeSplit: false,
    lib: {
      entry: "src/index.ts",
      formats: ["es"],
      fileName: () => "magister-homework-card.js",
    },
    rollupOptions: {
      output: { minify: true },
    },
  },
});
