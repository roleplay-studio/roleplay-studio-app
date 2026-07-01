<!-- ChatBubble — FlyonUI-styled chat bubble component with avatar, header and HTML content -->
<!-- Usage: <ChatBubble role="user" content="Hello!" time="12:34" /> -->
<script lang="ts">
  const {
    class: className = '',
    content = '',
    role = 'user',
    time = '',
  }: {
    class?: string;
    content?: string;
    role?: 'assistant' | 'system' | 'user';
    short_content?: string;
    time?: string;
  } = $props();

  const initial = $derived(role === 'user' ? 'U' : role === 'assistant' ? 'A' : 'S');
  const displayName = $derived(
    role === 'user' ? 'User' : role === 'assistant' ? 'Assistant' : 'System',
  );
  const isSender = $derived(role === 'user');
  const avatarBg = $derived(
    role === 'user' ? 'bg-primary' : role === 'assistant' ? 'bg-secondary' : 'bg-neutral',
  );
</script>

<div class="chat {isSender ? 'chat-sender' : 'chat-receiver'} {className}">
  <div class="chat-avatar avatar">
    <div class="w-10 rounded-full {avatarBg} text-white">
      <span>{initial}</span>
    </div>
  </div>
  <div class="text-xs text-base-content/60 mb-1">
    {displayName}
    {#if time}
      <time class="text-xs opacity-50 ml-1">{time}</time>
    {/if}
  </div>
  <div class="chat-bubble">
    {@html content}
  </div>
</div>
