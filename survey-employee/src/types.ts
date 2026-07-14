export type QuestionType =
  | "single_selection"
  | "multiple_selection"
  | "distribution"
  | "number"
  | "rating"
  | "percentage"
  | "free_text";

export interface PublicQuestion {
  id: string;
  number: number;
  total: number;
  category: string;
  question_type: QuestionType;
  prompt: string;
  options: string[];
  min_value: number | null;
  max_value: number | null;
  max_choices: number | null;
  min_length: number;
}

export interface ChatMessage {
  role: "assistant" | "user";
  content: string;
}

export interface Session {
  session_id: string;
  completed: boolean;
  progress: number;
  total_questions: number;
  assistant_message: string;
  current_question: PublicQuestion | null;
  chat_history: ChatMessage[];
  responses: Record<string, unknown>;
}

export interface Survey {
  survey_id: string;
  title: string | null;
  company_name: string | null;
  total_questions: number;
  created_at: string;
  survey_url: string;
}
