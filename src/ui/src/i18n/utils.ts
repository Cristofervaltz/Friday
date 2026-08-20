// string manipulation and lookup helpers for i18n
import type { TranslationParams } from './types.ts';

// handy helper to dig into nested dict paths like chat.queue_header
export function getNestedValue(obj: any, path: string): string | undefined {
  if (!obj || typeof obj !== 'object') return undefined;
  
  // check direct property first in case flat keys were used
  if (path in obj && typeof obj[path] === 'string') {
    return obj[path];
  }
  
  const parts = path.split('.');
  let current = obj;
  for (const part of parts) {
    if (current && typeof current === 'object' && part in current) {
      current = current[part];
    } else {
      return undefined;
    }
  }
  return typeof current === 'string' ? current : undefined;
}

// replace {token} with runtime param values
export function interpolate(text: string, params?: TranslationParams): string {
  if (!params) return text;
  return text.replace(/\{(\w+)\}/g, (match, key) => {
    return key in params ? String(params[key]) : match;
  });
}
