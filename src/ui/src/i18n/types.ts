// supported languages for friday app
export type Language = 'en' | 'ru';

// param bag for interpolating tokens like {count}
export type TranslationParams = Record<string, string | number>;

// translation func signature
export type TFunction = (key: string, params?: TranslationParams) => string;

// context contract for react tree
export interface I18nContextType {
  language: Language;
  setLanguage: (lang: Language) => void;
  t: TFunction;
}

// translation dictionary shape
export type TranslationDict = Record<string, any>;
