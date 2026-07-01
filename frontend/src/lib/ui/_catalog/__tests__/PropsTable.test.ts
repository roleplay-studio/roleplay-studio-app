// __tests__/PropsTable.test.ts
import { cleanup, render } from '@testing-library/svelte';
import { afterEach, describe, expect, it } from 'vitest';

import type { CatalogProp } from '../_data/catalog';

import PropsTable from '../_components/PropsTable.svelte';

const PROPS: CatalogProp[] = [
  { default: '""', description: 'The text value.', name: 'value', required: true, type: 'string' },
  { description: 'Hint text.', name: 'placeholder', required: false, type: 'string' },
  {
    default: 'false',
    description: 'Disable input.',
    name: 'disabled',
    required: false,
    type: 'boolean',
  },
];

afterEach(() => cleanup());

describe('PropsTable', () => {
  it('renders header row with 4 columns', () => {
    const { container } = render(PropsTable, { props: { props: PROPS } });
    const headers = container.querySelectorAll('thead th');
    expect(headers).toHaveLength(4);
    expect(headers[0]?.textContent).toBe('Prop');
    expect(headers[1]?.textContent).toBe('Type');
    expect(headers[2]?.textContent).toBe('Default');
    expect(headers[3]?.textContent).toBe('Description');
  });

  it('renders one body row per prop', () => {
    const { container } = render(PropsTable, { props: { props: PROPS } });
    const bodyRows = container.querySelectorAll('tbody tr');
    expect(bodyRows).toHaveLength(PROPS.length);
  });

  it('marks required props with a star', () => {
    const { container } = render(PropsTable, { props: { props: PROPS } });
    const stars = container.querySelectorAll('.pt-req');
    expect(stars).toHaveLength(1); // only 'value' is required
  });

  it('shows em-dash for missing default', () => {
    const { container } = render(PropsTable, { props: { props: PROPS } });
    const placeholderRow = Array.from(container.querySelectorAll('tbody tr')).find((tr) =>
      tr.textContent?.includes('placeholder'),
    );
    const cells = placeholderRow?.querySelectorAll('td');
    expect(cells?.[2]?.textContent?.trim()).toBe('—');
  });
});
