import { getImageProps } from 'next/image';
import { smallFixturePhoto } from './small-fixture-photo';

/** Use cached, size-appropriate copies; unknown hosts retain the original path. */
export function smallTipPhoto(src: string | null | undefined, pixels: 32 | 48 | 80): string | null {
  if (!src) return null;
  const local = src.replace(/^https:\/\/ilmargine\.bet(?=\/)/, '');
  const compact = smallFixturePhoto(local);
  if (compact !== local && pixels <= 48) return compact;
  // The identity route redirects: optimise only after it has resolved the exact
  // player, rather than asking the image optimiser to decode a redirect body.
  if (/^\/api\/tip-portrait\/[1-9]\d*\?v=[a-f0-9]+$/.test(local)) {
    return `${local}&thumb=${pixels === 32 ? 64 : pixels === 48 ? 96 : 256}`;
  }
  const supported = /^https:\/\/images\.fotmob\.com\/image_resources\/playerimages\/\d+\.png$/.test(src)
    || /^https:\/\/images\.wimbledon\.com\/wide_nobg\/[a-z0-9]+\.png$/i.test(src)
    || /^https:\/\/a\.espncdn\.com\/i\/headshots\/tennis\/players\/full\/\d+\.png$/.test(src)
    || /^\/players\/tennis\/[a-z0-9-]+\.(?:png|jpg|webp)$/i.test(local);
  return supported ? getImageProps({ src: local, alt: '', width: pixels, height: pixels }).props.src : src;
}
