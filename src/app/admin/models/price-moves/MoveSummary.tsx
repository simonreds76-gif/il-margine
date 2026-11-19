import React from 'react';
import styles from './MoveSummary.module.css';

/**
 * MoveSummary — one immutable, source-free alert card for a tennis price move.
 *
 * Every figure is derived from the props alone. Nothing reads the clock, so the
 * card renders identically before and after the scheduled start: it describes
 * the record as it stood at detection.
 */
export interface MoveSummaryProps {
  /** Player the price refers to (to win the match). */
  player: string;
  opponent: string;
  selection?: string;
  /** Tour / event label, e.g. "ATP Challenger · Helsinki". */
  league: string;
  /** Scheduled first serve. ISO 8601 with an explicit `Z` or UTC offset. */
  start: string;
  /** When the earlier quote was observed. ISO 8601 with `Z` or offset. */
  before: string;
  /** When the move was detected. ISO 8601 with `Z` or offset. */
  after: string;
  /** Earlier decimal price. */
  old: number;
  /** Detected decimal price. */
  new: number;
  /** Optional heading supplied by the parent, e.g. "Latest alerted price move". */
  heading?: string;
}

const MONTHS = [
  'Jan',
  'Feb',
  'Mar',
  'Apr',
  'May',
  'Jun',
  'Jul',
  'Aug',
  'Sep',
  'Oct',
  'Nov',
  'Dec',
] as const;

const MINUS = '−';
const DASH = '—';

/**
 * A timestamp must carry its own zone (`Z` or `±hh:mm`). A zoneless string would
 * be read as viewer-local time by `Date.parse`, which would silently shift a UTC
 * record, so it is rejected instead of guessed.
 */
const INSTANT =
  /^(\d{4})-(\d{2})-(\d{2})[Tt ](\d{2}):(\d{2})(?::(\d{2})(?:[.,](\d+))?)?\s?([Zz]|[+-]\d{2}(?::?\d{2})?)$/;

function parseInstant(value: unknown): number | null {
  if (typeof value !== 'string') return null;
  const match = INSTANT.exec(value.trim());
  if (!match) return null;

  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const hour = Number(match[4]);
  const minute = Number(match[5]);
  const second = match[6] === undefined ? 0 : Number(match[6]);
  const millis =
    match[7] === undefined ? 0 : Number((match[7] + '000').slice(0, 3));

  if (year < 1970 || month < 1 || month > 12 || day < 1) return null;
  if (hour > 23 || minute > 59 || second > 59) return null;

  const wallClock = Date.UTC(year, month - 1, day, hour, minute, second, millis);
  if (!Number.isFinite(wallClock)) return null;

  // Reject calendar overflow such as 31 Feb, which Date.UTC would roll forward.
  const check = new Date(wallClock);
  if (check.getUTCMonth() !== month - 1 || check.getUTCDate() !== day) {
    return null;
  }

  // The pattern guarantees a zone; the fallback only satisfies strict index typing.
  const zone = match[8] || 'Z';
  let offsetMinutes = 0;
  if (zone !== 'Z' && zone !== 'z') {
    const digits = zone.slice(1).replace(':', '');
    const zoneHours = Number(digits.slice(0, 2));
    const zoneMinutes = digits.length > 2 ? Number(digits.slice(2, 4)) : 0;
    if (zoneHours > 14 || zoneMinutes > 59) return null;
    offsetMinutes = (zone[0] === '-' ? -1 : 1) * (zoneHours * 60 + zoneMinutes);
  }

  return wallClock - offsetMinutes * 60000;
}

function parsePrice(value: unknown): number | null {
  // A decimal price is only meaningful strictly above 1.
  return typeof value === 'number' && Number.isFinite(value) && value > 1
    ? value
    : null;
}

function cleanText(value: unknown): string {
  return typeof value === 'string' ? value.replace(/\s+/g, ' ').trim() : '';
}

function pad(value: number): string {
  return value < 10 ? `0${value}` : String(value);
}

/** Two decimals, or three when the quote genuinely carries a third. */
function formatPrice(price: number): string {
  const fixed = price.toFixed(3);
  return fixed.charAt(fixed.length - 1) === '0' ? fixed.slice(0, -1) : fixed;
}

