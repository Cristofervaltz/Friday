// react context definition and default state helpers
import { createContext } from 'react';
import type { Language, I18nContextType } from './types.ts';

// key for saving user pref in localstorage
export const STORAGE_KEY = 'friday_language';

// get saved lang from localStorage or fallback to en
export const getInitialLanguage = (): Language => {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === 'en' || saved === 'ru') {
      return saved;
    }
  } catch {
    // storage might fail in restricted envs
  }
  return 'en';
};

// context instance
export const I18nContext = createContext<I18nContextType | null>(null);
