'use client';

import Image from 'next/image';
import { useState, type ReactNode } from 'react';
import styles from './FixturePhoto.module.css';

type Props = { src: string | null; className: string; size: number; fallback: ReactNode };

// A new source remounts its loading state, so a previous failed image cannot hide it.
export default function FixturePhoto(props: Props) {
  const src = props.src?.replace(/^https:\/\/ilmargine\.bet\//, '/') ?? null;
  return <PhotoState key={src} {...props} src={src} />;
}

function PhotoState({ src, className, size, fallback }: Props) {
  const [state, setState] = useState<'loading' | 'ready' | 'failed'>('loading');
  return <span className={`${className} ${styles.photo}`}>
    {state !== 'ready' && <span className={styles.fallback} aria-hidden="true">{fallback}</span>}
    {src && state !== 'failed' && <Image src={src} alt="" width={size} height={size}
      unoptimized loading="eager" className={styles.image} style={{ opacity: state === 'ready' ? 1 : 0 }}
      onLoad={() => setState('ready')} onError={() => setState('failed')} />}
  </span>;
}
