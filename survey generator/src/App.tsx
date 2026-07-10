import { useState } from "react";
import type { Question, QuestionDraft } from "./types/models";
import Header from "./components/Header";
import QuestionList from "./components/QuestionList";
import QuestionForm from "./components/QuestionForm";
import GenerateChatbotModal from "./components/GenerateChatbotModal";
import AddQuestionChoice from "./components/AddQuestionChoice";
import QuestionLibrary from "./components/QuestionLibrary";
import "./App.css";

const MAX_QUESTIONS = 4;
const SURVEY_ID = "employee-survey-2025";

function emptyForm(): QuestionDraft {
  return {
    category: "",
    question: "",
    type: "single_selection",
    options: [
      { code: "A", label: "" },
      { code: "B", label: "" },
    ],
    metadata: {},
  };
}

export default function App() {
  const [questions, setQuestions] = useState<Question[]>([]);
  const [panelOpen, setPanelOpen] = useState(false);
  const [showExport, setShowExport] = useState(false);
  const [choiceOpen, setChoiceOpen] = useState(false);
  const [libraryOpen, setLibraryOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<QuestionDraft>(emptyForm());

  // "Add Question" first asks how: blank or from the 300-item library.
  const openAdd = () => setChoiceOpen(true);

  const openBlankForm = () => {
    setChoiceOpen(false);
    setEditingId(null);
    setForm(emptyForm());
    setPanelOpen(true);
  };

  const openLibrary = () => {
    setChoiceOpen(false);
    setLibraryOpen(true);
  };

  // Appends a question as-is (used by the locked library flow). Uses the
  // functional updater so the id and the MAX cap read the latest list.
  const addQuestionFromDraft = (draft: QuestionDraft) => {
    setQuestions((prev) => {
      if (prev.length >= MAX_QUESTIONS) return prev;
      const newQ: Question = {
        id: `q${String(prev.length + 1).padStart(2, "0")}`,
        survey_id: SURVEY_ID,
        ...draft,
      };
      return [...prev, newQ];
    });
  };

  // Library picks are locked: selecting adds the question as-is, no edit step.
  // The library stays open so several can be picked in a row.
  const selectFromLibrary = (draft: QuestionDraft) => {
    addQuestionFromDraft(draft);
  };

  const openEdit = (q: Question) => {
    setEditingId(q.id);
    setForm({
      category: q.category,
      question: q.question,
      type: q.type,
      options: (q.options ?? []).map((o) => ({ ...o })),
      metadata: { ...(q.metadata ?? {}) },
    });
    setPanelOpen(true);
  };

  const closePanel = () => {
    setPanelOpen(false);
    setEditingId(null);
  };

  const saveQuestion = () => {
    if (editingId) {
      setQuestions((prev) =>
        prev.map((q) => (q.id === editingId ? { ...q, ...form } : q))
      );
    } else {
      const newQ: Question = {
        id: `q${String(questions.length + 1).padStart(2, "0")}`,
        survey_id: SURVEY_ID,
        ...form,
      };
      setQuestions((prev) => [...prev, newQ]);
    }
    closePanel();
  };

  const deleteQuestion = (id: string) =>
    setQuestions((prev) => prev.filter((q) => q.id !== id));

  const moveQuestion = (id: string, dir: -1 | 1) => {
    setQuestions((prev) => {
      const idx = prev.findIndex((q) => q.id === id);
      const next = idx + dir;
      if (next < 0 || next >= prev.length) return prev;
      const arr = [...prev];
      [arr[idx], arr[next]] = [arr[next], arr[idx]];
      return arr;
    });
  };

  const canAdd = questions.length < MAX_QUESTIONS;
  const isReady = questions.length === MAX_QUESTIONS;

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-blue-100">
      <Header
        count={questions.length}
        max={MAX_QUESTIONS}
        onAdd={openAdd}
        onGenerate={() => setShowExport(true)}
        canAdd={canAdd}
        isReady={isReady}
      />

      <main className="max-w-4xl mx-auto px-4 py-8">
        <QuestionList
          questions={questions}
          onEdit={openEdit}
          onDelete={deleteQuestion}
          onMove={moveQuestion}
          onAdd={openAdd}
          canAdd={canAdd}
        />
      </main>

      {panelOpen && (
        <>
          <div className="fixed inset-0 bg-black/30 backdrop-blur-sm z-40" onClick={closePanel} />
          <QuestionForm
            form={form}
            setForm={setForm}
            onSave={saveQuestion}
            onClose={closePanel}
            isEditing={!!editingId}
          />
        </>
      )}

      {choiceOpen && (
        <AddQuestionChoice
          onBlank={openBlankForm}
          onLibrary={openLibrary}
          onClose={() => setChoiceOpen(false)}
        />
      )}

      {libraryOpen && (
        <QuestionLibrary
          usedStatements={questions.map((q) => q.question)}
          canAdd={canAdd}
          count={questions.length}
          max={MAX_QUESTIONS}
          onSelect={selectFromLibrary}
          onClose={() => setLibraryOpen(false)}
        />
      )}

      {showExport && (
        <GenerateChatbotModal
          questions={questions}
          onClose={() => setShowExport(false)}
        />
      )}
    </div>
  );
}
