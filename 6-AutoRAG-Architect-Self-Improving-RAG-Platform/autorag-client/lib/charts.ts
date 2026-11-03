import type { PipelineWithRun } from "@/types";

export const processPipelineDataForCharts = (pipelines: PipelineWithRun[]) => {
  if (!pipelines) {
    return [];
  }

  // Aggregate data into time buckets (e.g., 5-minute intervals)
  const timeBuckets = new Map<string, { volume: number; scores: number[]; count: number }>();
  const now = new Date();
  const lastHour = new Date(now.getTime() - 60 * 60 * 1000);

  pipelines.forEach((p) => {
    const createdAt = new Date(p.created_at);
    if (createdAt < lastHour) {
      return;
    }

    const minutes = createdAt.getMinutes();
    const bucket = Math.floor(minutes / 5) * 5;
    const timeKey = `${createdAt.getHours()}:${bucket.toString().padStart(2, "0")}`;

    if (!timeBuckets.has(timeKey)) {
      timeBuckets.set(timeKey, { volume: 0, scores: [], count: 0 });
    }

    const bucketData = timeBuckets.get(timeKey)!;
    bucketData.volume += 1;
    // unified_score is null when the run never reached Evaluator, but a real
    // score of exactly 0 must still count -- a truthy check would silently
    // drop it (same bug class as lib/kpi.ts's 13-Jul-2026 fix).
    if (p.latest_run?.unified_score !== null && p.latest_run?.unified_score !== undefined) {
      bucketData.scores.push(p.latest_run.unified_score);
    }
    bucketData.count += 1;
  });

  // Convert map to array and calculate average score
  const chartData = Array.from(timeBuckets.entries()).map(([time, data]) => {
    const avgScore = data.scores.length > 0 ? data.scores.reduce((a, b) => a + b, 0) / data.scores.length : 0;
    return {
      time,
      volume: data.volume,
      score: avgScore,
    };
  });

  // Sort by time
  return chartData.sort((a, b) => (a.time > b.time ? 1 : -1));
};