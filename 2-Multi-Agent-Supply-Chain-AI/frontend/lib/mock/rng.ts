/** Deterministic pseudo-random helpers so mock data is stable across reloads. */

export function mulberry32(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export class Rng {
  private next: () => number;

  constructor(seed: number) {
    this.next = mulberry32(seed);
  }

  float(min = 0, max = 1): number {
    return min + (max - min) * this.next();
  }

  int(min: number, max: number): number {
    return Math.floor(this.float(min, max + 1));
  }

  pick<T>(items: readonly T[]): T {
    return items[Math.floor(this.next() * items.length)];
  }

  chance(p: number): boolean {
    return this.next() < p;
  }

  /** Approximately normal via Box-Muller. */
  normal(mean: number, std: number): number {
    const u = Math.max(this.next(), 1e-9);
    const v = this.next();
    return mean + std * Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
  }

  /** Log-normal: right-skewed positive values (demand, prices). */
  logNormal(median: number, spread: number): number {
    return median * Math.exp(this.normal(0, spread));
  }
}

export const DAY_MS = 86_400_000;

/** Reference "now", rounded to the minute so repeated calls within a render agree. */
export function now(): Date {
  const d = new Date();
  d.setSeconds(0, 0);
  return d;
}

export function daysFromNow(days: number, base = now()): Date {
  return new Date(base.getTime() + days * DAY_MS);
}

export function isoDate(d: Date): string {
  return d.toISOString().slice(0, 10);
}

/** Rounds to a step (e.g. 0.1) without floating-point noise like 4.1000000000000005. */
export function round(value: number, step = 1): number {
  const decimals = Math.max(0, -Math.floor(Math.log10(step)));
  return Number((Math.round(value / step) * step).toFixed(decimals));
}

export function ceilTo(value: number, step: number): number {
  return Math.ceil(value / step) * step;
}
