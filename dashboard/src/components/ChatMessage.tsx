'use client';

import { Message } from '@/types';
import { cn } from '@/lib/utils';
import { ArrowRight } from 'lucide-react';

export type ActionType = 'FLOOR_PLANNER' | 'UPLOAD_IMAGE' | 'SIMULATOR';

interface ChatMessageProps {
  message: Message;
  isStreaming?: boolean;
  onAction?: (action: ActionType) => void;
}

const ACTION_BUTTONS: Record<ActionType, { label: string; description: string; accent: string; border: string; text: string; hover: string }> = {
  FLOOR_PLANNER: {
    label: 'Open Floor Planner',
    description: 'Pre-loaded with your event data',
    accent: 'bg-brand-50',
    border: 'border-brand-200',
    text: 'text-brand-700',
    hover: 'hover:bg-brand-100/60',
  },
  UPLOAD_IMAGE: {
    label: 'Upload Floor Plan',
    description: 'Attach a venue image',
    accent: 'bg-emerald-50',
    border: 'border-emerald-200',
    text: 'text-emerald-700',
    hover: 'hover:bg-emerald-100/60',
  },
  SIMULATOR: {
    label: 'Run Simulation',
    description: 'Simulate crowd flow',
    accent: 'bg-amber-50',
    border: 'border-amber-200',
    text: 'text-amber-700',
    hover: 'hover:bg-amber-100/60',
  },
};

const ACTION_REGEX = /\{\{(FLOOR_PLANNER|UPLOAD_IMAGE|SIMULATOR)\}\}/g;

function formatContent(content: string): string {
  let html = content
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/`(.*?)`/g, '<code>$1</code>')
    .replace(/^### (.*$)/gm, '<h3>$1</h3>')
    .replace(/^## (.*$)/gm, '<h2>$1</h2>')
    .replace(/^# (.*$)/gm, '<h1>$1</h1>')
    .replace(/^[\-\*] (.*$)/gm, '<li>$1</li>')
    .replace(/^\d+\. (.*$)/gm, '<li>$1</li>')
    .replace(/\n\n/g, '</p><p>')
    .replace(/\n/g, '<br/>');

  html = html.replace(/(<li>.*?<\/li>)(\s*<br\/>?\s*)?(<li>)/g, '$1$3');
  html = html.replace(/(<li>.*?<\/li>)+/g, '<ul>$&</ul>');

  return `<p>${html}</p>`;
}

function ActionButton({ action, onAction }: { action: ActionType; onAction?: (a: ActionType) => void }) {
  const config = ACTION_BUTTONS[action];

  return (
    <button
      onClick={() => onAction?.(action)}
      className={cn(
        'flex items-center justify-between w-full px-4 py-3 rounded-2xl border transition-all duration-200 mt-3 mb-1 group',
        config.accent, config.border, config.hover
      )}
    >
      <div className="text-left">
        <p className={cn('text-[13px] font-semibold tracking-[-0.01em]', config.text)}>
          {config.label}
        </p>
        <p className="text-[11px] text-ink-400 mt-0.5">{config.description}</p>
      </div>
      <ArrowRight size={14} className={cn('opacity-40 group-hover:opacity-80 group-hover:translate-x-0.5 transition-all', config.text)} />
    </button>
  );
}

function renderContentWithActions(content: string, onAction?: (a: ActionType) => void) {
  const parts: React.ReactNode[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  const regex = new RegExp(ACTION_REGEX.source, 'g');

  while ((match = regex.exec(content)) !== null) {
    const textBefore = content.slice(lastIndex, match.index).trim();
    if (textBefore) {
      parts.push(
        <div key={`text-${lastIndex}`} className="prose-chat" dangerouslySetInnerHTML={{ __html: formatContent(textBefore) }} />
      );
    }
    const actionType = match[1] as ActionType;
    parts.push(<ActionButton key={`action-${match.index}`} action={actionType} onAction={onAction} />);
    lastIndex = match.index + match[0].length;
  }

  const remaining = content.slice(lastIndex).trim();
  if (remaining) {
    parts.push(
      <div key={`text-${lastIndex}`} className="prose-chat" dangerouslySetInnerHTML={{ __html: formatContent(remaining) }} />
    );
  }

  return parts.length > 0 ? parts : (
    <div className="prose-chat" dangerouslySetInnerHTML={{ __html: formatContent(content) }} />
  );
}

export default function ChatMessage({ message, isStreaming, onAction }: ChatMessageProps) {
  const isUser = message.role === 'user';

  return (
    <div
      className={cn(
        'animate-slide-up',
        isUser ? 'flex justify-end' : 'flex justify-start'
      )}
    >
      <div className={cn('max-w-[680px]', isUser && 'text-right')}>
        {/* Sender label */}
        <p className={cn(
          'text-[10.5px] font-medium uppercase tracking-[0.06em] mb-1.5 px-1',
          isUser ? 'text-ink-300' : 'text-ink-300'
        )}>
          {isUser ? 'You' : 'Raahi'}
        </p>

        {/* Message content */}
        <div
          className={cn(
            'rounded-2xl px-5 py-3.5 text-[13.5px] leading-[1.7]',
            isUser
              ? 'bg-ink-900 text-white/90 rounded-br-lg'
              : 'bg-white text-ink-700 rounded-bl-lg border border-surface-3/80'
          )}
        >
          {isUser ? (
            <p className="whitespace-pre-wrap text-left">{message.content}</p>
          ) : message.content ? (
            renderContentWithActions(message.content, onAction)
          ) : isStreaming ? (
            <div className="flex items-center gap-1.5 py-1 px-0.5">
              <div className="typing-dot w-1.5 h-1.5 rounded-full bg-ink-300" />
              <div className="typing-dot w-1.5 h-1.5 rounded-full bg-ink-300" />
              <div className="typing-dot w-1.5 h-1.5 rounded-full bg-ink-300" />
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
