<!-- ChatBubblesDemo.svelte — ChatBubble for user/assistant/system roles -->
<script lang="ts">
  import ChatBubble from '../../ChatBubble.svelte';
</script>

<div class="cb-stack">
  <ChatBubble
    role="user"
    content="<p>Hello! Can you help me with my bot configuration?</p>"
    time="14:32"
  />
  <ChatBubble
    role="assistant"
    content="<p>Of course! What would you like to adjust — the personality, scenario, or first message?</p>"
    time="14:32"
  />
  <ChatBubble
    role="system"
    content="<p><em>System reminder:</em> The model has switched to GPT-4o.</p>"
    time="14:33"
  />
  <ChatBubble role="user" content="<p>Personality — make it more witty.</p>" time="14:34" />
</div>

<style>
  .cb-stack {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }
</style>
