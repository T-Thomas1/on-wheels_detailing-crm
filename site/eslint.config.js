import eslintPluginAstro from "eslint-plugin-astro";
import tseslint from "typescript-eslint";

export default tseslint.config(
  {
    ignores: ["dist/**", "node_modules/**", ".astro/**"],
  },
  ...eslintPluginAstro.configs.recommended,
  {
    rules: {
      // set:html is used intentionally for schema.org JSON-LD injection
      "astro/no-set-html-directive": "off",
    },
  },
);
