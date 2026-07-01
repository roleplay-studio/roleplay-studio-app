// Safelist for @iconify/tailwind4 scanner
// Only icons used dynamically in Svelte components (template literals)
// Static icon-[tabler--*] classes are auto-detected by the scanner

const _safelist = [
  // Sidebar navigation
  'icon-[tabler--apps]',
  'icon-[tabler--message-circle]',
  'icon-[tabler--robot]',
  'icon-[tabler--users]',
  'icon-[tabler--books]',
  'icon-[tabler--settings]',
  // UI components (dynamic {icon} prop)
  'icon-[tabler--chevron-down]',
  'icon-[tabler--x]',
  'icon-[tabler--check]',
  'icon-[tabler--alert-triangle]',
  'icon-[tabler--alert-circle]',
  'icon-[tabler--background]',
];

export default _safelist;
