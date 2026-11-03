"use client";

import { useState } from "react";
import { Mail, Send, User, Building, CheckCircle2, Sparkles, Headphones, ShieldCheck } from "lucide-react";

export function ContactSection() {
  const [formData, setFormData] = useState({
    name: "",
    email: "",
    company: "",
    useCase: "Enterprise Search",
    message: "",
  });

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setTimeout(() => {
      setIsSubmitting(false);
      setSubmitted(true);
    }, 800);
  };

  return (
    <section id="contact" className="py-24 bg-slate-900 relative border-t border-slate-800">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10 space-y-12">
        <div className="text-center max-w-3xl mx-auto space-y-4">
          <div className="inline-flex items-center gap-2 px-3.5 py-1 rounded-full bg-orange-500/10 border border-orange-500/20 text-orange-400 text-xs font-mono font-bold uppercase tracking-wider">
            <Mail className="w-3.5 h-3.5" />
            <span>Contact &amp; Engineering Consultation</span>
          </div>
          <h2 className="text-3xl sm:text-5xl font-black text-white tracking-tight">
            Book a Custom AutoRAG Demo
          </h2>
          <p className="text-slate-400 text-base sm:text-lg font-medium">
            Speak directly with our AI retrieval architects to review your vector database topology, compliance requirements, or custom agent setup.
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
          <div className="lg:col-span-5 bg-slate-950 p-8 rounded-3xl border border-slate-800 space-y-6">
            <div className="space-y-2">
              <h3 className="text-xl font-extrabold text-white">Direct Sales &amp; Architecture Support</h3>
              <p className="text-xs text-slate-400 leading-relaxed font-medium">
                Our engineering team provides dedicated onboarding, custom VPC deployment assistance, and SLA guarantees.
              </p>
            </div>

            <div className="space-y-4 pt-4 border-t border-slate-800/80">
              <div className="flex items-start gap-3">
                <div className="p-2.5 rounded-xl bg-orange-500/10 text-orange-400 border border-orange-500/20">
                  <Headphones className="w-4 h-4" />
                </div>
                <div>
                  <div className="text-xs font-bold text-white">Technical Consultation</div>
                  <div className="text-xs text-slate-400 font-mono">support@autorag.dev</div>
                </div>
              </div>

              <div className="flex items-start gap-3">
                <div className="p-2.5 rounded-xl bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                  <ShieldCheck className="w-4 h-4" />
                </div>
                <div>
                  <div className="text-xs font-bold text-white">Security &amp; Compliance Audits</div>
                  <div className="text-xs text-slate-400 font-mono">security@autorag.dev</div>
                </div>
              </div>

              <div className="flex items-start gap-3">
                <div className="p-2.5 rounded-xl bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                  <Sparkles className="w-4 h-4" />
                </div>
                <div>
                  <div className="text-xs font-bold text-white">Enterprise SLA &amp; VPC Air-Gap</div>
                  <div className="text-xs text-slate-400 font-mono">sales@autorag.dev</div>
                </div>
              </div>
            </div>

            <div className="p-4 rounded-2xl bg-slate-900 border border-slate-800 text-xs text-slate-400 space-y-2">
              <div className="font-bold text-white">Enterprise SLA:</div>
              <ul className="space-y-1 list-disc list-inside text-slate-300">
                <li>Multi-region blue/green failover architecture</li>
                <li>Deployment-specific latency SLA, benchmarked against your workload</li>
                <li>Your data is never used for model training, on a SOC 2-aligned architecture</li>
              </ul>
            </div>
          </div>

          <div className="lg:col-span-7 bg-slate-950 p-8 rounded-3xl border border-slate-800 shadow-2xl">
            {submitted ? (
              <div className="py-12 text-center space-y-4 animate-fade-in-marketing">
                <div className="w-16 h-16 rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 mx-auto flex items-center justify-center">
                  <CheckCircle2 className="w-8 h-8" />
                </div>
                <h3 className="text-2xl font-black text-white">Consultation Request Received!</h3>
                <p className="text-xs text-slate-400 max-w-md mx-auto">
                  Thank you, <span className="text-white font-bold">{formData.name}</span>. An AutoRAG Solutions Architect will contact you at <span className="text-orange-400 font-mono">{formData.email}</span> within 2 hours.
                </p>
                <button
                  onClick={() => setSubmitted(false)}
                  className="px-6 py-2.5 rounded-full bg-slate-800 hover:bg-slate-700 text-white font-bold text-xs transition-colors cursor-pointer"
                >
                  Send Another Inquiry
                </button>
              </div>
            ) : (
              <form onSubmit={handleSubmit} className="space-y-4">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <label className="text-xs font-mono font-bold text-slate-300">Your Full Name</label>
                    <div className="relative">
                      <User className="w-4 h-4 text-slate-500 absolute left-3 top-3" />
                      <input
                        type="text"
                        required
                        value={formData.name}
                        onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                        placeholder="Sarah Jenkins"
                        className="w-full bg-slate-900 border border-slate-800 rounded-xl pl-9 pr-3 py-2.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-orange-500 transition-colors"
                      />
                    </div>
                  </div>

                  <div className="space-y-1.5">
                    <label className="text-xs font-mono font-bold text-slate-300">Work Email</label>
                    <div className="relative">
                      <Mail className="w-4 h-4 text-slate-500 absolute left-3 top-3" />
                      <input
                        type="email"
                        required
                        value={formData.email}
                        onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                        placeholder="sarah@company.com"
                        className="w-full bg-slate-900 border border-slate-800 rounded-xl pl-9 pr-3 py-2.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-orange-500 transition-colors"
                      />
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <label className="text-xs font-mono font-bold text-slate-300">Company Name</label>
                    <div className="relative">
                      <Building className="w-4 h-4 text-slate-500 absolute left-3 top-3" />
                      <input
                        type="text"
                        required
                        value={formData.company}
                        onChange={(e) => setFormData({ ...formData, company: e.target.value })}
                        placeholder="Acme Corp"
                        className="w-full bg-slate-900 border border-slate-800 rounded-xl pl-9 pr-3 py-2.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-orange-500 transition-colors"
                      />
                    </div>
                  </div>

                  <div className="space-y-1.5">
                    <label className="text-xs font-mono font-bold text-slate-300">Primary Industry / Use Case</label>
                    <select
                      value={formData.useCase}
                      onChange={(e) => setFormData({ ...formData, useCase: e.target.value })}
                      className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2.5 text-xs text-white focus:outline-none focus:border-orange-500 transition-colors"
                    >
                      <option value="Enterprise Search">Enterprise Search</option>
                      <option value="Documentation QA">Documentation QA</option>
                      <option value="Customer Support">Customer Support</option>
                      <option value="Financial Services">Financial Services</option>
                      <option value="Healthcare & Clinical">Healthcare &amp; Clinical</option>
                      <option value="Legal Tech">Legal Tech</option>
                      <option value="Developer Copilot">Developer Copilot</option>
                      <option value="Insurance">Insurance</option>
                      <option value="Manufacturing & Supply Chain">Manufacturing &amp; Supply Chain</option>
                      <option value="HR & People Operations">HR &amp; People Operations</option>
                    </select>
                  </div>
                </div>

                <div className="space-y-1.5">
                  <label className="text-xs font-mono font-bold text-slate-300">Inquiry Details</label>
                  <textarea
                    rows={4}
                    required
                    value={formData.message}
                    onChange={(e) => setFormData({ ...formData, message: e.target.value })}
                    placeholder="Tell us about your vector database setup, current RAG challenges, or throughput requirements..."
                    className="w-full bg-slate-900 border border-slate-800 rounded-xl p-3 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-orange-500 transition-colors"
                  />
                </div>

                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="w-full py-3 rounded-xl bg-gradient-to-r from-orange-500 to-amber-500 hover:from-orange-600 hover:to-amber-600 text-white font-extrabold text-xs shadow-lg shadow-orange-500/20 transition-all flex items-center justify-center gap-2 cursor-pointer"
                >
                  {isSubmitting ? (
                    <span>Submitting Request...</span>
                  ) : (
                    <>
                      <span>Submit Architecture Consultation Request</span>
                      <Send className="w-3.5 h-3.5" />
                    </>
                  )}
                </button>
              </form>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
