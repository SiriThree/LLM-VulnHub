"use client";

import { Dispatch, SetStateAction, useEffect, useRef, useState } from "react";

type DraftControls<T> = {
  ready: boolean;
  restored: boolean;
  clearDraft: (nextValue?: T) => void;
  discardDraft: (suppressNextSave?: boolean) => void;
};

export function useSessionDraft<T>(
  key: string,
  initialValue: T,
): [T, Dispatch<SetStateAction<T>>, DraftControls<T>] {
  const initialValueRef = useRef(initialValue);
  const [value, setValue] = useState<T>(initialValue);
  const [ready, setReady] = useState(false);
  const [restored, setRestored] = useState(false);
  const skipNextSave = useRef(false);

  useEffect(() => {
    try {
      const stored = window.sessionStorage.getItem(key);
      if (stored !== null) {
        setValue(JSON.parse(stored) as T);
        setRestored(true);
      }
    } catch {
      window.sessionStorage.removeItem(key);
    } finally {
      setReady(true);
    }
  }, [key]);

  useEffect(() => {
    if (!ready) return;
    if (skipNextSave.current) {
      skipNextSave.current = false;
      return;
    }
    window.sessionStorage.setItem(key, JSON.stringify(value));
  }, [key, ready, value]);

  function clearDraft(nextValue: T = initialValueRef.current) {
    skipNextSave.current = true;
    window.sessionStorage.removeItem(key);
    setValue(nextValue);
    setRestored(false);
  }

  function discardDraft(suppressNextSave = false) {
    skipNextSave.current = suppressNextSave;
    window.sessionStorage.removeItem(key);
    setRestored(false);
  }

  return [value, setValue, { ready, restored, clearDraft, discardDraft }];
}
