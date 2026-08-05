"use client";
/**
 * Session state: the chosen industry and its intake answers.
 *
 * sessionStorage, deliberately. The free tier has no persistence by design, and
 * a state library would be a dependency for two values that already have a
 * browser-native home. Clearing the tab clears the assessment, which matches
 * what the product promises.
 */
import { useCallback, useEffect, useState } from "react";

const INDUSTRY_KEY = "avenoir.industry";
const ANSWERS_KEY = "avenoir.answers";

export function readIndustry(): string | null {
  if (typeof window === "undefined") return null;
  return window.sessionStorage.getItem(INDUSTRY_KEY);
}

export function readAnswers(): Record<string, any> {
  if (typeof window === "undefined") return {};
  try {
    return JSON.parse(window.sessionStorage.getItem(ANSWERS_KEY) || "{}");
  } catch {
    return {};
  }
}

export function writeIndustry(id: string) {
  window.sessionStorage.setItem(INDUSTRY_KEY, id);
}

export function writeAnswers(a: Record<string, any>) {
  window.sessionStorage.setItem(ANSWERS_KEY, JSON.stringify(a));
}

/** Changing industry discards intake, so callers must confirm first. */
export function clearAnswers() {
  window.sessionStorage.removeItem(ANSWERS_KEY);
}

export function hasAnswers(): boolean {
  return Object.keys(readAnswers()).length > 0;
}

export function useSession() {
  const [industry, setIndustryState] = useState<string | null>(null);
  const [answers, setAnswersState] = useState<Record<string, any>>({});
  const [ready, setReady] = useState(false);

  useEffect(() => {
    setIndustryState(readIndustry());
    setAnswersState(readAnswers());
    setReady(true);
  }, []);

  const setIndustry = useCallback((id: string, { keepAnswers = false } = {}) => {
    writeIndustry(id);
    setIndustryState(id);
    if (!keepAnswers) {
      clearAnswers();
      setAnswersState({});
    }
  }, []);

  const setAnswers = useCallback((a: Record<string, any>) => {
    writeAnswers(a);
    setAnswersState(a);
  }, []);

  return { industry, answers, ready, setIndustry, setAnswers };
}
