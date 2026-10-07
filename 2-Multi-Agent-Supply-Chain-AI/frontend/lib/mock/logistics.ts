import type { CarrierPerformance, LogisticsSummary, Shipment, ShipmentStatus, TransportMode } from "@/types";
import { allInventory } from "./inventory";
import { allSuppliers } from "./suppliers";
import { DAY_MS, daysFromNow, now, Rng } from "./rng";

const CARRIERS: { name: string; mode: TransportMode; onTime: number; transit: number; costPerKg: number }[] = [
  { name: "Bluewater Ocean Lines", mode: "ocean", onTime: 0.88, transit: 21, costPerKg: 0.18 },
  { name: "Harbor Point Shipping", mode: "ocean", onTime: 0.84, transit: 24, costPerKg: 0.15 },
  { name: "SkyBridge Air Cargo", mode: "air", onTime: 0.96, transit: 3, costPerKg: 4.6 },
  { name: "TransPacific Freight", mode: "air", onTime: 0.93, transit: 4, costPerKg: 3.9 },
  { name: "Swift Road Haulage", mode: "road", onTime: 0.95, transit: 2, costPerKg: 0.42 },
  { name: "Meridian Rail Logistics", mode: "rail", onTime: 0.91, transit: 9, costPerKg: 0.27 },
];

const LANES: { origin: string; destination: string; carriers: number[] }[] = [
  { origin: "Shenzhen, CN", destination: "Tokyo DC", carriers: [0, 1, 2] },
  { origin: "Ho Chi Minh City, VN", destination: "Singapore Hub", carriers: [0, 1] },
  { origin: "Busan, KR", destination: "Osaka DC", carriers: [0, 3] },
  { origin: "Yokohama, JP", destination: "Tokyo DC", carriers: [4] },
  { origin: "Hamburg, DE", destination: "Rotterdam DC", carriers: [4, 5] },
  { origin: "Gdansk, PL", destination: "Rotterdam DC", carriers: [5, 4] },
  { origin: "Houston, US", destination: "Dallas DC", carriers: [4, 5] },
  { origin: "Kobe, JP", destination: "Singapore Hub", carriers: [0, 2] },
];

const EVENTS: Record<Exclude<ShipmentStatus, "delayed">, string[]> = {
  pending: ["Booking confirmed with carrier", "Awaiting pickup at origin"],
  in_transit: ["Departed origin", "In transit — on schedule", "Arrived at transshipment hub", "Out for final-mile delivery"],
  at_customs: ["Held for customs inspection", "Customs documents under review"],
  delivered: ["Delivered and received at DC", "Proof of delivery signed"],
};

/** Delay reasons depend on the transport mode, so a truck never "misses a vessel". */
const DELAY_REASONS: Record<TransportMode, string[]> = {
  ocean: ["Port congestion at destination — berthing delayed", "Missed vessel connection — rebooked", "Weather hold at origin port"],
  air: ["Flight cancelled — rebooked on next departure", "Capacity offload at hub airport"],
  road: ["Border crossing backlog", "Driver hours limit — overnight hold", "Road closure — rerouted"],
  rail: ["Rail yard congestion", "Locomotive shortage — departure delayed"],
};

let cache: Shipment[] | null = null;

