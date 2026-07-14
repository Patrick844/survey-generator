export type QuestionType =
  | "single_selection"
  | "multiple_selection"
  | "distribution"
  | "number"
  | "rating"
  | "percentage"
  | "free_text";

export interface Option {
  code: string;
  label: string;
}

export interface Metadata {
  min_value?: number | null;
  max_value?: number | null;
  max_choices?: number | null;
  min_length?: number | null;
}

export interface Question {
  id: string;
  survey_id: string;
  category: string;
  question: string;
  type: QuestionType;
  options: Option[];
  metadata: Metadata;
}

export type QuestionDraft = Omit<Question, "id" | "survey_id">;

export interface BackendQuestion {
  id: string;
  category: string;
  question_type: QuestionType;
  prompt: string;
  options: string[];
  min_value: number | null;
  max_value: number | null;
  max_choices: number | null;
  min_length: number;
}

export interface SetQuestionsRequest {
  questions: BackendQuestion[];
}

export interface DistributionItem {
  option: string;
  percentage: number;
}

export type Answer = DistributionItem[] | string | string[] | number;

export interface SurveyResponse {
  question_id: string;
  survey_id: string;
  answer: Answer;
}
