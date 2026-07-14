// _data/catalog.ts — static registry of all catalog entries.
// Each entry holds its demo via a dynamic import for lazy loading.
//
// Adding a new block: append a CatalogEntry to CATALOG with a demo
// arrow function pointing at _demos/<Name>Demo.svelte. The page shell
// picks it up automatically.

import type { Component } from 'svelte';

export interface CatalogEntry {
  /** Dynamic import of the demo wrapper. Returned component is rendered
   *  inside the ComponentFrame. Used for lazy-loading heavy demos. */
  demo: () => Promise<{ default: Component }>;
  description: string;
  group: CatalogGroup;
  /** When true, the ComponentFrame renders a side-by-side "Legacy (Raycast)"
   *  column next to the component column. Only set for the 5 atomic blocks
   *  that have an inline `.ray-btn`/`.ray-card` legacy version. */
  hasLegacyDemo?: boolean;
  /** Required for atomic/composite. Foundations omit props (they're static). */
  props?: CatalogProp[];
  /** Stable identifier, used for in-page anchors (#slug). Must be unique. */
  slug: string;
  /** Code snippets shown below the props table. */
  snippets: CatalogSnippet[];
  /** Path to the source file, relative to the repo root. Used for the
   *  "View source" link (deferred) and the catalog snapshot test. */
  source: string;
  title: string;
}

export type CatalogGroup = 'atomic' | 'composite' | 'foundations';

export interface CatalogProp {
  /** Default value as a string for display purposes. Omit for required-only. */
  default?: string;
  description: string;
  name: string;
  required: boolean;
  /** TypeScript-style type name (e.g. "string", "'sm' | 'md'", "Bot"). */
  type: string;
}

export interface CatalogSnippet {
  code: string;
  lang: 'bash' | 'svelte' | 'ts';
  title: string;
}

// ════════════════════════════════════════════════════════════════
// FOUNDATIONS — color tokens, typography, spacing. Static demos that
// read directly from CSS custom properties; no real components.
// ════════════════════════════════════════════════════════════════

const FoundationsPalette = (): Promise<{ default: Component }> =>
  import('../_demos/FoundationsPaletteDemo.svelte');
const FoundationsTypography = (): Promise<{ default: Component }> =>
  import('../_demos/FoundationsTypographyDemo.svelte');
const FoundationsSpacing = (): Promise<{ default: Component }> =>
  import('../_demos/FoundationsSpacingDemo.svelte');
const ButtonsDemo = (): Promise<{ default: Component }> => import('../_demos/ButtonsDemo.svelte');
const InputsDemo = (): Promise<{ default: Component }> => import('../_demos/InputsDemo.svelte');
const TextareasDemo = (): Promise<{ default: Component }> =>
  import('../_demos/TextareasDemo.svelte');
const SelectsDemo = (): Promise<{ default: Component }> => import('../_demos/SelectsDemo.svelte');
const ToggleDemo = (): Promise<{ default: Component }> => import('../_demos/ToggleDemo.svelte');
const FormFieldDemo = (): Promise<{ default: Component }> =>
  import('../_demos/FormFieldDemo.svelte');
const GeneratedAvatarsDemo = (): Promise<{ default: Component }> =>
  import('../_demos/GeneratedAvatarsDemo.svelte');
const AlertsDemo = (): Promise<{ default: Component }> => import('../_demos/AlertsDemo.svelte');
const BadgesDemo = (): Promise<{ default: Component }> => import('../_demos/BadgesDemo.svelte');
const TooltipsDemo = (): Promise<{ default: Component }> => import('../_demos/TooltipsDemo.svelte');
const LoadingDemo = (): Promise<{ default: Component }> => import('../_demos/LoadingDemo.svelte');
const CardsDemo = (): Promise<{ default: Component }> => import('../_demos/CardsDemo.svelte');
const ModalsDemo = (): Promise<{ default: Component }> => import('../_demos/ModalsDemo.svelte');
const TabsDemo = (): Promise<{ default: Component }> => import('../_demos/TabsDemo.svelte');
const DropdownsDemo = (): Promise<{ default: Component }> =>
  import('../_demos/DropdownsDemo.svelte');
const NotificationModalsDemo = (): Promise<{ default: Component }> =>
  import('../_demos/NotificationModalsDemo.svelte');
const ActionButtonsDemo = (): Promise<{ default: Component }> =>
  import('../_demos/ActionButtonsDemo.svelte');
const ChatBubblesDemo = (): Promise<{ default: Component }> =>
  import('../_demos/ChatBubblesDemo.svelte');
const GameStatsDemo = (): Promise<{ default: Component }> =>
  import('../_demos/GameStatsDemo.svelte');
const CategoryPickerDemo = (): Promise<{ default: Component }> =>
  import('../_demos/CategoryPickerDemo.svelte');
const MarkdownRenderersDemo = (): Promise<{ default: Component }> =>
  import('../_demos/MarkdownRenderersDemo.svelte');
const FileAttachmentsDemo = (): Promise<{ default: Component }> =>
  import('../_demos/FileAttachmentsDemo.svelte');
const BotCardsDemo = (): Promise<{ default: Component }> => import('../_demos/BotCardsDemo.svelte');
const BackendErrorScreensDemo = (): Promise<{ default: Component }> =>
  import('../_demos/BackendErrorScreensDemo.svelte');
const DeleteConfirmModalsDemo = (): Promise<{ default: Component }> =>
  import('../_demos/DeleteConfirmModalsDemo.svelte');
const ChatHeadersDemo = (): Promise<{ default: Component }> =>
  import('../_demos/ChatHeadersDemo.svelte');
const ChatInputsDemo = (): Promise<{ default: Component }> =>
  import('../_demos/ChatInputsDemo.svelte');
const AvatarUploadsDemo = (): Promise<{ default: Component }> =>
  import('../_demos/AvatarUploadsDemo.svelte');
const EditMessageModalsDemo = (): Promise<{ default: Component }> =>
  import('../_demos/EditMessageModalsDemo.svelte');
const SidebarsDemo = (): Promise<{ default: Component }> => import('../_demos/SidebarsDemo.svelte');
const MessageContextMenusDemo = (): Promise<{ default: Component }> =>
  import('../_demos/MessageContextMenusDemo.svelte');
const MessageBubblesDemo = (): Promise<{ default: Component }> =>
  import('../_demos/MessageBubblesDemo.svelte');
const RecentChatsDemo = (): Promise<{ default: Component }> =>
  import('../_demos/RecentChatsDemo.svelte');
const ThreadDrawersDemo = (): Promise<{ default: Component }> =>
  import('../_demos/ThreadDrawersDemo.svelte');
const PersonaSelectModalsDemo = (): Promise<{ default: Component }> =>
  import('../_demos/PersonaSelectModalsDemo.svelte');
const LLMDebugModalsDemo = (): Promise<{ default: Component }> =>
  import('../_demos/LLMDebugModalsDemo.svelte');
const GlobalDropZonesDemo = (): Promise<{ default: Component }> =>
  import('../_demos/GlobalDropZonesDemo.svelte');
const NavItemsDemo = (): Promise<{ default: Component }> => import('../_demos/NavItemsDemo.svelte');
const ThreadItemsDemo = (): Promise<{ default: Component }> =>
  import('../_demos/ThreadItemsDemo.svelte');
const ThreadGroupsDemo = (): Promise<{ default: Component }> =>
  import('../_demos/ThreadGroupsDemo.svelte');
const TTSButtonDemo = (): Promise<{ default: Component }> =>
  import('../_demos/TTSButtonDemo.svelte');

