import js from '@eslint/js';
import perfectionist from 'eslint-plugin-perfectionist';
import svelte from 'eslint-plugin-svelte';
import globals from 'globals';
import tseslint from 'typescript-eslint';

export default [
  js.configs.recommended,
  ...tseslint.configs.recommended,
  ...svelte.configs['flat/recommended'],
  perfectionist.configs['recommended-natural'],
  {
    languageOptions: {
      globals: {
        ...globals.browser,
        ...globals.node,
      },
    },
  },
  // TypeScript parser for Svelte files
  {
    files: ['**/*.svelte'],
    languageOptions: {
      parserOptions: {
        parser: tseslint.parser,
      },
    },
  },
  // Global rules
  {
    rules: {
      // no-explicit-any as warning
      '@typescript-eslint/no-explicit-any': 'warn',
      // Allow underscore-prefixed unused params (callbacks)
      '@typescript-eslint/no-unused-vars': [
        'error',
        { argsIgnorePattern: '^_', varsIgnorePattern: '^_' },
      ],
      // prefer-const for non-Svelte files
      'prefer-const': 'error',
      // {@html} is sanitized via DOMPurify
      'svelte/no-at-html-tags': 'off',
      // Unused svelte-ignore comments
      'svelte/no-unused-svelte-ignore': 'warn',
    },
  },
  // Svelte 5 runes: $props() destructuring and $state() use `let`
  // Must come AFTER global rules to override them
  {
    files: ['**/*.svelte'],
    rules: {
      'prefer-const': 'off',
    },
  },
  {
    ignores: [
      'dist/',
      'node_modules/',
      'src-tauri/',
      '*.d.ts',
      '**/*.svelte.ts',
      // Playwright trace HTML bundles — pre-compiled vendor JS, not project source
      'playwright-report/',
      // Playwright test runner output (screenshots, traces, last-run.json)
      'test-results/',
    ],
  },
];
