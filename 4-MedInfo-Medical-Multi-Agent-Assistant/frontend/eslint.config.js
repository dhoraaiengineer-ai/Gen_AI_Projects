// ESLint (flat config). The UI must never inject HTML: model output is only ever inserted as text nodes.
const js = require("@eslint/js");
const globals = require("globals");

const NO_HTML_INJECTION = [
  "error",
  { selector: "AssignmentExpression[left.property.name=/^(innerHTML|outerHTML)$/]", message: "Use textContent / createTextNode, never innerHTML." },
  { selector: "CallExpression[callee.property.name='insertAdjacentHTML']", message: "Never inject HTML." },
  { selector: "CallExpression[callee.object.name='document'][callee.property.name='write']", message: "Never use document.write." },
];

module.exports = [
  js.configs.recommended,
  {
    files: ["src/**/*.js"],
    languageOptions: { ecmaVersion: 2022, sourceType: "script", globals: { ...globals.browser } },
    rules: {
      "no-restricted-syntax": NO_HTML_INJECTION,
      "no-eval": "error",
      "no-implied-eval": "error",
      "no-new-func": "error",
      "no-unused-vars": ["error", { caughtErrors: "none" }],
    },
  },
  {
    files: ["tests/**/*.js", "playwright.config.js", "eslint.config.js"],
    // Tests also contain callbacks that run inside the browser (page.evaluate / waitForFunction).
    languageOptions: { ecmaVersion: 2022, sourceType: "commonjs", globals: { ...globals.node, ...globals.browser } },
  },
];
