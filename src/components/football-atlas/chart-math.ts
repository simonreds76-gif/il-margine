/** Distance below the highest preceding cumulative profit; zero means at a high. */
export function underwater(curve: number[]) {
    let peak = 0;
    return curve.map(value => { peak = Math.max(peak, value); return value - peak; });
}

/** Round, zero-inclusive unit ticks, with a finite domain for an empty/flat path. */
export function unitScale(values: number[]) {
    const low = Math.min(0, ...values), high = Math.max(0, ...values);
    const raw = Math.max(1, high - low) / 4;
    const magnitude = 10 ** Math.floor(Math.log10(raw));
    const step = ([1, 2, 2.5, 5, 10].find(n => n * magnitude >= raw) ?? 10) * magnitude;
    const min = Math.floor(low / step) * step;
    const max = high === low ? min + step * 4 : Math.ceil(high / step) * step;
    const ticks = Array.from({ length: Math.round((max - min) / step) + 1 }, (_, i) => Number((min + i * step).toPrecision(12)));
    return { min, max, ticks };
}
