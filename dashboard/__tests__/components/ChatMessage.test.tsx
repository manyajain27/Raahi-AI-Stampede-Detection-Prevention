import React from 'react';
import { render, screen } from '@testing-library/react';

jest.mock('lucide-react', () => ({
  Bot: () => <span data-testid="icon-bot" />,
  User: () => <span data-testid="icon-user" />,
}));

import ChatMessage from '@/components/ChatMessage';

describe('ChatMessage', () => {
  it('renders user message with correct styling', () => {
    render(<ChatMessage message={{ role: 'user', content: 'Hello world' }} />);
    expect(screen.getByText('Hello world')).toBeInTheDocument();
    expect(screen.getByTestId('icon-user')).toBeInTheDocument();
  });

  it('renders assistant message with correct styling', () => {
    render(<ChatMessage message={{ role: 'assistant', content: 'Hi there!' }} />);
    expect(screen.getByTestId('icon-bot')).toBeInTheDocument();
  });

  it('renders typing indicator when streaming with empty content', () => {
    const { container } = render(
      <ChatMessage message={{ role: 'assistant', content: '' }} isStreaming={true} />
    );
    const dots = container.querySelectorAll('.typing-dot');
    expect(dots.length).toBe(3);
  });

  it('does not show typing indicator when content exists', () => {
    const { container } = render(
      <ChatMessage message={{ role: 'assistant', content: 'Some text' }} isStreaming={true} />
    );
    const dots = container.querySelectorAll('.typing-dot');
    expect(dots.length).toBe(0);
  });

  it('renders bold markdown in assistant messages', () => {
    const { container } = render(
      <ChatMessage message={{ role: 'assistant', content: 'This is **bold** text' }} />
    );
    const strong = container.querySelector('strong');
    expect(strong).toBeInTheDocument();
    expect(strong?.textContent).toBe('bold');
  });

  it('preserves whitespace in user messages', () => {
    render(<ChatMessage message={{ role: 'user', content: 'Line 1\nLine 2' }} />);
    const p = screen.getByText(/Line 1/);
    expect(p.className).toContain('whitespace-pre-wrap');
  });
});
