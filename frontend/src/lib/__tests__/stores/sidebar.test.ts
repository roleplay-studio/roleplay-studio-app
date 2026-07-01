import { get } from 'svelte/store';
import { describe, expect, it } from 'vitest';

import { isMobile, sidebarOpen } from '../../stores/sidebar';

describe('sidebar store', () => {
  it('sidebarOpen starts as true', () => {
    expect(get(sidebarOpen)).toBe(true);
  });

  it('isMobile starts as false', () => {
    expect(get(isMobile)).toBe(false);
  });

  it('sidebarOpen can be set to false', () => {
    sidebarOpen.set(false);
    expect(get(sidebarOpen)).toBe(false);
    sidebarOpen.set(true); // reset
  });

  it('isMobile can be toggled', () => {
    isMobile.set(true);
    expect(get(isMobile)).toBe(true);
    isMobile.set(false);
  });
});
