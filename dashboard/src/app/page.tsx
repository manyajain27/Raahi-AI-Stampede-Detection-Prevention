'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import ChatMessage from '@/components/ChatMessage';
import ChatInput from '@/components/ChatInput';
import { Message } from '@/types';
import { ActionType } from '@/components/ChatMessage';

const SUGGESTIONS = [
  {
    title: 'Music Festival',
    description: 'Large outdoor event, 25k+ attendees',
    prompt: "We're organizing an outdoor music festival expecting around 25,000 attendees. Help us plan crowd management.",
  },
  {
    title: 'Marathon Event',
    description: 'Race route with 50k spectators',
    prompt: "We're hosting a city marathon with 10,000 runners and an estimated 50,000 spectators along the route. How should we manage the crowds?",
  },
  {
    title: 'Religious Gathering',
    description: 'Temple complex, 100k devotees',
    prompt: "We're expecting a religious gathering of about 100,000 devotees at a temple complex. What crowd safety measures should we implement?",
  },
  {
    title: 'Conference & Expo',
    description: 'Multi-hall corporate event, 5k attendees',
    prompt: "We're organizing a tech conference with 5,000 attendees across multiple halls and exhibition areas. Help us plan the crowd flow.",
  },
];

function extractEventData(messages: Message[]): Record<string, string> {
  const allText = messages.map((m) => m.content).join('\n');
  const data: Record<string, string> = {};

  // Extract capacity numbers
  const capacityMatch = allText.match(/(\d[\d,]+)\s*(attendees|people|capacity|visitors|devotees|spectators|runners)/i);
  if (capacityMatch) data.capacity = capacityMatch[1].replace(/,/g, '');

  // Extract venue type
  if (/outdoor|open[\s-]?air|park|ground|street|route/i.test(allText)) data.venueType = 'outdoor';
  else if (/indoor|hall|arena|convention|auditorium|stadium/i.test(allText)) data.venueType = 'indoor';

  // Extract event type
  const types = ['concert', 'festival', 'marathon', 'conference', 'expo', 'wedding', 'religious', 'pilgrimage', 'gathering', 'parade', 'match', 'game'];
  for (const t of types) {
    if (new RegExp(t, 'i').test(allText)) { data.eventType = t; break; }
  }

  // Build a summary from user messages only
  const userMsgs = messages.filter((m) => m.role === 'user').map((m) => m.content);
  data.conversationSummary = userMsgs.join(' | ');

  return data;
}

