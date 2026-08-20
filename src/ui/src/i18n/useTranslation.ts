// hook for components to easily consume translations
import { useContext } from 'react';
import type { I18nContextType, TranslationParams } from './types.ts';
import { I18nContext } from './context.ts';
import { translations } from './translations.ts';
import { getNestedValue, interpolate } from './utils.ts';

// custom hook for components to use translations easily
export function useTranslation(): I18nContextType {
  const context = useContext(I18nContext);
  if (!context) {
    // safe fallback so components or tests never crash if rendered outside provider
    return {
      language: 'en',
      setLanguage: () => {},
      t: (key: string, params?: TranslationParams) => {
        const raw = getNestedValue(translations.en, key) || key;
        return interpolate(raw, params);
      },
    };
  }
  return context;
}
