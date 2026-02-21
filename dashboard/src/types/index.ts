export interface Message {
  role: 'user' | 'assistant' | 'system';
  content: string;
}

export interface ChatRequest {
  messages: Message[];
}

export interface StreamChunk {
  content: string;
}

export interface ServiceStatus {
  name: string;
  url: string;
  status: 'online' | 'offline' | 'checking';
  latency?: number;
}

export interface EventSetup {
  eventName: string;
  eventType: string;
  expectedAttendance: number;
  maxCapacity: number;
  venueType: 'indoor' | 'outdoor' | '';
  hasFloorPlan: boolean;
  floorPlanPath?: string;
}

export interface Suggestion {
  title: string;
  description: string;
  prompt: string;
  icon: string;
}

export interface NavItem {
  label: string;
  href: string;
  icon: string;
  badge?: string;
}
