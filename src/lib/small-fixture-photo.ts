import portraits from './fixture-portrait-thumbnails.json';
import crests from './fixture-crest-thumbnails.json';
import { smallTeamLogo } from './small-team-logo';

/** Only substitute known local artwork; new and external sources remain usable. */
export function smallFixturePhoto(src: string | null): string | null {
  if (!src) return src;
  const local = src.replace(/^https:\/\/ilmargine\.bet(?=\/)/, '');
  return (portraits as Record<string, string>)[local] ?? (crests as Record<string, string>)[local] ?? smallTeamLogo(local);
}
