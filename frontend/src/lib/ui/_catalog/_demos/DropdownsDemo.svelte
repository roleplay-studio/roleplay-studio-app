<!-- DropdownsDemo.svelte — Dropdown component, with icons + dividers + alignment -->
<script lang="ts">
  import Dropdown from '../../Dropdown.svelte';
</script>

<div class="dd-stack">
  <div class="dd-row">
    <span class="dd-label">Basic</span>
    <Dropdown
      label="Options"
      items={[
        { label: 'Edit', value: 'edit' },
        { label: 'Duplicate', value: 'duplicate' },
        { label: 'Archive', value: 'archive' },
      ]}
      onselect={(v) => console.log('[dd-basic]', v)}
    />
  </div>

  <div class="dd-row">
    <span class="dd-label">With icons</span>
    <Dropdown
      label="Actions"
      items={[
        { icon: 'edit', label: 'Edit', value: 'edit' },
        { icon: 'copy', label: 'Duplicate', value: 'duplicate' },
        { icon: 'trash', label: 'Delete', value: 'delete' },
      ]}
      onselect={(v) => console.log('[dd-icons]', v)}
    />
  </div>

  <div class="dd-row">
    <span class="dd-label">With divider</span>
    <Dropdown
      label="Account"
      items={[
        { icon: 'edit', label: 'Profile', value: 'profile' },
        { icon: 'settings-2', label: 'Settings', value: 'settings' },
        { divider: true, label: '', value: 'd1' },
        { icon: 'trash', label: 'Sign out', value: 'signout' },
      ]}
      onselect={(v) => console.log('[dd-divider]', v)}
    />
  </div>

  <div class="dd-row">
    <span class="dd-label">End-aligned</span>
    <Dropdown
      align="end"
      label="⋯"
      items={[
        { label: 'Rename', value: 'rename' },
        { label: 'Move', value: 'move' },
        { divider: true, label: '', value: 'd1' },
        { label: 'Delete', value: 'delete' },
      ]}
      onselect={(v) => console.log('[dd-end]', v)}
    />
  </div>
</div>

<style>
  .dd-stack {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .dd-row {
    display: flex;
    align-items: center;
    gap: 12px;
  }
  .dd-label {
    font-family: 'Maple Mono', monospace;
    font-size: 11px;
    color: var(--ray-text-tertiary);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    min-width: 100px;
  }
</style>
