import type { Session, Survey } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

export class ApiError extends Error {}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      method,
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError("Could not reach the server. Please try again in a moment.");
  }

  if (!res.ok) {
    let detail = `Error ${res.status}`;
    try {
      const data = await res.json();
      detail = data.detail ?? detail;
    } catch {
      /* keep default */
    }
    throw new ApiError(detail);
  }
  return res.json() as Promise<T>;
}

export const api = {
  getSurvey: (surveyId: string) => request<Survey>("GET", `/surveys/${surveyId}`),

  startSession: (surveyId: string, employeeId: string | null) =>
    request<Session>("POST", "/sessions", { survey_id: surveyId, employee_id: employeeId || null }),

  sendMessage: (sessionId: string, message: string) =>
    request<Session>("POST", `/sessions/${sessionId}/message`, { message }),

  deleteSession: (sessionId: string) => request<{ status: string }>("DELETE", `/sessions/${sessionId}`),
};