export function allShipments(): Shipment[] {
  if (cache) return cache;
  const rng = new Rng(4242);
  const items = allInventory();
  const suppliers = allSuppliers();
  const today = now();
  const out: Shipment[] = [];
  const total = 214;
  for (let i = 0; i < total; i++) {
    const lane = rng.pick(LANES);
    const carrier = CARRIERS[rng.pick(lane.carriers)];
    const item = i === 0 ? items[0] : rng.pick(items);
    const transit = Math.max(1, Math.round(carrier.transit * rng.float(0.85, 1.2)));
    const shippedOffset = -rng.int(0, transit + 4);
    const shippedAt = new Date(today.getTime() + shippedOffset * DAY_MS);
    const promised = new Date(shippedAt.getTime() + transit * DAY_MS);
    // 12 delayed shipments among active ones, plus some delivered and pending.
    let status: ShipmentStatus;
    if (i < 12) status = "delayed";
    else if (i < 18) status = "at_customs";
    else if (i < 40) status = "pending";
    else if (i < 70) status = "delivered";
    else status = "in_transit";
    const delayDays = status === "delayed" ? rng.int(1, 6) : status === "at_customs" ? rng.int(0, 2) : 0;
    // A delayed shipment's ETA is re-forecast, so it is always in the future and later than promised.
    let eta = new Date(promised.getTime() + delayDays * DAY_MS);
    if (status === "delayed" && eta <= today) eta = new Date(today.getTime() + rng.int(1, delayDays + 1) * DAY_MS);
    const lateBy = Math.max(delayDays, Math.round((eta.getTime() - promised.getTime()) / DAY_MS));
    const elapsed = (today.getTime() - shippedAt.getTime()) / (eta.getTime() - shippedAt.getTime());
    const progress =
      status === "delivered" ? 100 : status === "pending" ? 0 : Math.min(96, Math.max(6, Math.round(elapsed * 100)));
    const supplier = rng.pick(suppliers.filter((s) => s.categories.includes(item.category))) ?? suppliers[0];
    out.push({
      id: `SHP-${String(48210 + i)}`,
      poNumber: `PO-${String(77031 + i * 3)}`,
      sku: item.sku,
      product: item.name,
      supplier: supplier.name,
      origin: lane.origin,
      destination: lane.destination,
      carrier: carrier.name,
      mode: carrier.mode,
      status,
      shippedAt: (status === "pending" ? daysFromNow(rng.int(1, 4)) : shippedAt).toISOString(),
      eta: (status === "pending" ? daysFromNow(transit + rng.int(1, 4)) : eta).toISOString(),
      promisedDate: promised.toISOString(),
      delayDays: status === "delayed" ? lateBy : delayDays,
      progress,
      units: Math.round(item.dailyDemand * rng.float(10, 40)),
      lastEvent: status === "delayed" ? rng.pick(DELAY_REASONS[carrier.mode]) : rng.pick(EVENTS[status]),
    });
  }
  // SKU-100's inbound partial order (850 units): ocean freight Shenzhen → Tokyo, delayed 3 days.
  const promised = new Date(today.getTime() + 1 * DAY_MS);
  out[0] = {
    ...out[0],
    supplier: "Kaito Precision Industries",
    origin: "Shenzhen, CN",
    destination: "Tokyo DC",
    carrier: "Bluewater Ocean Lines",
    mode: "ocean",
    units: 850,
    shippedAt: new Date(promised.getTime() - 21 * DAY_MS).toISOString(),
    promisedDate: promised.toISOString(),
    eta: new Date(promised.getTime() + 3 * DAY_MS).toISOString(),
    delayDays: 3,
    progress: 86,
    lastEvent: "Port congestion at destination — berthing delayed",
  };
  cache = out;
  return cache;
}

export function delayedShipments(): Shipment[] {
  return allShipments().filter((s) => s.status === "delayed");
}

export function logisticsSummary(): LogisticsSummary {
  const shipments = allShipments();
  const active = shipments.filter((s) => s.status !== "delivered");
  const delayed = shipments.filter((s) => s.status === "delayed");
  const rng = new Rng(99);
  const carriers: CarrierPerformance[] = CARRIERS.map((c) => ({
    carrier: c.name,
    mode: c.mode,
    onTimeRate: c.onTime,
    avgTransitDays: c.transit,
    costPerKg: c.costPerKg,
    activeShipments: active.filter((s) => s.carrier === c.name).length,
    trend: Array.from({ length: 12 }, () => Math.round((c.onTime + rng.normal(0, 0.015)) * 1000) / 10),
  }));
  const deliveryForecast = Array.from({ length: 14 }, (_, k) => {
    const day = daysFromNow(k);
    const sameDay = (iso: string) => new Date(iso).toDateString() === day.toDateString();
    return {
      label: day.toLocaleDateString("en-US", { month: "short", day: "numeric" }),
      expected: active.filter((s) => sameDay(s.eta)).length + rng.int(2, 6),
      atRisk: active.filter((s) => sameDay(s.eta) && (s.status === "delayed" || s.status === "at_customs")).length,
    };
  });
  const lanes = LANES.map((l) => {
    const onLane = active.filter((s) => s.origin === l.origin && s.destination === l.destination);
    return { origin: l.origin, destination: l.destination, shipments: onLane.length, delayed: onLane.filter((s) => s.status === "delayed").length };
  }).sort((a, b) => b.shipments - a.shipments);
  return {
    active: active.length,
    delayed: delayed.length,
    onTimeRate: 0.927,
    avgDelayDays: Math.round((delayed.reduce((s, x) => s + x.delayDays, 0) / Math.max(delayed.length, 1)) * 10) / 10,
    inTransitValue: 18_420_000,
    deliveryForecast,
    carriers,
    lanes,
  };
}
