import React, { useState, useEffect, useCallback, useMemo, type ReactNode } from 'react';
import type { Language, TranslationParams } from './types.ts';
import { STORAGE_KEY, getInitialLanguage, I18nContext } from './context.ts';
import { translations } from './translations.ts';
import { getNestedValue, interpolate } from './utils.ts';

export interface I18nProviderProps {
  children: ReactNode;
  initialLanguage?: Language;
}

// provider component that wraps the react app tree
export const I18nProvider: React.FC<I18nProviderProps> = ({ children, initialLanguage }) => {
  const [language, setLanguageState] = useState<Language>(() => initialLanguage || getInitialLanguage());

  // sync html document lang tag
  useEffect(() => {
    if (typeof document !== 'undefined') {
      document.documentElement.lang = language;
    }
  }, [language]);

  // language switch handler that also persists to localStorage
  const setLanguage = useCallback((newLang: Language) => {
    setLanguageState(newLang);
    try {
      localStorage.setItem(STORAGE_KEY, newLang);
    } catch {
      // storage access failed
    }
    if (typeof document !== 'undefined') {
      document.documentElement.lang = newLang;
    }
  }, []);

  // lookup key, fallback to en, then fallback to key itself, then interpolate
  const t = useCallback(
    (key: string, params?: TranslationParams): string => {
      // 1. try target language
      let raw = getNestedValue(translations[language], key);
      
      // 2. fallback to english if missing in current lang
      if (raw === undefined && language !== 'en') {
        raw = getNestedValue(translations.en, key);
      }

      // 3. fallback to key literal if completely missing
      if (raw === undefined) {
        raw = key;
      }

      // 4. interpolate tokens like {count}
      return interpolate(raw, params);
    },
    [language]
  );

  // memoize context value object so consumers don't rerender unnecessarily
  const contextValue = useMemo(() => ({
    language,
    setLanguage,
    t,
  }), [language, setLanguage, t]);

  return (
    <I18nContext.Provider value={contextValue}>
      {children}
    </I18nContext.Provider>
  );
};
