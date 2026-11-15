export function resolveTennisPortrait(name: string, rows?: { name: string; src: string | null }[]): { name: string; src: string | null; position?: string; scale?: number } | null;

export function safeTennisPortraitSource(src: string | null | undefined, sha256?: string): string | null;
