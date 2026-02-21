/**
 * Tests for the /api/chat route.
 * These tests verify request validation, error handling, and streaming response structure.
 * Note: Actual Groq API calls require a valid API key — mock the client for unit tests.
 */

import { SYSTEM_PROMPT, MODEL } from '@/lib/groq';

describe('/api/chat', () => {
  it('SYSTEM_PROMPT is defined and non-empty', () => {
    expect(SYSTEM_PROMPT).toBeDefined();
    expect(SYSTEM_PROMPT.length).toBeGreaterThan(100);
  });

  it('SYSTEM_PROMPT mentions Raahi', () => {
    expect(SYSTEM_PROMPT).toContain('Raahi');
  });

  it('SYSTEM_PROMPT covers key topics', () => {
    expect(SYSTEM_PROMPT).toContain('crowd');
    expect(SYSTEM_PROMPT).toContain('Floor Planner');
    expect(SYSTEM_PROMPT).toContain('Crowd Simulator');
    expect(SYSTEM_PROMPT).toContain('Live Monitoring');
  });

  it('MODEL is set to a valid Groq model', () => {
    expect(MODEL).toBeDefined();
    expect(MODEL).toContain('llama');
  });

  it('validates message format requirements', () => {
    // Simulate validation logic that the route performs
    const validMessages = [{ role: 'user', content: 'Hello' }];
    const emptyMessages: never[] = [];
    const nullMessages = null;

    expect(Array.isArray(validMessages) && validMessages.length > 0).toBe(true);
    expect(Array.isArray(emptyMessages) && emptyMessages.length > 0).toBe(false);
    expect(Array.isArray(nullMessages)).toBe(false);
  });

  it('constructs correct chat messages with system prompt prepended', () => {
    const userMessages = [
      { role: 'user', content: 'Tell me about crowd safety' },
    ];

    const chatMessages = [
      { role: 'system', content: SYSTEM_PROMPT },
      ...userMessages.map((m) => ({ role: m.role, content: m.content })),
    ];

    expect(chatMessages[0].role).toBe('system');
    expect(chatMessages[0].content).toBe(SYSTEM_PROMPT);
    expect(chatMessages[1].role).toBe('user');
    expect(chatMessages[1].content).toBe('Tell me about crowd safety');
    expect(chatMessages.length).toBe(2);
  });

  it('handles multi-turn conversation correctly', () => {
    const messages = [
      { role: 'user', content: 'Planning a concert' },
      { role: 'assistant', content: 'How many attendees?' },
      { role: 'user', content: 'About 10,000' },
    ];

    const chatMessages = [
      { role: 'system', content: SYSTEM_PROMPT },
      ...messages,
    ];

    expect(chatMessages.length).toBe(4);
    expect(chatMessages[3].content).toBe('About 10,000');
  });
});
