import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import { BoardItemSchema, CheckInResultSchema, type BoardItem, type VehicleContext } from "../api/advisor";
import { api } from "../api/client";
import { ApiError } from "../api/envelope";
import { pageSchema } from "../api/schemas";
import { VehicleContextCard } from "../components/VehicleContextCard";

const today = () => new Date().toISOString().slice(0, 10);

function CheckInForm({ item, onDone }: { item: BoardItem; onDone: (ctx: VehicleContext) => void }) {
  const qc = useQueryClient();
  const [odometer, setOdometer] = useState("");
  const [level, setLevel] = useState(item.model === "Volt" ? "80% charge" : "1/2 tank");
  const [damage, setDamage] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [idemKey] = useState(() => crypto.randomUUID());
  const mutation = useMutation({
    mutationFn: () =>
      api(`/api/v1/repair-orders/${item.ro_id}/check-in`, CheckInResultSchema, {
        body: { odometer_in_km: Number(odometer), fuel_or_charge_level: level, damage_notes: damage, complaint_confirmed: confirmed },
        idempotencyKey: idemKey,
      }),
    onSuccess: (out) => {
      void qc.invalidateQueries({ queryKey: ["board"] });
      onDone(out.vehicle_context);
    },
  });
  function submit(e: FormEvent) {
    e.preventDefault();
    mutation.mutate();
  }
  return (
    <form onSubmit={submit} aria-label={`Check in ${item.ro_ref}`} className="mt-2 grid gap-2 sm:grid-cols-2">
      <label className="text-sm">
        Odometer (km)
        <input required inputMode="numeric" pattern="[0-9]*" value={odometer} onChange={(e) => setOdometer(e.target.value)}
          className="mt-1 block min-h-tap w-full rounded border border-slate-300 px-2 dark:bg-slate-900" />
      </label>
      <label className="text-sm">
        {item.model === "Volt" ? "Charge level" : "Fuel level"}
        <input required value={level} onChange={(e) => setLevel(e.target.value)} maxLength={32}
          className="mt-1 block min-h-tap w-full rounded border border-slate-300 px-2 dark:bg-slate-900" />
      </label>
      <label className="text-sm sm:col-span-2">
        Visible damage notes
        <input value={damage} onChange={(e) => setDamage(e.target.value)} maxLength={2000}
          className="mt-1 block min-h-tap w-full rounded border border-slate-300 px-2 dark:bg-slate-900" />
      </label>
      <label className="flex min-h-tap items-center gap-2 text-sm sm:col-span-2">
        <input type="checkbox" checked={confirmed} onChange={(e) => setConfirmed(e.target.checked)} className="h-6 w-6" />
        Owner's complaint confirmed with the owner
      </label>
      {mutation.isError && (
        <p role="alert" className="text-sm text-red-700 sm:col-span-2">
          {mutation.error instanceof ApiError ? mutation.error.message : "Check-in failed."}
        </p>
      )}
      <button type="submit" disabled={mutation.isPending}
        className="min-h-tap rounded bg-blue-700 px-4 font-medium text-white disabled:opacity-60 sm:col-span-2">
        {mutation.isPending ? "Checking in…" : "Check in"}
      </button>
    </form>
  );
}

export function AdvisorBoard() {
  const [date, setDate] = useState(today());
  const [openId, setOpenId] = useState<string | null>(null);
  const [context, setContext] = useState<VehicleContext | null>(null);
  const board = useQuery({
    queryKey: ["board", date],
    queryFn: () => api(`/api/v1/appointments?date=${date}`, pageSchema(BoardItemSchema)),
  });
  return (
    <section aria-labelledby="page-title" className="mx-auto max-w-5xl p-4">
      <div className="flex flex-wrap items-center gap-3">
        <h1 id="page-title" className="text-2xl font-semibold">
          Advisor board
        </h1>
        <label className="ml-auto text-sm">
          Date{" "}
          <input type="date" value={date} onChange={(e) => setDate(e.target.value)}
            className="min-h-tap rounded border border-slate-300 px-2 dark:bg-slate-900" />
        </label>
      </div>
      {board.isError && <p role="alert">Could not load appointments.</p>}
      {board.data && board.data.items.length === 0 && <p className="mt-4 text-slate-600">No appointments on this day.</p>}
      <ul className="mt-4 space-y-3">
        {board.data?.items.map((item) => (
          <li key={item.ro_id} className="rounded-lg bg-white p-4 shadow dark:bg-slate-800">
            <div className="flex flex-wrap items-baseline gap-2">
              <strong>{new Date(item.slot_start).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</strong>
              <Link to={`/ro/${item.ro_id}`} className="underline">
                {item.ro_ref}
              </Link>
              <span className="rounded bg-slate-200 px-2 text-xs dark:bg-slate-700">{item.ro_status.replace(/_/g, " ")}</span>
              <span className="text-sm text-slate-600 dark:text-slate-400">
                Veloxa {item.model} {item.model_year} ({item.vin_masked}) · {item.owner_display_name}
              </span>
            </div>
            <blockquote className="mt-1 border-l-4 border-slate-300 pl-2 text-sm italic">“{item.complaint_text}”</blockquote>
            {item.ro_status === "BOOKED" &&
              (openId === item.ro_id ? (
                <CheckInForm item={item} onDone={(ctx) => setContext(ctx)} />
              ) : (
                <button type="button" onClick={() => { setOpenId(item.ro_id); setContext(null); }}
                  className="mt-2 min-h-tap rounded border border-blue-700 px-3 text-sm text-blue-800 dark:text-blue-200">
                  Start check-in
                </button>
              ))}
            {openId === item.ro_id && context && <VehicleContextCard ctx={context} />}
          </li>
        ))}
      </ul>
    </section>
  );
}
