// Side-effect locale subpath imports for moment.js.
// The moment package ships JS for `moment/locale/*` but no .d.ts files
// for these subpaths, so TypeScript reports "cannot find module" for
// them. These ambient declarations tell svelte-check that the imports
// exist at runtime and have no exported values.
declare module 'moment/locale/*';
