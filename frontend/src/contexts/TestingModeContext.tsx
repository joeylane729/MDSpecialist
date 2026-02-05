import React, { createContext, useContext, useState, useCallback, useEffect, ReactNode } from 'react';

const STORAGE_KEY = 'mdspecialist_testing_mode';

interface TestingModeContextValue {
  testingMode: boolean;
  setTestingMode: (value: boolean) => void;
}

const TestingModeContext = createContext<TestingModeContextValue | null>(null);

export function TestingModeProvider({ children }: { children: ReactNode }) {
  const [testingMode, setTestingModeState] = useState<boolean>(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      return stored === 'true';
    } catch {
      return false;
    }
  });

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, String(testingMode));
    } catch {
      // ignore
    }
  }, [testingMode]);

  const setTestingMode = useCallback((value: boolean) => {
    setTestingModeState(value);
  }, []);

  return (
    <TestingModeContext.Provider value={{ testingMode, setTestingMode }}>
      {children}
    </TestingModeContext.Provider>
  );
}

export function useTestingMode(): TestingModeContextValue {
  const ctx = useContext(TestingModeContext);
  if (!ctx) {
    throw new Error('useTestingMode must be used within TestingModeProvider');
  }
  return ctx;
}