export const CATALOG: CatalogEntry[] = [
  {
    demo: FoundationsPalette,
    description: 'Surface / neko / roleplay-studio palette in light + dark mode.',
    group: 'foundations',
    slug: 'foundations-colors',
    snippets: [],
    source: 'frontend/src/app.css',
    title: 'Colors',
  },
  {
    demo: FoundationsTypography,
    description: 'Maple Mono font family with weight scale and size scale.',
    group: 'foundations',
    slug: 'foundations-typography',
    snippets: [],
    source: 'frontend/src/app.css',
    title: 'Typography',
  },
  {
    demo: FoundationsSpacing,
    description: 'Spacing scale (4/8/12/16/20/24/32/40/48/64) and border-radius scale.',
    group: 'foundations',
    slug: 'foundations-spacing',
    snippets: [],
    source: 'frontend/src/app.css',
    title: 'Spacing & Radius',
  },
  {
    demo: ButtonsDemo,
    description: 'Raycast-style button with pill shape, opacity hover, and 10 variants.',
    group: 'atomic',
    hasLegacyDemo: true,
    props: [
      { description: 'Button content.', name: 'children', required: false, type: 'Snippet' },
      {
        default: '"primary"',
        description:
          'Visual style. One of: primary, secondary, outline, ghost, soft, text, pill, accent, info, success, warning, error.',
        name: 'variant',
        required: false,
        type: 'ButtonVariant',
      },
      {
        default: '"md"',
        description: 'Size preset.',
        name: 'size',
        required: false,
        type: "'sm' | 'md' | 'lg' | 'xl'",
      },
      {
        default: 'false',
        description: 'Disable interaction.',
        name: 'disabled',
        required: false,
        type: 'boolean',
      },
      {
        default: 'false',
        description: 'Show spinner, block interaction.',
        name: 'loading',
        required: false,
        type: 'boolean',
      },
      {
        description: 'Icon component (Lucide) or string key from iconMap.',
        name: 'icon',
        required: false,
        type: 'Component | string',
      },
      {
        description: 'If set, renders as <a> instead of <button>.',
        name: 'href',
        required: false,
        type: 'string',
      },
      {
        description: 'Click handler.',
        name: 'onclick',
        required: false,
        type: '(e: MouseEvent) => void',
      },
      {
        default: '"button"',
        description: 'HTML button type.',
        name: 'type',
        required: false,
        type: "'button' | 'submit' | 'reset'",
      },
    ],
    slug: 'button',
    snippets: [
      {
        code: `<Button variant="primary" onclick={handleSave}>Save</Button>`,
        lang: 'svelte',
        title: 'Basic usage',
      },
      {
        code: `<Button variant="primary" icon={Plus} onclick={add}>Add bot</Button>`,
        lang: 'svelte',
        title: 'With icon',
      },
      {
        code: `<Button variant="ghost" href="/dashboard">Back</Button>`,
        lang: 'svelte',
        title: 'As link',
      },
    ],
    source: 'frontend/src/lib/ui/Button.svelte',
    title: 'Button',
  },
  {
    demo: InputsDemo,
    description:
      'Text input with label, error state, and focus ring. Can render as <textarea> when textarea=true.',
    group: 'atomic',
    hasLegacyDemo: true,
    props: [
      {
        default: '""',
        description: 'Bound input value ($bindable).',
        name: 'value',
        required: false,
        type: 'string',
      },
      {
        default: '"text"',
        description: 'HTML input type.',
        name: 'type',
        required: false,
        type: 'string',
      },
      {
        description: 'Label rendered above the input.',
        name: 'label',
        required: false,
        type: 'string',
      },
      { description: 'Placeholder text.', name: 'placeholder', required: false, type: 'string' },
      {
        description: 'Error message; also styles the field red.',
        name: 'error',
        required: false,
        type: 'string',
      },
      {
        default: 'false',
        description: 'Disable input.',
        name: 'disabled',
        required: false,
        type: 'boolean',
      },
      {
        default: '3',
        description: 'When textarea=true, sets initial rows.',
        name: 'rows',
        required: false,
        type: 'number',
      },
      {
        default: 'false',
        description: 'Render as <textarea> instead of <input>.',
        name: 'textarea',
        required: false,
        type: 'boolean',
      },
      {
        description: 'Input event handler.',
        name: 'oninput',
        required: false,
        type: '(e: Event) => void',
      },
    ],
    slug: 'input',
    snippets: [
      {
        code: `<Input bind:value={name} label="Bot name" placeholder="Enter name..." />`,
        lang: 'svelte',
        title: 'Basic',
      },
      {
        code: `<Input bind:value={apiKey} error="API key is required" />`,
        lang: 'svelte',
        title: 'With error',
      },
    ],
    source: 'frontend/src/lib/ui/Input.svelte',
    title: 'Input',
  },
  {
    demo: NavItemsDemo,
    description:
      'Single nav row used by Sidebar: icon + label, with active/collapsed states. Domain-agnostic — takes pre-translated label and SVG icon.',
    group: 'atomic',
    props: [
      {
        description: 'SVG markup (use {@html} to render).',
        name: 'icon',
        required: true,
        type: 'string',
      },
      {
        description: 'Already-translated label text.',
        name: 'label',
        required: true,
        type: 'string',
      },
      {
        default: 'false',
        description: 'Highlight as the current page.',
        name: 'active',
        required: false,
        type: 'boolean',
      },
      {
        default: 'false',
        description: 'Hide the label (icon-only mode for collapsed sidebar).',
        name: 'collapsed',
        required: false,
        type: 'boolean',
      },
      { description: 'Click handler.', name: 'onclick', required: false, type: '() => void' },
    ],
    slug: 'nav-item',
    snippets: [
      {
        code: `<NavItem\n  icon={icons.chat}\n  label={t('nav.chats', lang)}\n  active={currentRoute === '/chats'}\n  collapsed={!$sidebarOpen}\n  onclick={() => goto('/chats')}\n/>`,
        lang: 'svelte',
        title: 'Sidebar nav row',
      },
    ],
    source: 'frontend/src/lib/ui/NavItem.svelte',
    title: 'NavItem',
  },
  {
    demo: ThreadItemsDemo,
    description:
      'Single thread row used by ThreadDrawer: name + persona + time, with selected/renaming states. Renaming delegates to parent (input + bind:renameValue).',
    group: 'atomic',
    props: [
      {
        description: 'The thread to render (id, name, persona_name, created_at, etc.).',
        name: 'thread',
        required: true,
        type: 'Thread',
      },
      {
        description: 'Pre-formatted relative time string (e.g. "5m", "2h", "1d").',
        name: 'timeLabel',
        required: true,
        type: 'string',
      },
      {
        default: 'false',
        description: 'Highlight as the currently-selected thread.',
        name: 'selected',
        required: false,
        type: 'boolean',
      },
      {
        default: 'false',
        description: 'Show the inline rename input instead of the name.',
        name: 'renaming',
        required: false,
        type: 'boolean',
      },
      {
        default: '""',
        description: 'Bound rename input value ($bindable).',
        name: 'renameValue',
        required: false,
        type: 'string',
      },
      {
        description: 'Called with the thread id when the row is clicked.',
        name: 'onselect',
        required: false,
        type: '(id: number) => void',
      },
      {
        description:
          'Called with the mouse event and id on right-click (parent shows context menu).',
        name: 'oncontextmenu',
        required: false,
        type: '(e: MouseEvent, id: number) => void',
      },
      {
        description: 'Called when the dots button is clicked (stops propagation).',
        name: 'ondotsclick',
        required: false,
        type: '(e: MouseEvent, id: number) => void',
      },
      {
        description: 'Called on Enter or blur of the rename input.',
        name: 'onrename',
        required: false,
        type: '(id: number, name: string) => void',
      },
      {
        description: 'Called on Escape of the rename input.',
        name: 'oncancelrename',
        required: false,
        type: '(id: number) => void',
      },
    ],
    slug: 'thread-item',
    snippets: [
      {
        code: `<ThreadItem\n  {thread}\n  timeLabel={formatRelativeTime(thread.created_at, lang)}\n  selected={selectedThreadId === thread.id}\n  renaming={renamingThreadId === thread.id}\n  bind:renameValue\n  onselect={selectThread}\n  oncontextmenu={handleContextMenu}\n  ondotsclick={handleContextMenu}\n  onrename={commitRename}\n  oncancelrename={cancelRename}\n/>`,
        lang: 'svelte',
        title: 'Inside ThreadDrawer',
      },
    ],
    source: 'frontend/src/lib/ui/ThreadItem.svelte',
    title: 'ThreadItem',
  },
  {
    demo: ThreadGroupsDemo,
    description:
      'Sticky collapsible bot-section header for the cross-bot recent-chats listing. Owns no collapse state — parent passes `isCollapsed` + `onToggle` (RecentChats persists via localStorage).',
    group: 'atomic',
    props: [
      {
        description:
          'ISO timestamp of the most recent thread in this group — used for the "active N мин назад" subtitle.',
        name: 'lastActivityLabel',
        required: true,
        type: 'string',
      },
      {
        description:
          "Initial of the bot's name, used as the avatar placeholder when bot_avatar_path is null.",
        name: 'bot_name',
        required: true,
        type: 'string',
      },
      {
        description:
          'Array of category tags — only the first one is rendered as a pill.',
        name: 'bot_categories',
        required: false,
        type: 'string[]',
      },
      {
        description: 'Bot avatar URL or null (renders a styled initial).',
        name: 'bot_avatar_path',
        required: true,
        type: 'string | null',
      },
      {
        description: 'Parent-controlled collapse state.',
        name: 'isCollapsed',
        required: true,
        type: 'boolean',
      },
      {
        description:
          'Toggle handler — typically wires to localStorage persistence (see RecentChats).',
        name: 'onToggle',
        required: true,
        type: '() => void',
      },
      {
        description: 'Number of threads in the group — rendered as a pill.',
        name: 'threadCount',
        required: true,
        type: 'number',
      },
    ],
    snippets: [
      {
        code: `<ThreadGroup
  bot_name={group.bot_name}
  bot_avatar_path={thumbUrl(group.bot_avatar_path, 200)}
  bot_categories={group.bot_categories}
  threadCount={group.threads.length}
  lastActivityLabel={formatTime(group.lastActivityAt)}
  isCollapsed={collapsedBots.has(group.bot_id)}
  onToggle={() => toggleCollapsed(group.bot_id)}
>
  {#each group.threads as thread (thread.thread_id)}
    <RecentRow {thread} />
  {/each}
</ThreadGroup>`,
        lang: 'svelte',
        title: 'RecentChats usage',
      },
    ],
    source: 'frontend/src/lib/ui/ThreadGroup.svelte',
    title: 'ThreadGroup',
  },
  {
    demo: TextareasDemo,
    description:
      'Auto-growing textarea for multi-line input. (Wrapper around Input with textarea=true.)',
    group: 'atomic',
    props: [
      {
        default: '""',
        description: 'Bound textarea value ($bindable).',
        name: 'value',
        required: false,
        type: 'string',
      },
      { description: 'Placeholder text.', name: 'placeholder', required: false, type: 'string' },
      {
        default: 'false',
        description: 'Disable textarea.',
        name: 'disabled',
        required: false,
        type: 'boolean',
      },
      {
        default: '3',
        description: 'Initial visible row count.',
        name: 'rows',
        required: false,
        type: 'number',
      },
      {
        description: 'Input event handler.',
        name: 'oninput',
        required: false,
        type: '(e: Event) => void',
      },
    ],
    slug: 'textarea',
    snippets: [
      {
        code: `<Textarea bind:value={bio} placeholder="Tell me about yourself..." />`,
        lang: 'svelte',
        title: 'Basic',
      },
    ],
    source: 'frontend/src/lib/ui/Textarea.svelte',
    title: 'Textarea',
  },
  {
    demo: SelectsDemo,
    description: 'Dropdown selector with custom styling and placeholder support.',
    group: 'atomic',
    props: [
      { description: 'Currently selected value.', name: 'value', required: false, type: 'string' },
      {
        description: 'Available options.',
        name: 'options',
        required: true,
        type: '{ label: string; value: string }[]',
      },
      {
        description: 'Shown when no value is selected.',
        name: 'placeholder',
        required: false,
        type: 'string',
      },
      {
        default: 'false',
        description: 'Disable select.',
        name: 'disabled',
        required: false,
        type: 'boolean',
      },
    ],
    slug: 'select',
    snippets: [
      {
        code: `<Select bind:value={type} options={[{label: 'RP', value: 'rp'}, {label: 'Assistant', value: 'assistant'}]} />`,
        lang: 'svelte',
        title: 'Basic',
      },
    ],
    source: 'frontend/src/lib/ui/Select.svelte',
    title: 'Select',
  },
  {
    demo: ToggleDemo,
    description: 'On/off switch with smooth animation.',
    group: 'atomic',
    props: [
      {
        default: 'false',
        description: 'Toggle state.',
        name: 'checked',
        required: false,
        type: 'boolean',
      },
      {
        default: 'false',
        description: 'Disable toggle.',
        name: 'disabled',
        required: false,
        type: 'boolean',
      },
      {
        description: 'Change handler.',
        name: 'onchange',
        required: false,
        type: '(e: Event) => void',
      },
    ],
    slug: 'toggle',
    snippets: [{ code: `<Toggle bind:checked={enabled} />`, lang: 'svelte', title: 'Basic' }],
    source: 'frontend/src/lib/ui/Toggle.svelte',
    title: 'Toggle',
  },
  {
    demo: FormFieldDemo,
    description: 'Wrapper that adds a label, hint, and error text around any form control.',
    group: 'atomic',
    props: [
      { description: 'Field label.', name: 'label', required: false, type: 'string' },
      { description: 'Hint text below the field.', name: 'hint', required: false, type: 'string' },
      {
        description: 'Error text; styles the field red.',
        name: 'error',
        required: false,
        type: 'string',
      },
      {
        default: 'false',
        description: 'Marks the label with a star.',
        name: 'required',
        required: false,
        type: 'boolean',
      },
      {
        description: 'The form control itself.',
        name: 'children',
        required: true,
        type: 'Snippet',
      },
    ],
    slug: 'form-field',
    snippets: [
      {
        code: `<FormField label="API key" hint="Stored locally, never sent to server"><Input bind:value={key} type="password" /></FormField>`,
        lang: 'svelte',
        title: 'Wrapping Input',
      },
    ],
    source: 'frontend/src/lib/ui/FormField.svelte',
    title: 'FormField',
  },
  {
    demo: GeneratedAvatarsDemo,
    description:
      'Deterministic placeholder avatar for bots/personas that haven’t uploaded an image. Hashes the name into an HSL gradient + one of 8 kaomoji-style face SVGs. Same name → same avatar, always.',
    group: 'atomic',
    props: [
      {
        description: 'Name to hash. Empty falls back to "?".',
        name: 'name',
        required: false,
        type: 'string',
      },
      {
        default: '40',
        description: 'Diameter in pixels.',
        name: 'size',
        required: false,
        type: 'number',
      },
      {
        default: '"circle"',
        description: 'circle (50% radius), rounded (22% radius), or square (6px).',
        name: 'shape',
        required: false,
        type: '"circle" | "rounded" | "square"',
      },
      {
        description: 'Accessible alt text (defaults to "Avatar for {name}").',
        name: 'alt',
        required: false,
        type: 'string',
      },
    ],
    slug: 'generated-avatar',
    snippets: [
      {
        code: `<GeneratedAvatar name={bot.name} size={36} />\n<GeneratedAvatar name={persona.name} size={48} shape="rounded" />`,
        lang: 'svelte',
        title: 'Basic',
      },
      {
        code: `// In MessageBubble.svelte\n{#if botAvatarPath}\n  <img src={thumbUrl(botAvatarPath, 50)} alt={botName} class="mb-avatar-img" />\n{:else}\n  <GeneratedAvatar name={botName} size={36} />\n{/if}`,
        lang: 'svelte',
        title: 'In MessageBubble',
      },
    ],
    source: 'frontend/src/lib/ui/GeneratedAvatar.svelte',
    title: 'GeneratedAvatar',
  },
  {
    demo: AlertsDemo,
    description: 'Inline notification box for info/success/warning/error/primary feedback.',
    group: 'atomic',
    props: [
      { description: 'Alert body.', name: 'children', required: true, type: 'Snippet' },
      {
        default: '"info"',
        description: 'Semantic style.',
        name: 'variant',
        required: false,
        type: "'info' | 'success' | 'warning' | 'error' | 'primary'",
      },
      {
        description: 'Icon name from iconMap (Lucide key).',
        name: 'icon',
        required: false,
        type: 'string',
      },
      {
        default: 'false',
        description: 'Show a close button and hide on click.',
        name: 'dismissible',
        required: false,
        type: 'boolean',
      },
      {
        description: 'Callback fired after the alert is closed.',
        name: 'onclose',
        required: false,
        type: '() => void',
      },
    ],
    slug: 'alert',
    snippets: [
      {
        code: `<Alert variant="success" icon="circle-check">Saved to library</Alert>`,
        lang: 'svelte',
        title: 'Basic',
      },
      {
        code: `<Alert variant="warning" dismissible onclose={ack}>Careful!</Alert>`,
        lang: 'svelte',
        title: 'Dismissible',
      },
    ],
    source: 'frontend/src/lib/ui/Alert.svelte',
    title: 'Alert',
  },
  {
    demo: BadgesDemo,
    description: 'Compact pill label for tags, counts, and status indicators.',
    group: 'atomic',
    props: [
      { description: 'Badge content.', name: 'children', required: true, type: 'Snippet' },
      {
        default: '"primary"',
        description: 'Color variant.',
        name: 'variant',
        required: false,
        type: "'primary' | 'success' | 'warning' | 'error' | 'info' | 'accent' | 'soft' | 'secondary' | 'outline'",
      },
      {
        default: '"md"',
        description: 'Size preset.',
        name: 'size',
        required: false,
        type: "'sm' | 'md' | 'lg'",
      },
    ],
    slug: 'badge',
    snippets: [
      { code: `<Badge variant="primary">New</Badge>`, lang: 'svelte', title: 'Basic' },
      {
        code: `<Badge variant="success" size="sm">Saved</Badge>`,
        lang: 'svelte',
        title: 'Sized',
      },
    ],
    source: 'frontend/src/lib/ui/Badge.svelte',
    title: 'Badge',
  },
  {
    demo: TooltipsDemo,
    description: 'CSS-only hover tooltip with four positions and three color variants.',
    group: 'atomic',
    props: [
      {
        description: 'The trigger element.',
        name: 'children',
        required: true,
        type: 'Snippet',
      },
      {
        description: 'Tooltip body text.',
        name: 'text',
        required: true,
        type: 'string',
      },
      {
        default: '"top"',
        description: 'Where the tip appears relative to the trigger.',
        name: 'position',
        required: false,
        type: "'top' | 'bottom' | 'left' | 'right'",
      },
      {
        default: '"default"',
        description: 'Color treatment.',
        name: 'variant',
        required: false,
        type: "'default' | 'info' | 'error'",
      },
    ],
    slug: 'tooltip',
    snippets: [
      {
        code: `<Tooltip text="Saved to library" position="top"><Button>Save</Button></Tooltip>`,
        lang: 'svelte',
        title: 'Basic',
      },
      {
        code: `<Tooltip text="Connection failed" variant="error" position="right"><Button variant="error">Retry</Button></Tooltip>`,
        lang: 'svelte',
        title: 'Error variant',
      },
    ],
    source: 'frontend/src/lib/ui/Tooltip.svelte',
    title: 'Tooltip',
  },
  {
    demo: LoadingDemo,
    description: 'Spinner / dots indicator with five sizes and optional caption text.',
    group: 'atomic',
    props: [
      {
        default: '"spinner"',
        description: 'Animation type.',
        name: 'type',
        required: false,
        type: "'spinner' | 'dots'",
      },
      {
        default: '"md"',
        description: 'Size preset.',
        name: 'size',
        required: false,
        type: "'xs' | 'sm' | 'md' | 'lg' | 'xl'",
      },
      {
        description: 'Caption shown below the indicator.',
        name: 'text',
        required: false,
        type: 'string',
      },
    ],
    slug: 'loading',
    snippets: [
      { code: `<Loading type="spinner" />`, lang: 'svelte', title: 'Basic' },
      {
        code: `<Loading type="spinner" text="Loading bots..." />`,
        lang: 'svelte',
        title: 'With caption',
      },
    ],
    source: 'frontend/src/lib/ui/Loading.svelte',
    title: 'Loading',
  },
  {
    demo: CardsDemo,
    description: 'Raycast-style card with optional header / footer snippets and hover state.',
    group: 'atomic',
    props: [
      { description: 'Card body.', name: 'children', required: true, type: 'Snippet' },
      {
        description: 'Header content (rendered above body with a divider).',
        name: 'header',
        required: false,
        type: 'Snippet',
      },
      {
        description: 'Footer content (rendered below body with a divider).',
        name: 'footer',
        required: false,
        type: 'Snippet',
      },
      {
        default: 'true',
        description: 'Add 20px padding to the card body.',
        name: 'padding',
        required: false,
        type: 'boolean',
      },
      {
        default: 'true',
        description: 'Show a 1px subtle border.',
        name: 'bordered',
        required: false,
        type: 'boolean',
      },
      {
        default: 'false',
        description: 'Animate border + shadow on hover.',
        name: 'hover',
        required: false,
        type: 'boolean',
      },
    ],
    slug: 'card',
    snippets: [
      {
        code: `<Card><p>Simple card with body content.</p></Card>`,
        lang: 'svelte',
        title: 'Basic',
      },
      {
        code: `<Card hover>\n  {#snippet header()}Title{/snippet}\n  Body content\n  {#snippet footer()}<small>Footer</small>{/snippet}\n</Card>`,
        lang: 'svelte',
        title: 'With header/footer',
      },
    ],
    source: 'frontend/src/lib/ui/Card.svelte',
    title: 'Card',
  },
  {
    demo: ModalsDemo,
    description: 'Centered dialog with backdrop blur, escape-to-close, and four size presets.',
    group: 'atomic',
    props: [
      {
        description: 'Open state ($bindable).',
        name: 'open',
        required: false,
        type: 'boolean',
      },
      { description: 'Header title.', name: 'title', required: false, type: 'string' },
      {
        default: '"md"',
        description: 'Width preset.',
        name: 'size',
        required: false,
        type: "'sm' | 'md' | 'lg' | 'xl'",
      },
      { description: 'Body content.', name: 'children', required: true, type: 'Snippet' },
      {
        description: 'Footer content (typically action buttons).',
        name: 'footer',
        required: false,
        type: 'Snippet',
      },
      {
        description: 'Called when modal closes (via X, Esc, or backdrop click).',
        name: 'onclose',
        required: false,
        type: '() => void',
      },
    ],
    slug: 'modal',
    snippets: [
      {
        code: `<Modal bind:open={show} size="md" title="Confirm">Are you sure?</Modal>`,
        lang: 'svelte',
        title: 'Basic',
      },
      {
        code: `<Modal bind:open={show} title="Delete">\n  This action cannot be undone.\n  {#snippet footer()}\n    <Button onclick={cancel}>Cancel</Button>\n    <Button variant="error" onclick={confirm}>Delete</Button>\n  {/snippet}\n</Modal>`,
        lang: 'svelte',
        title: 'With footer actions',
      },
    ],
    source: 'frontend/src/lib/ui/Modal.svelte',
    title: 'Modal',
  },
  {
    demo: TabsDemo,
    description: 'Segmented tab control with active-state pill and optional icons.',
    group: 'atomic',
    props: [
      {
        description: 'Currently active tab id.',
        name: 'activeTab',
        required: true,
        type: 'string',
      },
      {
        description: 'Tab definitions.',
        name: 'tabs',
        required: true,
        type: '{ id: string; label: string; icon?: string }[]',
      },
      {
        description: 'Called when a tab is clicked.',
        name: 'onchange',
        required: false,
        type: '(id: string) => void',
      },
    ],
    slug: 'tabs',
    snippets: [
      {
        code: `<Tabs\n  activeTab={active}\n  onchange={(id) => (active = id)}\n  tabs={[{id: 'a', label: 'A'}, {id: 'b', label: 'B'}]}\n/>`,
        lang: 'svelte',
        title: 'Basic',
      },
    ],
    source: 'frontend/src/lib/ui/Tabs.svelte',
    title: 'Tabs',
  },
  {
    demo: DropdownsDemo,
    description: 'Popover menu with trigger button, items, icons, and dividers.',
    group: 'atomic',
    props: [
      {
        description: 'Trigger button label.',
        name: 'label',
        required: false,
        type: 'string',
      },
      {
        description: 'Menu items.',
        name: 'items',
        required: true,
        type: '{ label: string; value: string; icon?: string; divider?: boolean }[]',
      },
      {
        default: '"start"',
        description: 'Panel alignment relative to trigger.',
        name: 'align',
        required: false,
        type: "'start' | 'end'",
      },
      {
        description: 'Called when an item is selected.',
        name: 'onselect',
        required: false,
        type: '(value: string) => void',
      },
    ],
    slug: 'dropdown',
    snippets: [
      {
        code: `<Dropdown\n  label="Actions"\n  items={[\n    {label: 'Edit', value: 'edit'},\n    {label: 'Delete', value: 'delete'}\n  ]}\n  onselect={handle}\n/>`,
        lang: 'svelte',
        title: 'Basic',
      },
      {
        code: `<Dropdown\n  label="Account"\n  items={[\n    {icon: 'edit', label: 'Profile', value: 'profile'},\n    {divider: true, label: '', value: 'd'},\n    {icon: 'trash', label: 'Sign out', value: 'signout'}\n  ]}\n/>`,
        lang: 'svelte',
        title: 'With icons and dividers',
      },
    ],
    source: 'frontend/src/lib/ui/Dropdown.svelte',
    title: 'Dropdown',
  },
  {
    demo: NotificationModalsDemo,
    description:
      'Pre-styled modal wrapper with centered colored icon, message, and OK button. 6 semantic variants (success / info / warning / error / celebration / help) — each picks a different inline SVG icon over a pastel circle background.',
    group: 'atomic',
    props: [
      {
        description: 'Open state.',
        name: 'show',
        required: false,
        type: 'boolean',
      },
      { description: 'Body text.', name: 'message', required: false, type: 'string' },
      {
        description: 'Called when OK is clicked or modal closes.',
        name: 'onclose',
        required: false,
        type: '() => void',
      },
      {
        default: '"info"',
        description:
          'Visual variant. Picks the icon (checkmark, info-i, warning-triangle, X, party-popper, question-mark) and the pastel circle color (green / blue / amber / red / purple / teal).',
        name: 'variant',
        required: false,
        type: '"success" | "info" | "warning" | "error" | "celebration" | "help"',
      },
    ],
    slug: 'notification-modal',
    snippets: [
      {
        code: `<NotificationModal show={open} message="Saved!" onclose={() => (open = false)} />`,
        lang: 'svelte',
        title: 'Basic (defaults to info)',
      },
      {
        code: `<NotificationModal show={errOpen} variant="error" message="Could not save." onclose={() => (errOpen = false)} />\n<NotificationModal show={winOpen} variant="celebration" message="1000 messages!" onclose={() => (winOpen = false)} />`,
        lang: 'svelte',
        title: 'With variant',
      },
    ],
    source: 'frontend/src/lib/ui/NotificationModal.svelte',
    title: 'NotificationModal',
  },
  {
    demo: ActionButtonsDemo,
    description:
      'Violet pill button group for in-message quick actions (RP game choices, command suggestions).',
    group: 'atomic',
    props: [
      {
        description: 'Action labels rendered as buttons.',
        name: 'actions',
        required: false,
        type: 'string[]',
      },
      {
        description: 'Called with the clicked action text.',
        name: 'onaction',
        required: false,
        type: '(text: string) => void',
      },
    ],
    slug: 'action-buttons',
    snippets: [
      {
        code: `<ActionButtons\n  actions={['Continue', 'Roll dice', 'Inventory']}\n  onaction={handle}\n/>`,
        lang: 'svelte',
        title: 'Basic',
      },
    ],
    source: 'frontend/src/lib/ui/ActionButtons.svelte',
    title: 'ActionButtons',
  },
  {
    demo: ChatBubblesDemo,
    description:
      'FlyonUI chat bubble with avatar, role-based name (user/assistant/system), and HTML body.',
    group: 'atomic',
    props: [
      {
        description: 'Raw HTML body content.',
        name: 'content',
        required: false,
        type: 'string',
      },
      {
        default: '"user"',
        description: 'Speaker role — controls avatar color and name.',
        name: 'role',
        required: false,
        type: "'user' | 'assistant' | 'system'",
      },
      {
        description: 'Optional timestamp label.',
        name: 'time',
        required: false,
        type: 'string',
      },
    ],
    slug: 'chat-bubble',
    snippets: [
      {
        code: `<ChatBubble role="user" content="<p>Hello!</p>" time="14:32" />`,
        lang: 'svelte',
        title: 'Basic',
      },
      {
        code: `<ChatBubble role="assistant" content={markdownToHtml(msg)} time={ts} />`,
        lang: 'svelte',
        title: 'With markdown',
      },
    ],
    source: 'frontend/src/lib/ui/ChatBubble.svelte',
    title: 'ChatBubble',
  },
  {
    demo: GameStatsDemo,
    description: 'Grid of stat bars (numeric) and badges (string) for game/RP messages.',
    group: 'atomic',
    props: [
      {
        description:
          'Stat entries; numeric values get a progress bar, strings get a colored badge.',
        name: 'entries',
        required: false,
        type: 'MetadataEntry[]',
      },
    ],
    slug: 'game-stats',
    snippets: [
      {
        code: `<GameStats\n  entries={[\n    {key: 'hp', displayKey: 'HP', isNumeric: true, value: 87},\n    {key: 'mp', displayKey: 'MP', isNumeric: true, value: 42}\n  ]}\n/>`,
        lang: 'svelte',
        title: 'Numeric stats',
      },
    ],
    source: 'frontend/src/lib/ui/GameStats.svelte',
    title: 'GameStats',
  },
  {
    demo: CategoryPickerDemo,
    description: 'Multi-select pill grid for picking bot categories. Two-way bound selected array.',
    group: 'composite',
    props: [
      {
        description: 'All available category labels.',
        name: 'allCategories',
        required: false,
        type: 'string[]',
      },
      {
        description: 'Currently selected category labels.',
        name: 'selected',
        required: false,
        type: 'string[]',
      },
      {
        description: 'Called with the new selection when a pill is toggled.',
        name: 'onchange',
        required: false,
        type: '(categories: string[]) => void',
      },
    ],
    slug: 'category-picker',
    snippets: [
      {
        code: `<CategoryPicker\n  allCategories={['Anime', 'Sci-Fi', 'Fantasy']}\n  selected={selected}\n  onchange={(c) => (selected = c)}\n/>`,
        lang: 'svelte',
        title: 'Basic',
      },
    ],
    source: 'frontend/src/lib/CategoryPicker.svelte',
    title: 'CategoryPicker',
  },
  {
    demo: MarkdownRenderersDemo,
    description:
      'XSS-safe markdown rendering via marked + DOMPurify, with streaming cursor support.',
    group: 'composite',
    props: [
      {
        description: 'Raw markdown source.',
        name: 'content',
        required: false,
        type: 'string',
      },
      {
        default: 'false',
        description: 'Whether this is the last message in the stream.',
        name: 'isLast',
        required: false,
        type: 'boolean',
      },
      {
        default: 'false',
        description: 'Show a blinking cursor when content is empty and this is the last message.',
        name: 'streaming',
        required: false,
        type: 'boolean',
      },
    ],
    slug: 'markdown-renderer',
    snippets: [
      {
        code: `<MarkdownRenderer content={messageText} />`,
        lang: 'svelte',
        title: 'Basic',
      },
      {
        code: `<MarkdownRenderer content={last} isLast={true} streaming={streaming} />`,
        lang: 'svelte',
        title: 'Streaming',
      },
    ],
    source: 'frontend/src/lib/MarkdownRenderer.svelte',
    title: 'MarkdownRenderer',
  },
  {
    demo: FileAttachmentsDemo,
    description:
      'File chip row for a chat thread — click to expand extracted text, × to delete. Hidden for RP bots.',
    group: 'composite',
    props: [
      {
        description: 'Files attached to a thread/message.',
        name: 'threadFiles',
        required: false,
        type: 'ThreadFileDTO[]',
      },
      {
        default: '"rp"',
        description: 'Bot type — file UI is hidden for "rp" bots.',
        name: 'botType',
        required: false,
        type: 'string',
      },
      {
        description: 'Called when a file × button is clicked.',
        name: 'ondelet',
        required: false,
        type: '(id: number) => void',
      },
    ],
    slug: 'file-attachments',
    snippets: [
      {
        code: `<FileAttachments\n  botType="assistant"\n  threadFiles={files}\n  ondelet={removeFile}\n/>`,
        lang: 'svelte',
        title: 'Basic',
      },
    ],
    source: 'frontend/src/lib/FileAttachments.svelte',
    title: 'FileAttachments',
  },
  {
    demo: BotCardsDemo,
    description:
      'Hero card with avatar/gradient, categories, type badge, and per-card action buttons.',
    group: 'composite',
    props: [
      {
        description: 'Bot data (12 required fields).',
        name: 'bot',
        required: true,
        type: 'Bot',
      },
      {
        default: 'false',
        description: 'Show chat/edit/export/delete action buttons in the footer.',
        name: 'showActions',
        required: false,
        type: 'boolean',
      },
      {
        description: 'Card click handler (makes the whole card a button).',
        name: 'onclick',
        required: false,
        type: '(bot: Bot) => void',
      },
      {
        description: 'Chat action (only when showActions).',
        name: 'onchat',
        required: false,
        type: '(bot: Bot) => void',
      },
      {
        description: 'Edit action (only when showActions).',
        name: 'onedit',
        required: false,
        type: '(bot: Bot) => void',
      },
      {
        description: 'Export action (only when showActions).',
        name: 'onexport',
        required: false,
        type: '(bot: Bot, format: "json" | "png") => void',
      },
      {
        description: 'Delete action (only when showActions).',
        name: 'ondelete',
        required: false,
        type: '(bot: Bot) => void',
      },
    ],
    slug: 'bot-card',
    snippets: [
      {
        code: `<BotCard {bot} onclick={(b) => gotoThread(b.id)} />`,
        lang: 'svelte',
        title: 'Basic',
      },
      {
        code: `<BotCard\n  {bot}\n  showActions\n  onchat={openChat}\n  onedit={openEditor}\n  onexport={(b, fmt) => exportBot(b, fmt)}\n  ondelete={removeBot}\n/>`,
        lang: 'svelte',
        title: 'With actions',
      },
    ],
    source: 'frontend/src/lib/BotCard.svelte',
    title: 'BotCard',
  },
  {
    demo: BackendErrorScreensDemo,
    description:
      'Full-page error screen for backend unreachable or degraded states, with copy-URL + retry.',
    group: 'composite',
    props: [
      {
        description: 'Error category driving the headline copy.',
        name: 'kind',
        required: true,
        type: "'unreachable' | 'degraded'",
      },
      {
        description: 'Last-known backend URL.',
        name: 'apiBase',
        required: true,
        type: 'string',
      },
      {
        description: 'HTTP status code, when known.',
        name: 'status',
        required: false,
        type: 'number',
      },
      {
        description: 'Raw error detail from the health response.',
        name: 'detail',
        required: false,
        type: 'string',
      },
      {
        description: 'Re-run the readiness check.',
        name: 'onretry',
        required: true,
        type: '() => void',
      },
      {
        default: 'false',
        description: 'Disable the retry button while in flight.',
        name: 'retrying',
        required: false,
        type: 'boolean',
      },
    ],
    slug: 'backend-error-screen',
    snippets: [
      {
        code: `<BackendErrorScreen\n  kind="unreachable"\n  apiBase={apiBase()}\n  onretry={checkBackend}\n/>`,
        lang: 'svelte',
        title: 'Unreachable',
      },
      {
        code: `<BackendErrorScreen\n  kind="degraded"\n  status={503}\n  detail={err}\n  apiBase={apiBase()}\n  onretry={checkBackend}\n  retrying={loading}\n/>`,
        lang: 'svelte',
        title: 'Degraded with detail',
      },
    ],
    source: 'frontend/src/lib/BackendErrorScreen.svelte',
    title: 'BackendErrorScreen',
  },
  {
    demo: DeleteConfirmModalsDemo,
    description:
      'Confirmation modal with red warning icon, i18n-aware title/message, and cancel/delete buttons.',
    group: 'composite',
    props: [
      {
        description: 'Open state ($bindable).',
        name: 'show',
        required: false,
        type: 'boolean',
      },
      {
        description: 'Language code for title/msg/button copy.',
        name: 'lang',
        required: false,
        type: 'string',
      },
      {
        description: 'Called when Cancel is clicked (also fires onclose).',
        name: 'oncancel',
        required: false,
        type: '() => void',
      },
      {
        description: 'Called when Delete is clicked.',
        name: 'onconfirm',
        required: false,
        type: '() => void',
      },
    ],
    slug: 'delete-confirm-modal',
    snippets: [
      {
        code: `<DeleteConfirmModal\n  show={open}\n  lang="en"\n  oncancel={() => (open = false)}\n  onconfirm={removeMessage}\n/>`,
        lang: 'svelte',
        title: 'Basic',
      },
    ],
    source: 'frontend/src/lib/DeleteConfirmModal.svelte',
    title: 'DeleteConfirmModal',
  },
  {
    demo: ChatHeadersDemo,
    description:
      'Chat-thread header: bot avatar+name+stats on the left, ⋮ thread menu (new/summarize/export/edit/delete) on the right.',
    group: 'composite',
    props: [
      {
        description: 'Display name of the bot.',
        name: 'botName',
        required: false,
        type: 'string',
      },
      {
        description: 'Avatar path served by the backend, or null for placeholder.',
        name: 'botAvatarPath',
        required: false,
        type: 'string | null',
      },
      {
        description: 'Number of messages in the thread (used in stats line).',
        name: 'messageCount',
        required: false,
        type: 'number',
      },
      {
        description: 'Total tokens across the thread (formatted as 1.2k).',
        name: 'totalTokens',
        required: false,
        type: 'number',
      },
      {
        default: 'false',
        description: 'Show green-active state on menu button when a summary exists.',
        name: 'hasSummary',
        required: false,
        type: 'boolean',
      },
      {
        default: 'false',
        description: 'Show spinner in the "Summarize" menu item while compressing.',
        name: 'compressing',
        required: false,
        type: 'boolean',
      },
      {
        description: 'Language code for all button labels and stats template.',
        name: 'lang',
        required: false,
        type: 'string',
      },
      {
        description: 'Open thread-list drawer.',
        name: 'ontoggleThreads',
        required: false,
        type: '() => void',
      },
      {
        description: 'Start a new thread in this bot.',
        name: 'onnewthread',
        required: false,
        type: '() => void',
      },
      {
        description: 'Compress this thread into a summary (disabled while compressing).',
        name: 'oncompress',
        required: false,
        type: '() => void',
      },
      {
        description: 'Export this thread (json/png).',
        name: 'onexport',
        required: false,
        type: '() => void',
      },
      {
        description: 'Edit the bot (jumps to bot editor).',
        name: 'oneditbot',
        required: false,
        type: '() => void',
      },
      {
        description: 'Delete this thread (confirm modal elsewhere).',
        name: 'ondeleteThread',
        required: false,
        type: '() => void',
      },
    ],
    slug: 'chat-header',
    snippets: [
      {
        code: `<ChatHeader\n  botName={bot.name}\n  botAvatarPath={bot.avatar_path}\n  messageCount={msgs.length}\n  totalTokens={totalTokens}\n  onnewthread={newThread}\n/>`,
        lang: 'svelte',
        title: 'Basic',
      },
    ],
    source: 'frontend/src/lib/ChatHeader.svelte',
    title: 'ChatHeader',
  },
  {
    demo: ChatInputsDemo,
    description:
      'Auto-grow textarea with bold-action (RP bots) or file upload (assistant bots), drag-and-drop, and stop button while streaming.',
    group: 'composite',
    props: [
      {
        description: 'Bot id for upload endpoint.',
        name: 'botId',
        required: false,
        type: 'number',
      },
      {
        description: 'Thread id for upload endpoint.',
        name: 'threadId',
        required: false,
        type: 'number',
      },
      {
        default: '"rp"',
        description: 'Bot type — RP shows bold, assistant shows file upload.',
        name: 'botType',
        required: false,
        type: 'BotType',
      },
      {
        default: 'false',
        description: 'Show the red stop button instead of send; disables the textarea.',
        name: 'streaming',
        required: false,
        type: 'boolean',
      },
      {
        description: 'Called with (text, fileIds) on send; empty text sends "*continue*".',
        name: 'onsend',
        required: false,
        type: '(text: string, fileIds: number[]) => void',
      },
      {
        description: 'Called when the stop button is clicked while streaming.',
        name: 'onstop',
        required: false,
        type: '() => void',
      },
    ],
    slug: 'chat-input',
    snippets: [
      {
        code: `<ChatInput\n  botId={bot.id}\n  threadId={thread.id}\n  botType={bot.type}\n  streaming={streaming}\n  onsend={(text, files) => send(text, files)}\n  onstop={abortStream}\n/>`,
        lang: 'svelte',
        title: 'Basic',
      },
    ],
    source: 'frontend/src/lib/ChatInput.svelte',
    title: 'ChatInput',
  },
  {
    demo: AvatarUploadsDemo,
    description:
      'Square avatar (80×80) with hash-based gradient placeholder, click-to-upload, and loading-overlay while uploading.',
    group: 'composite',
    props: [
      {
        description: 'Object URL or data URL for the avatar preview.',
        name: 'avatarPreview',
        required: false,
        type: 'string',
      },
      {
        description:
          'Display name — used to pick a gradient and show the first letter in the placeholder.',
        name: 'name',
        required: false,
        type: 'string',
      },
      {
        default: 'false',
        description: 'Show the loading dots overlay and disable the upload button.',
        name: 'uploading',
        required: false,
        type: 'boolean',
      },
      {
        description: 'Id for the hidden <input type=file>; pair with the visible <label>.',
        name: 'inputId',
        required: false,
        type: 'string',
      },
      {
        description: 'Called on file change; read files[0] and call avatarPreview setter.',
        name: 'onupload',
        required: false,
        type: '(e: Event) => void',
      },
    ],
    slug: 'avatar-upload',
    snippets: [
      {
        code: `<AvatarUpload\n  name={bot.name}\n  avatarPreview={preview()}\n  uploading={busy}\n  onupload={handleAvatar}\n/>`,
        lang: 'svelte',
        title: 'Basic',
      },
    ],
    source: 'frontend/src/lib/AvatarUpload.svelte',
    title: 'AvatarUpload',
  },
  {
    demo: EditMessageModalsDemo,
    description:
      'Large modal wrapping a 10-row textarea (Input textarea) with cancel/save footer; save disabled when empty.',
    group: 'composite',
    props: [
      {
        description: 'Open state ($bindable).',
        name: 'show',
        required: false,
        type: 'boolean',
      },
      {
        description: 'Initial text to populate the textarea.',
        name: 'content',
        required: false,
        type: 'string',
      },
      {
        description: 'Language code for title + button labels.',
        name: 'lang',
        required: false,
        type: 'string',
      },
      {
        description: 'Called on cancel click and on Esc/backdrop close.',
        name: 'onclose',
        required: false,
        type: '() => void',
      },
      {
        description: 'Called with the edited text on save click.',
        name: 'onsave',
        required: false,
        type: '(text: string) => void',
      },
    ],
    slug: 'edit-message-modal',
    snippets: [
      {
        code: `<EditMessageModal\n  show={open}\n  content={msg.content}\n  onclose={() => (open = false)}\n  onsave={(t) => saveEdit(msg.id, t)}\n/>`,
        lang: 'svelte',
        title: 'Basic',
      },
    ],
    source: 'frontend/src/lib/EditMessageModal.svelte',
    title: 'EditMessageModal',
  },
  {
    demo: SidebarsDemo,
    description:
      'Fixed-position nav sidebar (220px expanded / 60px collapsed) with brand + 7 nav items + footer.',
    group: 'composite',
    props: [
      {
        description: "Hash route to highlight ('/' | '/chat' | '/bots' | ...).",
        name: 'currentRoute',
        required: false,
        type: 'string',
      },
    ],
    slug: 'sidebar',
    snippets: [
      {
        code: `<Sidebar currentRoute={route} />`,
        lang: 'svelte',
        title: 'Basic',
      },
    ],
    source: 'frontend/src/lib/Sidebar.svelte',
    title: 'Sidebar',
  },
  {
    demo: MessageContextMenusDemo,
    description:
      'Right-click context menu for a message — Copy (with copied feedback) and Edit. Edge-flips when near the viewport bottom.',
    group: 'composite',
    props: [
      {
        description: 'The message that was right-clicked (used for Copy/Edit).',
        name: 'msg',
        required: true,
        type: 'Message',
      },
      {
        description: 'Fixed-position coords; menu is hidden when null.',
        name: 'position',
        required: true,
        type: 'null | { x: number; y: number }',
      },
      {
        description: 'Called when Esc / outside-click / scroll / resize closes the menu.',
        name: 'onclose',
        required: true,
        type: '() => void',
      },
      {
        description: 'Called with the message when "Edit" is clicked.',
        name: 'onedit',
        required: false,
        type: '(msg: Message) => void',
      },
    ],
    slug: 'message-context-menu',
    snippets: [
      {
        code: `<MessageContextMenu\n  {msg}\n  {position}\n  onclose={() => (position = null)}\n  onedit={(m) => openEditModal(m)}\n/>`,
        lang: 'svelte',
        title: 'Basic',
      },
    ],
    source: 'frontend/src/lib/MessageContextMenu.svelte',
    title: 'MessageContextMenu',
  },
  {
    demo: MessageBubblesDemo,
    description:
      'Per-message bubble: avatar + markdown content + reasoning panel + files + action bar (regenerate/edit/debug/delete) + versions. Right-click for the context menu.',
    group: 'composite',
    props: [
      {
        description: 'The message to render (role/content/timestamps/etc.).',
        name: 'msg',
        required: true,
        type: 'Message',
      },
      {
        description: 'Bot display name (used for {{char}} substitution and avatar placeholder).',
        name: 'botName',
        required: false,
        type: 'string',
      },
      {
        description: 'Bot avatar path; null for gradient placeholder.',
        name: 'botAvatarPath',
        required: false,
        type: 'string | null',
      },
      {
        description: 'Persona display name (used for {{user}} substitution).',
        name: 'personaName',
        required: false,
        type: 'string',
      },
      {
        description: 'Persona avatar path; null for gradient placeholder.',
        name: 'personaAvatarPath',
        required: false,
        type: 'string | null',
      },
      {
        description: 'Files attached to this message (chips below the bubble).',
        name: 'files',
        required: false,
        type: 'ThreadFileDTO[]',
      },
      {
        default: 'false',
        description: 'Show the typing-dots placeholder while content is empty and streaming.',
        name: 'streaming',
        required: false,
        type: 'boolean',
      },
      {
        default: 'false',
        description:
          'Whether this is the last message (controls streaming cursor + regenerate button).',
        name: 'isLast',
        required: false,
        type: 'boolean',
      },
      {
        default: 'false',
        description: 'Show a "Retry" button for failed user messages.',
        name: 'showRetry',
        required: false,
        type: 'boolean',
      },
      {
        description: 'All versions of this message; only show version controls if length > 1.',
        name: 'versions',
        required: false,
        type: 'Message[]',
      },
      {
        description: 'Called with the clicked action button text (parsed from message content).',
        name: 'onaction',
        required: false,
        type: '(text: string) => void',
      },
      {
        description: 'Called when "Edit" is clicked (opens EditMessageModal).',
        name: 'onedit',
        required: false,
        type: '(m: Message) => void',
      },
      {
        description: 'Called when "Delete" is clicked.',
        name: 'ondelete',
        required: false,
        type: '(msgId: number) => void',
      },
      {
        description: 'Called when the "Regenerate" icon is clicked on the last assistant message.',
        name: 'onregenerate',
        required: false,
        type: '() => void',
      },
      {
        description: 'Called when the user retries a failed message.',
        name: 'onretry',
        required: false,
        type: '() => void',
      },
      {
        description: 'Called with the chosen version id from the version control arrows.',
        name: 'onswitchversion',
        required: false,
        type: '(versionId: number) => void',
      },
      {
        description: 'Called when the "wrench" button is clicked (opens LLMDebugModal).',
        name: 'onopendebug',
        required: false,
        type: '() => void',
      },
    ],
    slug: 'message-bubble',
    snippets: [
      {
        code: `<MessageBubble\n  botName={bot.name}\n  personaName="me"\n  msg={msg}\n  isLast\n  onregenerate={regen}\n  onedit={openEdit}\n  ondelete={remove}\n/>`,
        lang: 'svelte',
        title: 'Assistant (last)',
      },
    ],
    source: 'frontend/src/lib/MessageBubble.svelte',
    title: 'MessageBubble',
  },
  {
    demo: RecentChatsDemo,
    description:
      'List of recent chat threads with avatar + last message preview + delete button. Loading and empty states included.',
    group: 'composite',
    props: [
      {
        description: 'Threads to render.',
        name: 'threads',
        required: false,
        type: 'RecentThread[]',
      },
      {
        default: 'false',
        description: 'Show a "loading" message instead of the list.',
        name: 'loading',
        required: false,
        type: 'boolean',
      },
      {
        description: 'Called when a thread card is clicked.',
        name: 'onselectThread',
        required: false,
        type: '(botId: number, threadId: number) => void',
      },
      {
        description:
          'Called when the delete button is clicked (component shows a spinner until resolution).',
        name: 'ondeleteThread',
        required: false,
        type: '(threadId: number) => void',
      },
    ],
    slug: 'recent-chats',
    snippets: [
      {
        code: `<RecentChats\n  threads={threads}\n  loading={busy}\n  onselectThread={(b, t) => open(b, t)}\n  ondeleteThread={remove}\n/>`,
        lang: 'svelte',
        title: 'Basic',
      },
    ],
    source: 'frontend/src/lib/RecentChats.svelte',
    title: 'RecentChats',
  },
  {
    demo: ThreadDrawersDemo,
    description:
      'Right-aside thread picker for a chat. Right-click for rename/delete context menu, inline rename, and delete confirmation modal.',
    group: 'composite',
    props: [
      {
        description: 'Threads for the current bot.',
        name: 'threads',
        required: false,
        type: 'Thread[]',
      },
      {
        description: 'Currently selected thread id (highlighted).',
        name: 'selectedThreadId',
        required: false,
        type: 'null | number',
      },
      {
        description: 'Close the drawer (backdrop click on mobile, X button).',
        name: 'onclose',
        required: false,
        type: '() => void',
      },
      {
        description: 'Start a new thread for the current bot.',
        name: 'onnew',
        required: false,
        type: '() => void',
      },
      {
        description: 'Select a thread (closes the drawer on mobile).',
        name: 'onselect',
        required: false,
        type: '(id: number) => void',
      },
      {
        description: 'Called after a successful rename.',
        name: 'onrename',
        required: false,
        type: '(id: number, name: string) => void',
      },
      {
        description: 'Called after a successful delete.',
        name: 'ondelete',
        required: false,
        type: '(id: number) => void',
      },
    ],
    slug: 'thread-drawer',
    snippets: [
      {
        code: `<ThreadDrawer\n  threads={botThreads}\n  {selectedThreadId}\n  onclose={() => (open = false)}\n  onselect={(id) => gotoThread(id)}\n  onnew={newThread}\n/>`,
        lang: 'svelte',
        title: 'Basic',
      },
    ],
    source: 'frontend/src/lib/ThreadDrawer.svelte',
    title: 'ThreadDrawer',
  },
  {
    demo: PersonaSelectModalsDemo,
    description:
      'Modal that asks the user which persona to chat with — list of existing + inline create form + start chat / import action.',
    group: 'composite',
    props: [
      {
        description: 'Open state ($bindable).',
        name: 'show',
        required: false,
        type: 'boolean',
      },
      {
        description: 'Bot id for the new thread (chat mode).',
        name: 'botId',
        required: false,
        type: 'number',
      },
      {
        default: '"chat"',
        description: '"chat" creates a new thread, "import" just returns the persona id.',
        name: 'mode',
        required: false,
        type: '"chat" | "import"',
      },
      {
        description: 'Available personas.',
        name: 'personas',
        required: false,
        type: 'Persona[]',
      },
      {
        description: 'Called with the new thread id (chat) or persona id (import).',
        name: 'onselect',
        required: false,
        type: '(threadId: number) => void',
      },
    ],
    slug: 'persona-select-modal',
    snippets: [
      {
        code: `<PersonaSelectModal\n  show={open}\n  botId={bot.id}\n  {personas}\n  onselect={(tid) => gotoThread(tid)}\n/>`,
        lang: 'svelte',
        title: 'Chat mode',
      },
    ],
    source: 'frontend/src/lib/PersonaSelectModal.svelte',
    title: 'PersonaSelectModal',
  },
  {
    demo: LLMDebugModalsDemo,
    description:
      'Dev-mode modal showing the exact messages array sent to the LLM, with usage pills (prompt/completion/total tokens) and a pretty-printed JSON block.',
    group: 'composite',
    props: [
      {
        description: 'LLM call metadata (model, temperature, max_tokens, messages array).',
        name: 'debug',
        required: true,
        type: 'LLMDebugInfo',
      },
      {
        description: 'Token usage breakdown; pass null if the model did not return it.',
        name: 'usage',
        required: true,
        type: 'LLMUsage | null',
      },
      {
        description: 'Close handler (Esc + backdrop click).',
        name: 'onclose',
        required: true,
        type: '() => void',
      },
    ],
    slug: 'llm-debug-modal',
    snippets: [
      {
        code: `<LLMDebugModal\n  {debug}\n  {usage}\n  onclose={() => (open = false)}\n/>`,
        lang: 'svelte',
        title: 'Basic',
      },
    ],
    source: 'frontend/src/lib/LLMDebugModal.svelte',
    title: 'LLMDebugModal',
  },
  {
    demo: GlobalDropZonesDemo,
    description:
      'Full-window drop zone that imports a character card (.json/.png/.webp) by calling api.importBot on drop. Renders a centered overlay during drag.',
    group: 'composite',
    props: [],
    slug: 'global-drop-zone',
    snippets: [
      {
        code: `<!-- Mount once at the App level -->\n<GlobalDropZone />`,
        lang: 'svelte',
        title: 'No props',
      },
    ],
    source: 'frontend/src/lib/GlobalDropZone.svelte',
    title: 'GlobalDropZone',
  },
  {
    demo: TTSButtonDemo,
    description:
      'Per-message text-to-speech control (play / loading spinner / stop). Hidden when the backend returns 503 for /synthesize (TTS_PROVIDER=disabled). Cache id is reused across plays so re-listens do not re-charge the provider.',
    group: 'composite',
    props: [
      {
        description:
          'Plain text to speak. Markdown metadata is stripped by the parent MessageBubble before this prop is set.',
        name: 'content',
        required: true,
        type: 'string',
      },
    ],
    slug: 'tts-button',
    snippets: [
      {
        code: `<TTSButton content={msg.content} />`,
        lang: 'svelte',
        title: 'In MessageBubble',
      },
    ],
    source: 'frontend/src/lib/ui/TTSButton.svelte',
    title: 'TTSButton',
  },
];
