'use client';

import { useState, useRef, useEffect } from 'react';
import { Send, ImagePlus } from 'lucide-react';
import { cn } from '@/lib/utils';

interface ChatInputProps {
  onSend: (message: string) => void;
  isLoading: boolean;
  placeholder?: string;
  onImageUpload?: (dataUrl: string, fileName: string) => void;
  uploadedImageName?: string | null;
}

export default function ChatInput({ onSend, isLoading, placeholder, onImageUpload, uploadedImageName }: ChatInputProps) {
  const [input, setInput] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 160)}px`;
    }
  }, [input]);

  const handleSubmit = () => {
    const trimmed = input.trim();
    if (!trimmed || isLoading) return;
    onSend(trimmed);
    setInput('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleImageSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
      const dataUrl = ev.target?.result as string;
      if (dataUrl && onImageUpload) {
        onImageUpload(dataUrl, file.name);
      }
    };
    reader.readAsDataURL(file);
    e.target.value = '';
  };

  return (
    <div className="w-full max-w-[720px] mx-auto px-4">
      {uploadedImageName && (
        <div className="flex items-center gap-2 mb-2.5 px-1">
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-emerald-50 border border-emerald-100 text-emerald-600 text-[11.5px] font-medium">
            <span>{uploadedImageName}</span>
            <span className="text-emerald-400">attached</span>
          </div>
        </div>
      )}

      <div
        className={cn(
          'relative flex items-end gap-1 rounded-2xl border bg-white transition-all duration-200 shadow-sm',
          'focus-within:border-brand-400 focus-within:ring-4 focus-within:ring-brand-100/50',
          'border-surface-3'
        )}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          onChange={handleImageSelect}
          className="hidden"
        />
        <button
          onClick={() => fileInputRef.current?.click()}
          disabled={isLoading}
          className="flex-shrink-0 ml-2 mb-2.5 p-2 rounded-lg text-ink-300 hover:text-brand-500 hover:bg-brand-50 transition-colors disabled:opacity-40"
          title="Upload floor plan image"
        >
          <ImagePlus size={16} />
        </button>

        <textarea
          ref={textareaRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder || 'Describe your event or ask a question...'}
          disabled={isLoading}
          rows={1}
          className={cn(
            'flex-1 resize-none bg-transparent py-3.5 text-[13.5px] leading-relaxed',
            'text-ink-900 placeholder:text-ink-400',
            'focus:outline-none disabled:opacity-40',
            'min-h-[48px] max-h-[160px]'
          )}
        />
        <button
          onClick={handleSubmit}
          disabled={!input.trim() || isLoading}
          className={cn(
            'flex-shrink-0 m-1.5 p-2.5 rounded-xl transition-all duration-200',
            input.trim() && !isLoading
              ? 'bg-gradient-to-r from-brand-600 to-brand-700 text-white hover:from-brand-700 hover:to-brand-800 shadow-sm'
              : 'bg-surface-2 text-ink-200 cursor-not-allowed'
          )}
        >
          <Send size={15} />
        </button>
      </div>
      <p className="text-center text-[10.5px] text-ink-400 mt-3 pb-1 tracking-wide">
        Raahi AI can make mistakes. Verify critical safety recommendations.
      </p>
    </div>
  );
}
