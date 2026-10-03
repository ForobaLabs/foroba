import '../i18n';
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { JeliPromptChips } from './JeliPromptChips';

describe('JeliPromptChips', () => {
  it('sends the chip text when clicked', () => {
    const onPick = vi.fn();
    render(<JeliPromptChips onPick={onPick} />);
    fireEvent.click(screen.getByRole('button', { name: 'Where did most of my money go this month?' }));
    expect(onPick).toHaveBeenCalledWith('Where did most of my money go this month?');
  });

  it('renders three chips in a labelled group', () => {
    render(<JeliPromptChips onPick={() => {}} />);
    expect(screen.getByRole('group', { name: 'Try asking' })).toBeInTheDocument();
    expect(screen.getAllByRole('button')).toHaveLength(3);
  });
});