function formatPercent(probability: number): string {
  return `${(probability * 100).toFixed(1)}%`;
}

/** Signed percentage points; an extra decimal under 1 pp so small moves are not flattened. */
function formatPoints(points: number): string {
  const magnitude = Math.abs(points).toFixed(Math.abs(points) < 1 ? 2 : 1);
  if (Number(magnitude) === 0) return magnitude;
  return `${points > 0 ? '+' : MINUS}${magnitude}`;
}

/** Whole units, rounded down, so a duration is never overstated. */
function formatDuration(milliseconds: number): string {
  const total = Math.floor(milliseconds / 1000);
  if (total < 1) return 'under 1 s';
  const days = Math.floor(total / 86400);
  const hours = Math.floor((total % 86400) / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const seconds = total % 60;
  if (days > 0) return hours > 0 ? `${days} d ${hours} h` : `${days} d`;
  if (hours > 0) return minutes > 0 ? `${hours} h ${minutes} min` : `${hours} h`;
  if (minutes > 0) {
    return seconds > 0 ? `${minutes} min ${seconds} s` : `${minutes} min`;
  }
  return `${seconds} s`;
}

function renderInstant(
  instant: number | null,
  withSeconds: boolean,
): React.ReactElement {
  if (instant === null) {
    return <span className={styles.missing}>Time unavailable</span>;
  }
  const date = new Date(instant);
  const day = `${date.getUTCDate()} ${MONTHS[date.getUTCMonth()]} ${date.getUTCFullYear()}`;
  const clock = `${pad(date.getUTCHours())}:${pad(date.getUTCMinutes())}${
    withSeconds ? `:${pad(date.getUTCSeconds())}` : ''
  } UTC`;
  return (
    <time className={styles.instant} dateTime={date.toISOString()}>
      <span className={styles.instantPart}>{day}</span>{' '}
      <span className={styles.instantPart}>{clock}</span>
    </time>
  );
}

export function MoveSummary(props: MoveSummaryProps): React.ReactElement {
  const heading = cleanText(props.heading);
  const player = cleanText(props.player);
  const opponent = cleanText(props.opponent);
  const league = cleanText(props.league);

  const earlierPrice = parsePrice(props.old);
  const detectedPrice = parsePrice(props.new);
  const earlierAt = parseInstant(props.before);
  const detectedAt = parseInstant(props.after);
  const startAt = parseInstant(props.start);

  const hasBothPrices = earlierPrice !== null && detectedPrice !== null;

  // Price-implied win chance, before margin adjustment.
  const earlierChance = earlierPrice === null ? null : 1 / earlierPrice;
  const detectedChance = detectedPrice === null ? null : 1 / detectedPrice;
  const points =
    earlierPrice !== null && detectedPrice !== null
      ? 100 * (1 / detectedPrice - 1 / earlierPrice)
      : null;

  // Actual observed interval between the two quotes.
  const interval =
    earlierAt !== null && detectedAt !== null ? detectedAt - earlierAt : null;

  // Scheduled first serve relative to detection. Never relative to "now".
  const toServe =
    startAt !== null && detectedAt !== null ? startAt - detectedAt : null;

  let moveLabel = 'Price move';
  if (earlierPrice !== null && detectedPrice !== null) {
    if (detectedPrice < earlierPrice) moveLabel = 'Price drop';
    else if (detectedPrice > earlierPrice) moveLabel = 'Price rise';
    else moveLabel = 'No price change';
  }

  let intervalText: string;
  if (interval === null) {
    intervalText = 'Observed interval unavailable';
  } else if (interval > 0) {
    intervalText = `over ${formatDuration(interval)} observed`;
  } else if (interval === 0) {
    intervalText = 'Observed interval unavailable: both quotes share one timestamp';
  } else {
    intervalText = 'Observed interval unavailable: quote timestamps are out of order';
  }

  let serveValue: string;
  let serveNote: string | null = null;
  if (toServe === null) {
    serveValue = 'Unavailable';
  } else if (toServe > 0) {
    serveValue = formatDuration(toServe);
  } else if (toServe === 0) {
    serveValue = 'None';
    serveNote = 'Detected at the scheduled time. Actual start is not recorded here.';
  } else {
    serveValue = `Passed ${formatDuration(-toServe)} earlier`;
    serveNote =
      'Detected after the scheduled time. Actual start is not recorded here.';
  }

  const problems: string[] = [];
  if (!player) problems.push('player');
  if (!opponent) problems.push('opponent');
  if (!league) problems.push('event');
  if (earlierPrice === null) problems.push('earlier quote');
  if (detectedPrice === null) problems.push('detected price');
  if (earlierAt === null) problems.push('earlier quote time');
  if (detectedAt === null) problems.push('detection time');
  if (startAt === null) problems.push('scheduled first serve');
  if (interval !== null && interval <= 0) problems.push('quote time order');

  const MatchHeading = heading ? 'h3' : 'h2';

  return (
    <article className={styles.card}>
      <header className={styles.header}>
        {heading ? <h2 className={styles.heading}>{heading}</h2> : null}
        <p className={styles.kicker}>
          <span className={styles.tag}>{moveLabel}</span>
          {league ? <span className={styles.league}>{league}</span> : null}
        </p>
        <MatchHeading className={styles.match}>
          <span className={player ? styles.player : styles.missing}>
            {player || 'Player unavailable'}
          </span>
          <span className={styles.versus}> v </span>
          <span className={opponent ? styles.opponent : styles.missing}>
            {opponent || 'Opponent unavailable'}
          </span>
        </MatchHeading>
        <p className={styles.subject}>
          {props.selection ? 'Decimal price for ' + props.selection : 'Decimal price for ' + (player || 'the listed player') + ' to win'}
        </p>
      </header>

      <dl className={styles.figures}>
        <div className={`${styles.group} ${styles.earlier}`}>
          <dt className={styles.term}>Earlier quote</dt>
          <dd className={styles.price}>
            {earlierPrice === null ? (
              <span className={styles.missing}>{DASH}</span>
            ) : (
              formatPrice(earlierPrice)
            )}
          </dd>
          <dd className={styles.when}>{renderInstant(earlierAt, true)}</dd>
        </div>

        <div className={`${styles.group} ${styles.detected}`}>
          <dt className={styles.term}>Detected price</dt>
          <dd className={styles.price}>
            {detectedPrice === null ? (
              <span className={styles.missing}>{DASH}</span>
            ) : (
              formatPrice(detectedPrice)
            )}
          </dd>
          <dd className={styles.when}>{renderInstant(detectedAt, true)}</dd>
        </div>

        <div className={`${styles.group} ${styles.chance}`}>
          <dt className={styles.term}>
            Change in price-implied chance
            <span className={styles.qualifier}>
              price-implied, before margin adjustment
            </span>
          </dt>
          <dd className={styles.points}>
            {points === null ? (
              <span className={styles.missing}>{DASH}</span>
            ) : (
              <>
                {formatPoints(points)}
                <abbr className={styles.unit} title="percentage points">
                  pp
                </abbr>
              </>
            )}
          </dd>
          <dd className={styles.detail}>
            {hasBothPrices && earlierChance !== null && detectedChance !== null ? (
              <span className={styles.range}>
                {formatPercent(earlierChance)}
                <span aria-hidden="true"> → </span>
                <span className={styles.srOnly}> to </span>
                {formatPercent(detectedChance)}
              </span>
            ) : (
              <span className={styles.range}>Needs both prices</span>
            )}{' '}
            <span className={styles.interval}>{intervalText}</span>
          </dd>
        </div>

        <div className={`${styles.group} ${styles.serve}`}>
          <dt className={styles.term}>
            Time to scheduled first serve, at detection
          </dt>
          <dd className={toServe === null ? styles.serveMissing : styles.serveValue}>
            {serveValue}
          </dd>
          <dd className={styles.detail}>
            {startAt === null ? (
              'Scheduled first serve not available'
            ) : (
              <>Scheduled {renderInstant(startAt, false)}</>
            )}
            {serveNote ? <span className={styles.note}> {serveNote}</span> : null}
          </dd>
        </div>
      </dl>

      {problems.length > 0 ? (
        <p className={styles.notice}>
          Incomplete record. Missing or invalid: {problems.join(', ')}. Nothing
          has been estimated.
        </p>
      ) : null}

      <p className={styles.footnote}>
        All figures as recorded at detection. This card does not update.
      </p>
    </article>
  );
}

export default MoveSummary;