export default function HomePage() {
  const router = useRouter();
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [uploadedImage, setUploadedImage] = useState<string | null>(null);
  const [uploadedImageName, setUploadedImageName] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const contentRef = useRef<string>('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  const hasStarted = messages.length > 0;

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  const saveEventDataToStorage = useCallback(() => {
    const data = extractEventData(messages);
    if (uploadedImage) data.floorPlanImage = uploadedImage;
    if (uploadedImageName) data.floorPlanImageName = uploadedImageName;
    localStorage.setItem('raahi_event_data', JSON.stringify(data));
    localStorage.setItem('raahi_chat_messages', JSON.stringify(messages));
  }, [messages, uploadedImage, uploadedImageName]);

  const handleImageUpload = (dataUrl: string, fileName: string) => {
    setUploadedImage(dataUrl);
    setUploadedImageName(fileName);
    // Notify the AI that an image was uploaded
    sendMessage(`I've uploaded a floor plan image: ${fileName}`);
  };

  const handleAction = (action: ActionType) => {
    saveEventDataToStorage();
    if (action === 'FLOOR_PLANNER') {
      router.push('/floor-planner');
    } else if (action === 'SIMULATOR') {
      router.push('/visualizer');
    } else if (action === 'UPLOAD_IMAGE') {
      fileInputRef.current?.click();
    }
  };

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
      const dataUrl = ev.target?.result as string;
      if (dataUrl) handleImageUpload(dataUrl, file.name);
    };
    reader.readAsDataURL(file);
    e.target.value = '';
  };

  const sendMessage = async (content: string) => {
    const userMessage: Message = { role: 'user', content };
    const updatedMessages = [...messages, userMessage];
    setMessages(updatedMessages);
    setIsLoading(true);
    contentRef.current = '';

    const aiPlaceholder: Message = { role: 'assistant', content: '' };
    setMessages([...updatedMessages, aiPlaceholder]);

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages: updatedMessages }),
      });

      if (!response.ok) {
        const err = await response.json().catch(() => ({ error: 'Unknown error' }));
        throw new Error(err.error || `Server error: ${response.status}`);
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error('No response stream');

      const decoder = new TextDecoder();

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const text = decoder.decode(value, { stream: true });
        const lines = text.split('\n').filter((l) => l.startsWith('data: '));

        for (const line of lines) {
          const data = line.slice(6);
          if (data === '[DONE]') break;

          try {
            const parsed = JSON.parse(data);
            if (parsed.content) {
              contentRef.current += parsed.content;
              const currentContent = contentRef.current;
              setMessages((prev) => {
                const updated = [...prev];
                updated[updated.length - 1] = {
                  role: 'assistant',
                  content: currentContent,
                };
                return updated;
              });
            }
          } catch {
            // skip malformed chunks
          }
        }
      }
    } catch (error: unknown) {
      const errorMessage = error instanceof Error ? error.message : 'Something went wrong';
      setMessages((prev) => {
        const updated = [...prev];
        updated[updated.length - 1] = {
          role: 'assistant',
          content: `I apologize, but I encountered an error: ${errorMessage}. Please try again.`,
        };
        return updated;
      });
    }

    setIsLoading(false);
  };

  return (
    <div className="flex flex-col h-full bg-surface-1">
      {/* Hidden file input for UPLOAD_IMAGE action */}
      <input
        ref={fileInputRef}
        type="file"
        accept="image/*"
        onChange={handleFileInputChange}
        className="hidden"
      />

      {!hasStarted ? (
        /* ─── Welcome Screen ─── */
        <div className="flex-1 flex flex-col items-center justify-center px-8">
          <div className="max-w-[600px] w-full text-center mb-14">
            <h1 className="font-display text-[32px] font-semibold text-ink-900 tracking-[-0.03em] mb-3 leading-tight">
              What event are we<br />planning today?
            </h1>
            <p className="text-[15px] text-ink-400 leading-relaxed max-w-[420px] mx-auto">
              Describe your event and I&apos;ll help you build a crowd
              management strategy from the ground up.
            </p>
          </div>

          <div className="grid grid-cols-2 gap-2.5 max-w-[520px] w-full mb-12">
            {SUGGESTIONS.map((s) => (
              <button
                key={s.title}
                onClick={() => sendMessage(s.prompt)}
                className="group text-left px-4 py-3.5 rounded-2xl border border-ink-100 bg-white hover:border-brand-200 hover:bg-brand-50/30 transition-all duration-200"
              >
                <p className="text-[13px] font-medium text-ink-900 group-hover:text-brand-600 transition-colors tracking-[-0.01em]">
                  {s.title}
                </p>
                <p className="text-[11.5px] text-ink-400 mt-1 leading-snug">
                  {s.description}
                </p>
              </button>
            ))}
          </div>

          <div className="w-full max-w-[600px]">
            <ChatInput
              onSend={sendMessage}
              isLoading={isLoading}
              onImageUpload={handleImageUpload}
              uploadedImageName={uploadedImageName}
            />
          </div>
        </div>
      ) : (
        /* ─── Conversation View ─── */
        <>
          <div className="flex-1 overflow-y-auto px-8 py-10">
            <div className="max-w-[740px] mx-auto space-y-7">
              {messages.map((msg, i) => (
                <ChatMessage
                  key={i}
                  message={msg}
                  isStreaming={isLoading && i === messages.length - 1 && msg.role === 'assistant'}
                  onAction={handleAction}
                />
              ))}
              <div ref={messagesEndRef} />
            </div>
          </div>

          <div className="border-t border-surface-3/60 bg-surface-1 py-4">
            <ChatInput
              onSend={sendMessage}
              isLoading={isLoading}
              onImageUpload={handleImageUpload}
              uploadedImageName={uploadedImageName}
            />
          </div>
        </>
      )}
    </div>
  );
}
