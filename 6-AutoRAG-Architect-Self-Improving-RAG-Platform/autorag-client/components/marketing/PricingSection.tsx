"use client";

import { useState } from "react";
import { CheckCircle2, XCircle, Sparkles, ArrowRight, GraduationCap } from "lucide-react";

interface Plan {
  id: string;
  name: string;
  bestFor: string;
  priceMonthly: string;
  priceYearly: string;
  popular?: boolean;
  ctaText: string;
  included: string[];
  notIncluded?: string[];
}

const PLANS: Plan[] = [
  {
    id: "community",
    name: "Community",
    bestFor: "Students & Learning",
    priceMonthly: "Free",
    priceYearly: "Free",
    ctaText: "Start Free",
    included: [
      "1 Workspace",
      "Up to 2 Pipelines",
      "200 Documents",
      "Basic RAG Evaluation",
      "Local Deployment",
      "Community Support",
      "Documentation & Tutorials",
    ],
    notIncluded: ["Team collaboration", "SSO", "MLflow", "Enterprise connectors", "Audit Logs", "Autonomous Optimization Agents"],
  },
  {
    id: "professional",
    name: "Professional",
    bestFor: "Individual Developers",
    priceMonthly: "₹2,499",
    priceYearly: "₹23,990",
    ctaText: "Start 14-Day Trial",
    included: [
      "Everything in Community",
      "Unlimited Pipelines",
      "Up to 5,000 Documents",
      "Hybrid Retrieval",
      "Retrieval Explorer",
      "Evaluation Center",
      "Experiments",
      "Pipeline History",
      "Deployment Center",
      "Email Support",
    ],
  },
  {
    id: "team",
    name: "Team",
    bestFor: "Startups & SMBs",
    priceMonthly: "₹7,999",
    priceYearly: "₹76,990",
    popular: true,
    ctaText: "Start Team Trial",
    included: [
      "Everything in Professional",
      "Up to 10 Team Members",
      "Shared Workspaces",
      "Role-Based Access",
      "API Keys",
      "Knowledge Collections",
      "GitHub Integration",
      "Slack Notifications",
      "Usage Analytics",
      "Priority Support",
    ],
  },
  {
    id: "business",
    name: "Business",
    bestFor: "Growing Enterprises",
    priceMonthly: "₹24,999",
    priceYearly: "₹2,39,990",
    ctaText: "Request Demo",
    included: [
      "Everything in Team",
      "Unlimited Team Members",
      "Unlimited Pipelines",
      "Observer",
      "Diagnoser",
      "Improver",
      "Pipeline Evolution",
      "MLflow Integration",
      "Audit Logs",
      "Single Sign-On (SSO)",
      "Advanced Security",
      "Priority SLA Support",
    ],
  },
  {
    id: "enterprise",
    name: "Enterprise",
    bestFor: "Large Organizations",
    priceMonthly: "Custom Quote",
    priceYearly: "Custom Quote",
    ctaText: "Contact Sales",
    included: [
      "Unlimited Everything",
      "Dedicated Infrastructure",
      "On-Premise Deployment",
      "Private VPC",
      "Air-Gapped Deployment",
      "Enterprise SLA",
      "Architecture Consulting",
      "Custom Integrations",
      "Dedicated Customer Success Manager",
      "Training & Onboarding",
      "24×7 Premium Support",
    ],
  },
];

const COMPARISON_ROWS: { feature: string; values: [string, string, string, string, string] }[] = [
  { feature: "Pipelines", values: ["2", "Unlimited", "Unlimited", "Unlimited", "Unlimited"] },
  { feature: "Documents", values: ["200", "5,000", "25,000", "Unlimited", "Unlimited"] },
  { feature: "Team Members", values: ["1", "1", "10", "Unlimited", "Unlimited"] },
  { feature: "Evaluation Center", values: ["yes", "yes", "yes", "yes", "yes"] },
  { feature: "Experiments", values: ["no", "yes", "yes", "yes", "yes"] },
  { feature: "Deployment Center", values: ["no", "yes", "yes", "yes", "yes"] },
  { feature: "Observer", values: ["no", "no", "no", "yes", "yes"] },
  { feature: "Diagnoser", values: ["no", "no", "no", "yes", "yes"] },
  { feature: "Improver", values: ["no", "no", "no", "yes", "yes"] },
  { feature: "MLflow Integration", values: ["no", "no", "no", "yes", "yes"] },
  { feature: "Audit Logs", values: ["no", "no", "yes", "yes", "yes"] },
  { feature: "Single Sign-On", values: ["no", "no", "no", "yes", "yes"] },
  { feature: "Enterprise SLA", values: ["no", "no", "no", "no", "yes"] },
];

