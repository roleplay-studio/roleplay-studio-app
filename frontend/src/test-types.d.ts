// Global ambient type declarations for test files.
//
// @testing-library/jest-dom adds custom matchers (toBeInTheDocument,
// toHaveTextContent, etc.) and the project loads them in vitest.setup.ts:
//   import '@testing-library/jest-dom/vitest';
// But the TS compiler doesn't know about the matchers at type-check
// time unless we tell it. Pulling in this .d.ts from every test file
// (or via a `types` field in tsconfig.json) makes the matchers visible
// to `svelte-check` and `tsc`.

/// <reference types="@testing-library/jest-dom" />
