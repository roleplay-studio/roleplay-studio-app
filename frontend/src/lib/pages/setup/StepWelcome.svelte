<script lang="ts">
  import iconUrl from '../../../icon.png';
  import { t } from '../../i18n';
  import { wizardState } from './wizardState.svelte';

  interface Feature {
    accent: string;
    descKey: string;
    id: string;
    svg: string;
    titleKey: string;
  }

  const features: Feature[] = [
    {
      accent: '#4f8cff',
      descKey: 'feature.chat.desc',
      id: 'chat',
      svg: '<svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>',
      titleKey: 'feature.chat.title',
    },
    {
      accent: '#8b5cf6',
      descKey: 'feature.bots.desc',
      id: 'bots',
      svg: '<svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="8" width="18" height="12" rx="3"/><circle cx="9" cy="14" r="1.5"/><circle cx="15" cy="14" r="1.5"/><line x1="12" y1="4" x2="12" y2="8"/><circle cx="12" cy="3" r="1" fill="currentColor"/></svg>',
      titleKey: 'feature.bots.title',
    },
    {
      accent: '#34c759',
      descKey: 'feature.personas.desc',
      id: 'personas',
      svg: '<svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="8" r="4"/><path d="M4 21c0-4 4-7 8-7s8 3 8 7"/></svg>',
      titleKey: 'feature.personas.title',
    },
    {
      accent: '#ff9500',
      descKey: 'feature.knowledge.desc',
      id: 'knowledge',
      svg: '<svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/></svg>',
      titleKey: 'feature.knowledge.title',
    },
    {
      accent: '#14b8a6',
      descKey: 'feature.models.desc',
      id: 'models',
      svg: '<svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 22 8.5 22 15.5 12 22 2 15.5 2 8.5"/><line x1="2" y1="8.5" x2="12" y2="15.5"/><line x1="22" y1="8.5" x2="12" y2="15.5"/><line x1="12" y1="15.5" x2="12" y2="22"/></svg>',
      titleKey: 'feature.models.title',
    },
    {
      accent: '#fbbf24',
      descKey: 'feature.streaming.desc',
      id: 'streaming',
      svg: '<svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10"/></svg>',
      titleKey: 'feature.streaming.title',
    },
    {
      accent: '#ec4899',
      descKey: 'feature.edit.desc',
      id: 'edit',
      svg: '<svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4z"/></svg>',
      titleKey: 'feature.edit.title',
    },
    {
      accent: '#6b7280',
      descKey: 'feature.history.desc',
      id: 'history',
      svg: '<svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><polyline points="12 7 12 12 15 14"/></svg>',
      titleKey: 'feature.history.title',
    },
    {
      accent: '#f43f5e',
      descKey: 'feature.themes.desc',
      id: 'themes',
      svg: '<svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="13.5" cy="6.5" r="1.5" fill="currentColor"/><circle cx="17.5" cy="10.5" r="1.5" fill="currentColor"/><circle cx="8.5" cy="7.5" r="1.5" fill="currentColor"/><circle cx="6.5" cy="12.5" r="1.5" fill="currentColor"/><path d="M12 2C6.5 2 2 6.5 2 12c0 2 .6 3.9 1.6 5.5L12 22l8.4-4.5C21.4 15.9 22 14 22 12c0-5.5-4.5-10-10-10z"/></svg>',
      titleKey: 'feature.themes.title',
    },
    {
      accent: '#0ea5e9',
      descKey: 'feature.i18n.desc',
      id: 'i18n',
      svg: '<svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><line x1="3" y1="12" x2="21" y2="12"/><path d="M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/></svg>',
      titleKey: 'feature.i18n.title',
    },
    {
      accent: '#10b981',
      descKey: 'feature.android.desc',
      id: 'android',
      svg: '<svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="6" y="2" width="12" height="20" rx="2"/><line x1="12" y1="18" x2="12" y2="18"/></svg>',
      titleKey: 'feature.android.title',
    },
    {
      accent: '#f59e0b',
      descKey: 'feature.upload.desc',
      id: 'upload',
      svg: '<svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66L9.41 17.41a2 2 0 0 1-2.83-2.83l8.49-8.48"/></svg>',
      titleKey: 'feature.upload.title',
    },
  ];
</script>

<div class="welcome-wrap">
  <img src={iconUrl} alt="logo" class="welcome-logo" />
  <h3 class="card-step-title">{t('setup.welcome_title', wizardState.editLanguage)}</h3>
  <p class="card-step-hint">{t('setup.welcome_subtitle', wizardState.editLanguage)}</p>

  <div class="feature-grid">
    {#each features as feat (feat.id)}
      <div class="feature-card" style="--card-accent: {feat.accent}">
        <div class="feature-icon">
          {@html feat.svg}
        </div>
        <div class="feature-text">
          <div class="feature-title">{t(feat.titleKey, wizardState.editLanguage)}</div>
          <div class="feature-desc">{t(feat.descKey, wizardState.editLanguage)}</div>
        </div>
      </div>
    {/each}
  </div>
</div>

<style>
  /* ─── Welcome Step ─── */
  .welcome-wrap {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 12px;
    padding: 12px 0;
    text-align: center;
  }
  .welcome-logo {
    width: 64px;
    height: 64px;
    border-radius: 16px;
  }

  /* ─── Feature Grid ─── */
  .feature-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 8px;
    width: 100%;
    margin-top: 12px;
    text-align: left;
  }
  .feature-card {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 10px;
    padding: 12px;
    text-align: center;
    background: var(--ray-surface);
    border: 1px solid var(--ray-border);
    border-radius: 10px;
    transition:
      background 0.15s ease,
      border-color 0.15s ease;
  }
  .feature-card:hover {
    background: color-mix(in srgb, var(--card-accent) 5%, var(--ray-surface));
    border-color: color-mix(in srgb, var(--card-accent) 25%, var(--ray-border));
  }
  .feature-icon {
    flex-shrink: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 60px;
    height: 60px;
    border-radius: 7px;
    background: color-mix(in srgb, var(--card-accent) 14%, transparent);
    color: var(--card-accent);
  }
  .feature-text {
    flex: 1;
    min-width: 0;
  }
  .feature-title {
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 13px;
    font-weight: 600;
    color: var(--ray-text);
    letter-spacing: 0.2px;
    line-height: 1.2;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .feature-desc {
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 11px;
    font-weight: 400;
    color: var(--ray-text-secondary);
    letter-spacing: 0.1px;
    line-height: 1.3;
    margin-top: 3px;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

  .card-step-hint {
    color: var(--ray-text-secondary);
  }

  @media (max-width: 480px) {
    .feature-grid {
      grid-template-columns: 1fr;
    }
  }
</style>
