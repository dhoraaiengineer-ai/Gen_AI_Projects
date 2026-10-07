import type { DemandForecast, ForecastHorizon, ForecastPoint } from "@/types";
import { inventoryItem } from "./inventory";
import { DAY_MS, isoDate, now, Rng } from "./rng";

/** Days of forecast and days of visible history for each horizon. */
const HORIZONS: Record<ForecastHorizon, { forecast: number; history: number }> = {
  "7d": { forecast: 7, history: 28 },
  "30d": { forecast: 30, history: 90 },
  "90d": { forecast: 90, history: 180 },
  "6m": { forecast: 182, history: 270 },
  "1y": { forecast: 365, history: 365 },
};

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
// Weekday seasonality (B2B pattern: weekday peaks, weekend troughs).
const WEEKDAY_INDEX = [1.08, 1.12, 1.1, 1.06, 1.04, 0.82, 0.78];

function hashSku(sku: string): number {
  let h = 0;
  for (const ch of sku) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  return h;
}

function weekdayIndex(d: Date): number {
  return WEEKDAY_INDEX[(d.getDay() + 6) % 7];
}

/**
 * Holt's linear trend with a multiplicative weekday index and an annual cycle — the same family of
 * methods used by app/services/forecasting.py. Confidence band widens with √h.
 */
export function demandForecast(sku: string, horizon: ForecastHorizon): DemandForecast {
  const item = inventoryItem(sku);
  const base = item?.dailyDemand ?? 50;
  const rng = new Rng(hashSku(sku));
  const { forecast: fDays, history: hDays } = HORIZONS[horizon];
  const today = now();
  const growthPerDay = sku === "SKU-100" ? 0.0011 : rng.float(-0.0006, 0.0012);
  const annualAmp = rng.float(0.05, 0.14);

  const rawLevel = (t: number) => base * (1 + growthPerDay * t) * (1 + annualAmp * Math.sin((2 * Math.PI * (t + 40)) / 365));
  // Calibrate so the 30-day forecast equals the inventory record's forecast30d — every page agrees on one number.
  let raw30 = 0;
  for (let h = 0; h < 30; h++) raw30 += rawLevel(h) * weekdayIndex(new Date(today.getTime() + h * DAY_MS));
  const scale = item ? item.forecast30d / raw30 : 1;
  const level = (t: number) => rawLevel(t) * scale;

  const points: ForecastPoint[] = [];
  const actuals: number[] = [];
  for (let t = -hDays; t < 0; t++) {
    const d = new Date(today.getTime() + t * DAY_MS);
    const actual = Math.max(0, Math.round(level(t) * weekdayIndex(d) + rng.normal(0, base * 0.12)));
    actuals.push(actual);
    points.push({ date: isoDate(d), actual });
  }
  const residualStd = base * 0.12;
  let total = 0;
  for (let h = 0; h < fDays; h++) {
    const d = new Date(today.getTime() + h * DAY_MS);
    const forecast = Math.round(level(h) * weekdayIndex(d));
    const band = 1.28 * residualStd * Math.sqrt(1 + h / 7);
    total += forecast;
    points.push({ date: isoDate(d), forecast, lower: Math.max(0, Math.round(forecast - band)), upper: Math.round(forecast + band) });
  }
  // Join the two series visually at the boundary.
  const lastActual = points[hDays - 1];
  lastActual.forecast = lastActual.actual;
  lastActual.lower = lastActual.actual;
  lastActual.upper = lastActual.actual;

  const firstHalf = actuals.slice(0, Math.floor(actuals.length / 2));
  const secondHalf = actuals.slice(Math.floor(actuals.length / 2));
  const mean = (xs: number[]) => xs.reduce((s, x) => s + x, 0) / Math.max(xs.length, 1);
  const pctChange = ((mean(secondHalf) - mean(firstHalf)) / Math.max(mean(firstHalf), 1)) * 100;
  const mape = sku === "SKU-100" ? 6.8 : Math.round(rng.float(5.5, 14) * 10) / 10;

  return {
    sku,
    name: item?.name ?? sku,
    horizon,
    method: "Holt linear trend + weekday seasonality",
    points,
    totalForecast: total,
    dailyMean: Math.round(total / fDays),
    trend: { direction: pctChange > 2 ? "up" : pctChange < -2 ? "down" : "flat", pctChange: Math.round(pctChange * 10) / 10 },
    seasonality: {
      detected: true,
      periodDays: 7,
      weekdayIndex: WEEKDAYS.map((day, i) => ({ day, index: WEEKDAY_INDEX[i] })),
    },
    accuracy: { mape, bias: Math.round(rng.float(-2.5, 2.5) * 10) / 10 },
    confidence: mape < 8 ? "high" : mape < 12 ? "medium" : "low",
    drivers:
      sku === "SKU-100"
        ? [
            `Demand up ${Math.round(pctChange)}% over the period, driven by the EV charger product line`,
            "Weekday ordering pattern — Tuesday peaks, weekend troughs",
            "Seasonal uplift expected ahead of the Q4 install season",
          ]
        : [
            pctChange > 2 ? `Demand trending up ${pctChange.toFixed(1)}% over the period` : pctChange < -2 ? `Demand trending down ${Math.abs(pctChange).toFixed(1)}% over the period` : "Stable demand with no significant trend",
            "Weekday ordering pattern detected (7-day cycle)",
          ],
  };
}
