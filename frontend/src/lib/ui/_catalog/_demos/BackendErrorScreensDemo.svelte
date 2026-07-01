<!-- BackendErrorScreensDemo.svelte — shows both error kinds with mock retry handlers -->
<script lang="ts">
  import BackendErrorScreen from '../../../BackendErrorScreen.svelte';

  let unreachableRetrying = $state(false);
  let degradedRetrying = $state(false);

  function retry(kind: 'degraded' | 'unreachable') {
    if (kind === 'unreachable') unreachableRetrying = true;
    else degradedRetrying = true;
    setTimeout(() => {
      unreachableRetrying = false;
      degradedRetrying = false;
    }, 1500);
  }
</script>

<div class="bes-stack">
  <div class="bes-row">
    <span class="bes-label">Unreachable (network down)</span>
    <div class="bes-frame">
      <BackendErrorScreen
        kind="unreachable"
        apiBase="http://127.0.0.1:55245"
        onretry={() => retry('unreachable')}
        retrying={unreachableRetrying}
      />
    </div>
  </div>
  <div class="bes-row">
    <span class="bes-label">Degraded (DB error)</span>
    <div class="bes-frame">
      <BackendErrorScreen
        kind="degraded"
        status={503}
        detail="database connection refused"
        apiBase="http://127.0.0.1:55245"
        onretry={() => retry('degraded')}
        retrying={degradedRetrying}
      />
    </div>
  </div>
</div>

<style>
  .bes-stack {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }
  .bes-row {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .bes-label {
    font-family: 'Maple Mono', monospace;
    font-size: 11px;
    color: var(--ray-text-tertiary);
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }
  .bes-frame {
    height: 480px;
    border: 1px solid var(--ray-border-subtle, rgba(255, 255, 255, 0.04));
    border-radius: 10px;
    overflow: hidden;
    position: relative;
  }
</style>
