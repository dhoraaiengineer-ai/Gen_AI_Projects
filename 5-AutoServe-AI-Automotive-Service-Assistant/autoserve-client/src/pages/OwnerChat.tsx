import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import { api, streamChat } from "../api/client";
import { ApiError } from "../api/envelope";
import { ChatReplySchema, pageSchema, VehicleSummarySchema, type ChatReply } from "../api/schemas";
import { CitationChip, SafetyBanner } from "../components/Safety";

type Turn = { id: number; role: "user" | "assistant"; text: string; reply?: ChatReply };

export function OwnerChat() {
  const vehicles = useQuery({
    queryKey: ["vehicles"],
    queryFn: () => api("/api/v1/vehicles", pageSchema(VehicleSummarySchema)),
  });
  const [vehicleId, setVehicleId] = useState<string>("");
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const nextId = useRef(1);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!vehicleId && vehicles.data?.items[0]) setVehicleId(vehicles.data.items[0].id);
  }, [vehicles.data, vehicleId]);
  useEffect(() => {
    // Braces matter: newer browsers return a Promise from scrollIntoView, which React would treat as a cleanup.
    endRef.current?.scrollIntoView?.({ block: "end" });
  }, [turns]);

  async function send(text: string) {
    if (!text.trim() || busy) return;
    setBusy(true);
    setError(null);
    const userTurn: Turn = { id: nextId.current++, role: "user", text };
    const botId = nextId.current++;
    setTurns((t) => [...t, userTurn, { id: botId, role: "assistant", text: "" }]);
    setDraft("");
    try {
      const reply = await streamChat(
        { text, conversation_id: conversationId ?? undefined, vehicle_id: vehicleId || undefined },
        ChatReplySchema,
        (token) => setTurns((t) => t.map((x) => (x.id === botId ? { ...x, text: x.text + token } : x))),
      );
      setConversationId(reply.conversation_id);
      setTurns((t) => t.map((x) => (x.id === botId ? { ...x, text: reply.reply, reply } : x)));
    } catch (err) {
      setTurns((t) => t.filter((x) => x.id !== botId));
      setError(err instanceof ApiError ? err.message : "Something went wrong. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    void send(draft);
  }

  return (
    <section aria-labelledby="page-title" className="mx-auto flex max-w-3xl flex-col p-4">
      <div className="flex flex-wrap items-center gap-3">
        <h1 id="page-title" className="text-2xl font-semibold">
          Owner chat
        </h1>
        <label className="ml-auto text-sm">
          Vehicle{" "}
          <select
            value={vehicleId}
            onChange={(e) => setVehicleId(e.target.value)}
            className="min-h-tap rounded border border-slate-300 px-2 dark:border-slate-600 dark:bg-slate-900"
          >
            {vehicles.data?.items.map((v) => (
              <option key={v.id} value={v.id}>
                Veloxa {v.model} {v.model_year} ({v.vin_masked})
              </option>
            ))}
          </select>
        </label>
      </div>
      <p className="mt-1 text-xs text-slate-500">
        Answers come only from the Veloxa manuals (SYNTHETIC). For anything safety-related, follow the banner and contact
        your service centre.
      </p>

      <ol aria-live="polite" className="mt-4 flex-1 space-y-3">
        {turns.map((t) => (
          <li key={t.id} className={t.role === "user" ? "text-right" : ""}>
            <div
              className={`inline-block max-w-[90%] rounded-lg px-3 py-2 text-left ${
                t.role === "user" ? "bg-blue-700 text-white" : "bg-white shadow dark:bg-slate-800"
              }`}
            >
              {t.reply && <SafetyBanner safety={t.reply.safety} />}
              <p className="whitespace-pre-wrap">{t.text || "…"}</p>
              {t.reply && t.reply.citations.length > 0 && (
                <p className="mt-1">
                  {t.reply.citations.map((c, i) => (
                    <CitationChip key={`${c.chunk_id}-${i}`} citation={c} />
                  ))}
                </p>
              )}
              {t.reply?.ro_status && (
                <p className="mt-1 text-sm">
                  Repair order:{" "}
                  <Link className="underline" to={`/ro/ref/${t.reply.ro_status.ro_ref}`}>
                    {t.reply.ro_status.ro_ref}
                  </Link>
                </p>
              )}
              {t.reply && t.reply.options.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-2">
                  {t.reply.options.map((o, i) => (
                    <button
                      key={o}
                      type="button"
                      onClick={() => void send(String(i + 1))}
                      className="min-h-tap rounded border border-blue-700 px-3 text-sm text-blue-800 dark:text-blue-200"
                    >
                      {i + 1}) {o}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </li>
        ))}
      </ol>
      <div ref={endRef} />

      {error && (
        <p role="alert" className="mt-2 text-sm text-red-700">
          {error}
        </p>
      )}
      <form onSubmit={onSubmit} className="mt-3 flex gap-2">
        <label htmlFor="chat-input" className="sr-only">
          Message
        </label>
        <input
          id="chat-input"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          maxLength={2000}
          placeholder="Ask about a warning light, book a service, or check a repair…"
          className="min-h-tap flex-1 rounded border border-slate-300 px-3 dark:border-slate-600 dark:bg-slate-900"
        />
        <button
          type="submit"
          disabled={busy || !draft.trim()}
          className="min-h-tap rounded bg-blue-700 px-4 font-medium text-white disabled:opacity-60"
        >
          Send
        </button>
      </form>
    </section>
  );
}
