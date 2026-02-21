import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

jest.mock('lucide-react', () => ({
  Send: () => <span data-testid="icon-send" />,
}));

import ChatInput from '@/components/ChatInput';

describe('ChatInput', () => {
  const mockOnSend = jest.fn();

  beforeEach(() => {
    mockOnSend.mockClear();
  });

  it('renders the textarea and send button', () => {
    render(<ChatInput onSend={mockOnSend} isLoading={false} />);
    expect(screen.getByRole('textbox')).toBeInTheDocument();
    expect(screen.getByRole('button')).toBeInTheDocument();
  });

  it('renders with custom placeholder', () => {
    render(<ChatInput onSend={mockOnSend} isLoading={false} placeholder="Custom placeholder" />);
    expect(screen.getByPlaceholderText('Custom placeholder')).toBeInTheDocument();
  });

  it('renders default placeholder when none provided', () => {
    render(<ChatInput onSend={mockOnSend} isLoading={false} />);
    expect(screen.getByPlaceholderText(/Describe your event/)).toBeInTheDocument();
  });

  it('disables textarea when loading', () => {
    render(<ChatInput onSend={mockOnSend} isLoading={true} />);
    expect(screen.getByRole('textbox')).toBeDisabled();
  });

  it('disables send button when input is empty', () => {
    render(<ChatInput onSend={mockOnSend} isLoading={false} />);
    expect(screen.getByRole('button')).toBeDisabled();
  });

  it('enables send button when input has text', async () => {
    render(<ChatInput onSend={mockOnSend} isLoading={false} />);
    const textarea = screen.getByRole('textbox');
    await userEvent.type(textarea, 'Hello');
    expect(screen.getByRole('button')).not.toBeDisabled();
  });

  it('calls onSend and clears input on submit', async () => {
    render(<ChatInput onSend={mockOnSend} isLoading={false} />);
    const textarea = screen.getByRole('textbox');
    await userEvent.type(textarea, 'Test message');
    fireEvent.click(screen.getByRole('button'));
    expect(mockOnSend).toHaveBeenCalledWith('Test message');
  });

  it('submits on Enter key (without Shift)', async () => {
    render(<ChatInput onSend={mockOnSend} isLoading={false} />);
    const textarea = screen.getByRole('textbox');
    await userEvent.type(textarea, 'Enter test');
    fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: false });
    expect(mockOnSend).toHaveBeenCalledWith('Enter test');
  });

  it('does not submit on Shift+Enter', async () => {
    render(<ChatInput onSend={mockOnSend} isLoading={false} />);
    const textarea = screen.getByRole('textbox');
    await userEvent.type(textarea, 'Multiline');
    fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: true });
    expect(mockOnSend).not.toHaveBeenCalled();
  });

  it('shows disclaimer text', () => {
    render(<ChatInput onSend={mockOnSend} isLoading={false} />);
    expect(screen.getByText(/can make mistakes/)).toBeInTheDocument();
  });
});
