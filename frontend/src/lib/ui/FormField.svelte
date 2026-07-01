<!-- FormField — label + input wrapper with hint/error support -->
<!-- Usage: <FormField label="Email" error="Required" hint="We'll never share"> <Input bind:value /></FormField> -->

<script lang="ts">
  const {
    children,
    class: className = '',
    error = '',
    hint = '',
    label = '',
    required = false,
  }: {
    children?: import('svelte').Snippet;
    class?: string;
    error?: string;
    hint?: string;
    label?: string;
    required?: boolean;
  } = $props();
</script>

<div class="flex flex-col gap-1.5 {className}">
  {#if label}
    <label class="text-sm text-theme-secondary">
      {label}
      {#if required}<span class="text-red-400">*</span>{/if}
    </label>
  {/if}

  {#if children}
    {@render children()}
  {/if}

  {#if error}
    <span class="text-xs text-rose-400">{error}</span>
  {:else if hint}
    <span class="text-xs text-theme-secondary">{hint}</span>
  {/if}
</div>