function ComparisonCell({ value }: { value: string }) {
  if (value === "yes") return <CheckCircle2 className="w-4 h-4 text-emerald-600 mx-auto" />;
  if (value === "no") return <XCircle className="w-4 h-4 text-slate-300 mx-auto" />;
  return <span className="text-xs font-semibold text-slate-700">{value}</span>;
}

interface PricingSectionProps {
  onOpenSandbox: () => void;
}

export function PricingSection({ onOpenSandbox }: PricingSectionProps) {
  const [annualBilling, setAnnualBilling] = useState(true);

  function handleCta(planId: string) {
    if (planId === "enterprise" || planId === "business") {
      document.getElementById("contact")?.scrollIntoView({ behavior: "smooth" });
      return;
    }
    onOpenSandbox();
  }

  return (
    <section id="pricing" className="py-24 bg-white relative overflow-hidden">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center max-w-3xl mx-auto mb-12">
          <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-orange-50 border border-orange-200 text-orange-700 text-xs font-bold uppercase tracking-wider mb-4">
            <Sparkles className="w-3.5 h-3.5 text-orange-500" /> AutoRAG Architect Pricing
          </div>
          <h2 className="text-3xl sm:text-5xl font-extrabold text-slate-900 tracking-tight mb-4">
            Scale Your RAG Stack <span className="text-gradient-primary">Without Hidden Fees</span>
          </h2>
          <p className="text-base sm:text-lg text-slate-600 font-medium mb-8">
            An accessible entry point for students and developers, clear value for startups, and premium capabilities reserved for business and enterprise customers.
          </p>

          <div className="inline-flex items-center gap-3 bg-slate-100 p-1.5 rounded-full border border-slate-200 shadow-inner">
            <button
              onClick={() => setAnnualBilling(false)}
              className={`px-4 py-1.5 rounded-full text-xs font-bold transition-all cursor-pointer ${
                !annualBilling ? "bg-white text-slate-900 shadow-sm" : "text-slate-600 hover:text-slate-900"
              }`}
            >
              Monthly
            </button>
            <button
              onClick={() => setAnnualBilling(true)}
              className={`px-4 py-1.5 rounded-full text-xs font-bold transition-all cursor-pointer flex items-center gap-1.5 ${
                annualBilling ? "bg-orange-500 text-white shadow-md" : "text-slate-600 hover:text-slate-900"
              }`}
            >
              <span>Yearly</span>
              <span className="px-1.5 py-0.5 rounded-full bg-amber-400 text-slate-900 text-[10px] font-black uppercase">
                Save 20%
              </span>
            </button>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-6 items-stretch">
          {PLANS.map((plan) => {
            const price = annualBilling ? plan.priceYearly : plan.priceMonthly;
            const isFreeOrCustom = price === "Free" || price === "Custom Quote";
            const periodLabel = isFreeOrCustom ? "" : annualBilling ? "/ year" : "/ month";

            return (
              <div
                key={plan.id}
                className={`p-6 rounded-3xl transition-all duration-300 flex flex-col justify-between relative hover:-translate-y-1 ${
                  plan.popular
                    ? "bg-gradient-to-b from-stone-950 via-amber-950 to-stone-950 text-white shadow-2xl border-2 border-orange-500 scale-105 z-10"
                    : "bg-white text-slate-900 border border-slate-200/90 shadow-md hover:shadow-xl"
                }`}
              >
                {plan.popular && (
                  <div className="absolute -top-3.5 left-1/2 -translate-x-1/2 px-3 py-1 rounded-full bg-gradient-to-r from-orange-500 to-amber-500 text-white text-[10px] font-black uppercase tracking-wider shadow-md whitespace-nowrap">
                    Most Popular
                  </div>
                )}

                <div>
                  <div className={`text-[10px] font-black uppercase tracking-wider mb-2 ${plan.popular ? "text-orange-400" : "text-slate-400"}`}>
                    {plan.bestFor}
                  </div>
                  <h3 className="text-xl font-black mb-4">{plan.name}</h3>

                  <div className="mb-5 pb-5 border-b border-slate-200/20">
                    <div className="flex items-baseline gap-1">
                      <span className="text-2xl sm:text-3xl font-black tracking-tight">{price}</span>
                      {periodLabel && (
                        <span className={`text-[11px] font-medium ${plan.popular ? "text-slate-400" : "text-slate-500"}`}>
                          {periodLabel}
                        </span>
                      )}
                    </div>
                  </div>

                  <div className="space-y-2.5 mb-6">
                    {plan.included.map((feat) => (
                      <div key={feat} className="flex items-start gap-2 text-[11px] font-semibold leading-tight">
                        <CheckCircle2 className={`w-3.5 h-3.5 shrink-0 mt-0.5 ${plan.popular ? "text-orange-400" : "text-emerald-600"}`} />
                        <span className={plan.popular ? "text-slate-200" : "text-slate-700"}>{feat}</span>
                      </div>
                    ))}
                    {plan.notIncluded?.map((feat) => (
                      <div key={feat} className="flex items-start gap-2 text-[11px] font-medium leading-tight opacity-60">
                        <XCircle className="w-3.5 h-3.5 shrink-0 mt-0.5 text-slate-400" />
                        <span className="text-slate-500 line-through">{feat}</span>
                      </div>
                    ))}
                  </div>
                </div>

                <button
                  onClick={() => handleCta(plan.id)}
                  className={`w-full py-3 px-4 rounded-2xl text-xs font-extrabold transition-all flex items-center justify-center gap-1.5 cursor-pointer shadow-sm ${
                    plan.popular
                      ? "bg-gradient-to-r from-orange-500 to-amber-500 text-white hover:opacity-95 shadow-orange-500/30"
                      : "bg-slate-900 text-white hover:bg-slate-800"
                  }`}
                >
                  <span>{plan.ctaText}</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </button>
              </div>
            );
          })}
        </div>

        {/* Feature comparison table */}
        <div className="mt-16 overflow-x-auto rounded-3xl border border-slate-200 shadow-sm">
          <table className="w-full min-w-[720px] text-left text-xs">
            <thead className="bg-slate-50 text-slate-500 font-bold uppercase tracking-wider text-[10px]">
              <tr>
                <th className="p-4">Feature</th>
                {PLANS.map((p) => (
                  <th key={p.id} className="p-4 text-center">{p.name}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {COMPARISON_ROWS.map((row) => (
                <tr key={row.feature} className="hover:bg-slate-50/60 transition-colors">
                  <td className="p-4 font-semibold text-slate-800">{row.feature}</td>
                  {row.values.map((v, i) => (
                    <td key={PLANS[i].id} className="p-4 text-center">
                      <ComparisonCell value={v} />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Academic program */}
        <div className="mt-8 p-6 rounded-3xl bg-slate-50 border border-slate-200 flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <GraduationCap className="w-8 h-8 text-orange-600 shrink-0" />
            <div>
              <div className="text-sm font-black text-slate-900">Student &amp; Academic License</div>
              <p className="text-xs font-medium text-slate-600 mt-0.5">
                Free for verified students, educators, and research institutions — Community plan features, 12-month academic license, unlimited local deployments.
              </p>
            </div>
          </div>
          <button
            onClick={onOpenSandbox}
            className="shrink-0 px-4 py-2 rounded-xl bg-white border border-slate-300 text-slate-900 font-bold text-xs hover:bg-slate-100 transition-colors cursor-pointer"
          >
            Apply for Academic Access
          </button>
        </div>
      </div>
    </section>
  );
}
