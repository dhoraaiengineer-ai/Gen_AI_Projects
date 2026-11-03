"use client";

import { useState, useRef, useCallback, useEffect } from "react";

interface SpeechRecognitionResultLike {
  isFinal: boolean;
  0: { transcript: string };
}

interface SpeechRecognitionEventLike {
  resultIndex: number;
  results: ArrayLike<SpeechRecognitionResultLike>;
}

interface SpeechRecognitionLike {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
  onend: (() => void) | null;
  onerror: (() => void) | null;
  start: () => void;
  stop: () => void;
}

type SpeechRecognitionCtor = new () => SpeechRecognitionLike;

function getSpeechRecognitionCtor(): SpeechRecognitionCtor | null {
  if (typeof window === "undefined") return null;
  const w = window as unknown as { SpeechRecognition?: SpeechRecognitionCtor; webkitSpeechRecognition?: SpeechRecognitionCtor };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

// Indian-English female voice names shipped by common browser/OS voice
// packs (Windows SAPI, Chrome/Android, macOS/iOS all ship at least one).
const INDIAN_FEMALE_VOICE_NAME_HINTS = ["heera", "veena", "priya", "google हिन्दी", "raveena", "aditi"];

const FEMALE_VOICE_NAME_HINTS = [
  "female",
  "zira",
  "samantha",
  "victoria",
  "karen",
  "moira",
  "tessa",
  "susan",
  "google us english",
  "google uk english female",
];

function pickFemaleVoice(): SpeechSynthesisVoice | null {
  if (typeof window === "undefined" || !("speechSynthesis" in window)) return null;
  const voices = window.speechSynthesis.getVoices();
  if (voices.length === 0) return null;

  // Prefer a named Indian-English female voice, then any en-IN voice, then
  // any generically-named female voice, then any English voice at all.
  const indianNamed = voices.find((v) => INDIAN_FEMALE_VOICE_NAME_HINTS.some((hint) => v.name.toLowerCase().includes(hint)));
  const indianLocale = voices.find((v) => v.lang.toLowerCase() === "en-in");
  const female = voices.find((v) => FEMALE_VOICE_NAME_HINTS.some((hint) => v.name.toLowerCase().includes(hint)));
  return indianNamed ?? indianLocale ?? female ?? voices.find((v) => v.lang.startsWith("en")) ?? voices[0];
}

/**
 * Client-only voice module for the marketing chat widget — browser-native
 * Web Speech API only (no external voice service/cost). Text-to-speech
 * prefers a female-sounding system voice; speech-to-text feeds the chat
 * input. Both degrade gracefully (buttons hidden) where unsupported (e.g.
 * Firefox has no SpeechRecognition).
 */
export function useVoice() {
  const [voiceEnabled, setVoiceEnabled] = useState(true);
  const [speakingMsgId, setSpeakingMsgId] = useState<string | null>(null);
  const [isListening, setIsListening] = useState(false);
  const [voiceSupported, setVoiceSupported] = useState(false);
  const [micSupported, setMicSupported] = useState(false);
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);

  useEffect(() => {
    setVoiceSupported(typeof window !== "undefined" && "speechSynthesis" in window);
    setMicSupported(getSpeechRecognitionCtor() !== null);
  }, []);

  const stopSpeaking = useCallback(() => {
    if (typeof window !== "undefined" && "speechSynthesis" in window) {
      window.speechSynthesis.cancel();
    }
    setSpeakingMsgId(null);
  }, []);

  const speak = useCallback((text: string, msgId: string) => {
    if (typeof window === "undefined" || !("speechSynthesis" in window)) return;
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text.replace(/[*#`_]/g, ""));
    const voice = pickFemaleVoice();
    if (voice) utterance.voice = voice;
    // Calm, professional "senior AI solutions architect" tone: medium-low
    // pitch, slightly slower than default speaking rate.
    utterance.pitch = 0.92;
    utterance.rate = 0.95;
    utterance.onend = () => setSpeakingMsgId(null);
    utterance.onerror = () => setSpeakingMsgId(null);
    setSpeakingMsgId(msgId);
    window.speechSynthesis.speak(utterance);
  }, []);

  const startListening = useCallback((onTranscript: (text: string) => void) => {
    const Ctor = getSpeechRecognitionCtor();
    if (!Ctor) return;
    const recognition = new Ctor();
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.lang = "en-IN";
    recognition.onresult = (event) => {
      let transcript = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        transcript += event.results[i][0].transcript;
      }
      onTranscript(transcript);
    };
    recognition.onend = () => setIsListening(false);
    recognition.onerror = () => setIsListening(false);
    recognitionRef.current = recognition;
    setIsListening(true);
    recognition.start();
  }, []);

  const stopListening = useCallback(() => {
    recognitionRef.current?.stop();
    setIsListening(false);
  }, []);

  return {
    voiceEnabled,
    setVoiceEnabled,
    speakingMsgId,
    speak,
    stopSpeaking,
    isListening,
    startListening,
    stopListening,
    voiceSupported,
    micSupported,
  };
}
