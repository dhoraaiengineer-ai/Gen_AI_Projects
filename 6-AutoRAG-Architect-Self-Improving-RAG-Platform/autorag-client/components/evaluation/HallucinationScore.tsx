"use client";

import { ShieldCheck, ShieldAlert } from "lucide-react";

import { FAILURE_CODE_INFO, isFailureCode } from "@/types";

interface HallucinationScoreProps {
  passed: boolean;
  failureTaxonomy: string[];
}

export function HallucinationScore({ passed, failureTaxonomy }: HallucinationScoreProps) {
  const Icon = passed ? ShieldCheck : ShieldAlert;

  return (
    <div
      className={`rounded-lg border p-4 ${
        passed
          ? "border-emerald-200 bg-emerald-50"
          : "border-rose-200 bg-rose-50"
      }`}
    >
      <div className="flex items-center gap-3">
        <Icon
          className={`h-8 w-8 shrink-0 ${passed ? "text-emerald-600" : "text-rose-600"}`}
          aria-hidden="true"
        />
        <div>
          <p
            className={`text-sm font-semibold ${
              passed ? "text-emerald-800" : "text-rose-800"
            }`}
          >
            Adversarial Benchmark
          </p>
          <p
            className={`text-xs ${passed ? "text-emerald-700/80" : "text-rose-700/80"}`}
          >
            {passed
              ? "Passed — no hallucinations detected"
              : "Failed — fabricated answers detected"}
          </p>
        </div>
        <span
          className={`ml-auto shrink-0 rounded-full px-3 py-1 text-xs font-bold ${
            passed
              ? "bg-emerald-100 text-emerald-800"
              : "bg-rose-100 text-rose-800"
          }`}
        >
          {passed ? "PASS" : "FAIL"}
        </span>
      </div>

      {!passed && failureTaxonomy.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {failureTaxonomy.map((code) => (
            <span
              key={code}
              className="rounded-full border border-rose-200 bg-rose-100 px-2.5 py-0.5 text-[11px] text-rose-700"
            >
              {code}: {isFailureCode(code) ? FAILURE_CODE_INFO[code].label : code}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
