<!-- AvatarUploadsDemo.svelte — avatar with placeholder gradient + loading overlay + upload button -->
<script lang="ts">
  import AvatarUpload from '../../../AvatarUpload.svelte';
  import { logOnly } from '../_mocks/callbacks';

  const onupload = logOnly('avatar-upload');
</script>

<div class="aud-row">
  <div class="aud-col">
    <span class="aud-label">Placeholder (name initial)</span>
    <AvatarUpload name="Aria" {onupload} />
  </div>
  <div class="aud-col">
    <span class="aud-label">Loading state (dots overlay)</span>
    <AvatarUpload name="Bob" uploading {onupload} />
  </div>
  <div class="aud-col">
    <span class="aud-label">Custom input id</span>
    <AvatarUpload name="Cat" inputId="custom-id" {onupload} />
  </div>
</div>

<style>
  .aud-row {
    display: flex;
    gap: 24px;
    flex-wrap: wrap;
  }
  .aud-col {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
  }
  .aud-label {
    font-family: 'Maple Mono', monospace;
    font-size: 10px;
    color: var(--ray-text-tertiary);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    text-align: center;
    max-width: 120px;
  }
</style>
