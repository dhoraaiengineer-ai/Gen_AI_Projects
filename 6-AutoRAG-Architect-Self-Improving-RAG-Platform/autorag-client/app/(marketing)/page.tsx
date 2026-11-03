"use client";

import { useState } from "react";
import { Navbar } from "@/components/marketing/Navbar";
import { HeroSection } from "@/components/marketing/HeroSection";
import { SolutionsSection } from "@/components/marketing/SolutionsSection";
import { ArchitectureSection } from "@/components/marketing/ArchitectureSection";
import { AgentsSection } from "@/components/marketing/AgentsSection";
import { FeaturesSection } from "@/components/marketing/FeaturesSection";
import { StatsSection } from "@/components/marketing/StatsSection";
import { DocsSection } from "@/components/marketing/DocsSection";
import { ScreensShowcase } from "@/components/marketing/ScreensShowcase";
import { TechStackSection } from "@/components/marketing/TechStackSection";
import { SecuritySection } from "@/components/marketing/SecuritySection";
import { AboutSection } from "@/components/marketing/AboutSection";
import { PricingSection } from "@/components/marketing/PricingSection";
import { ContactSection } from "@/components/marketing/ContactSection";
import { Footer } from "@/components/marketing/Footer";
import { RagSimulatorModal } from "@/components/marketing/RagSimulatorModal";
import { ScrollToTop } from "@/components/marketing/ScrollToTop";
import { MarketingChatWidget } from "@/components/marketing/chatbot/MarketingChatWidget";
import { MarketingChatLauncher } from "@/components/marketing/chatbot/MarketingChatLauncher";

export default function MarketingHomePage() {
  const [simulatorOpen, setSimulatorOpen] = useState(false);
  const [chatOpen, setChatOpen] = useState(false);

  const handleOpenBookDemo = () => {
    setChatOpen(false);
    document.getElementById("contact")?.scrollIntoView({ behavior: "smooth" });
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 font-sans selection:bg-orange-500 selection:text-white">
      <Navbar onOpenSandbox={() => setSimulatorOpen(true)} onOpenChat={() => setChatOpen(true)} />

      <main>
        <HeroSection onOpenSandbox={() => setSimulatorOpen(true)} onOpenChat={() => setChatOpen(true)} />
        <SolutionsSection />
        <ArchitectureSection />
        <AgentsSection />
        <FeaturesSection />
        <StatsSection />
        <DocsSection />
        <ScreensShowcase />
        <TechStackSection />
        <SecuritySection />
        <AboutSection />
        <PricingSection onOpenSandbox={() => setSimulatorOpen(true)} />
        <ContactSection />
      </main>

      <Footer />

      <RagSimulatorModal isOpen={simulatorOpen} onClose={() => setSimulatorOpen(false)} />
      <MarketingChatWidget isOpen={chatOpen} onClose={() => setChatOpen(false)} onOpenBookDemo={handleOpenBookDemo} />
      <MarketingChatLauncher onClick={() => setChatOpen(true)} />
      <ScrollToTop />
    </div>
  );
}
