export interface ToolActionItem {
  tool: string;
  input?: Record<string, unknown> | string;
  output?: Record<string, unknown> | string;
  status?: "pending" | "running" | "completed" | "refused";
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: string;
  model_used?: string;
  model_display?: string;
  route_reason?: string;
  tool_actions?: ToolActionItem[];
  skills_used?: string[];
  is_swarm?: boolean;
  error?: boolean;
}

export interface ChatSessionItem {
  id: string;
  title: string;
  created_at?: string;
  updated_at?: string;
  turn_count?: number;
}
