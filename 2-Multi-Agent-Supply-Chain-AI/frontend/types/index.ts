/**
 * API contract shared by the mock data source and the FastAPI backend.
 * The backend's pydantic response models mirror these shapes (camelCase over the wire).
 */

export type RiskLevel = "critical" | "high" | "medium" | "low";
export type Severity = "critical" | "warning" | "insight" | "info" | "success";
export type Role = "viewer" | "analyst" | "approver" | "admin";
export type Environment = "production" | "staging" | "development";

export interface TrendPoint {
  label: string;
  value: number;
}

// ---------------------------------------------------------------- overview / KPIs
export type KpiIcon = "boxes" | "alert" | "truck" | "activity" | "dollar" | "target" | "bot" | "gauge";

export interface Kpi {
  id: string;
  label: string;
  value: number;
  display: string;
  delta: number; // percentage change vs previous period
  deltaLabel: string;
  /** whether an increase is good ("up"), bad ("down") or neutral */
  goodDirection: "up" | "down" | "neutral";
  context: string;
  trend: number[];
  icon: KpiIcon;
}

export interface Recommendation {
  id: string;
  title: string;
  detail: string;
  sku?: string;
  risk: RiskLevel;
  impact: string;
  agents: AgentId[];
  confidence: number; // 0-1
  createdAt: string;
}

export interface HealthDimension {
  label: string;
  score: number; // 0-100
}

export interface Overview {
  kpis: Kpi[];
  healthScore: number;
  healthDimensions: HealthDimension[];
  topRisks: InventoryItem[];
  recommendations: Recommendation[];
  supplyDemand: { label: string; demand: number; supply: number }[];
}

// ---------------------------------------------------------------- inventory
export interface InventoryItem {
  sku: string;
  name: string;
  category: string;
  warehouse: string;
  onHand: number;
  available: number;
  onOrder: number;
  dailyDemand: number;
  forecast30d: number;
  safetyStock: number;
  reorderPoint: number;
  reorderQty: number;
  daysOfCover: number;
  leadTimeDays: number;
  risk: RiskLevel;
  recommendation: string;
  unitCost: number;
  turnover: number;
  agingDays: number;
  trend: number[];
}

export interface InventorySummary {
  totalSkus: number;
  totalValue: number;
  atRisk: number;
  critical: number;
  stockoutWithin7d: number;
  reorderRecommended: number;
  avgTurnover: number;
  agedValue: number; // value of stock older than 90 days
  inventoryTrend: { label: string; onHand: number; safetyStock: number }[];
  riskDistribution: { risk: RiskLevel; count: number }[];
  categoryDistribution: { category: string; value: number; skus: number }[];
  aging: { bucket: string; value: number }[];
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  pageSize: number;
}

export interface InventoryQuery {
  search?: string;
  risk?: RiskLevel | "all";
  category?: string;
  sort?: keyof InventoryItem;
  order?: "asc" | "desc";
  page?: number;
  pageSize?: number;
}

// ---------------------------------------------------------------- demand
export type ForecastHorizon = "7d" | "30d" | "90d" | "6m" | "1y";

export interface ForecastPoint {
  date: string;
  actual?: number;
  forecast?: number;
  lower?: number;
  upper?: number;
}

export interface DemandForecast {
  sku: string;
  name: string;
  horizon: ForecastHorizon;
  method: string;
  points: ForecastPoint[];
  totalForecast: number;
  dailyMean: number;
  trend: { direction: "up" | "down" | "flat"; pctChange: number };
  seasonality: { detected: boolean; periodDays: number; weekdayIndex: { day: string; index: number }[] };
  accuracy: { mape: number; bias: number };
  confidence: "high" | "medium" | "low";
  drivers: string[];
}

// ---------------------------------------------------------------- suppliers
export interface Supplier {
  id: string;
  name: string;
  country: string;
  region: string;
  categories: string[];
  unitPrice: number;
  leadTimeDays: number;
  reliability: number; // on-time delivery rate 0-1
  defectRate: number; // 0-1
  fillRate: number; // 0-1
  risk: RiskLevel;
  score: number; // 0-100 overall
  moq: number;
  contractExpiry: string;
  skusSupplied: number;
  spendYtd: number;
  certifications: string[];
  trend: number[];
}

export type SupplierSort = "price" | "leadTime" | "reliability" | "risk" | "score";

export interface SupplierRecommendation {
  supplierId: string;
  sku: string;
  summary: string;
  reasons: string[];
  confidence: number;
}

// ---------------------------------------------------------------- logistics
export type ShipmentStatus = "in_transit" | "delayed" | "delivered" | "at_customs" | "pending";
export type TransportMode = "ocean" | "air" | "road" | "rail";

export interface Shipment {
  id: string;
  poNumber: string;
  sku: string;
  product: string;
  supplier: string;
  origin: string;
  destination: string;
  carrier: string;
  mode: TransportMode;
  status: ShipmentStatus;
  shippedAt: string;
  eta: string;
  promisedDate: string;
  delayDays: number;
  progress: number; // 0-100
  units: number;
  lastEvent: string;
}

export interface CarrierPerformance {
  carrier: string;
  mode: TransportMode;
  onTimeRate: number;
  avgTransitDays: number;
  costPerKg: number;
  activeShipments: number;
  trend: number[];
}

export interface LogisticsSummary {
  active: number;
  delayed: number;
  onTimeRate: number;
  avgDelayDays: number;
  inTransitValue: number;
  deliveryForecast: { label: string; expected: number; atRisk: number }[];
  carriers: CarrierPerformance[];
  lanes: { origin: string; destination: string; shipments: number; delayed: number }[];
}

// ---------------------------------------------------------------- agents
export type AgentId = "supervisor" | "demand" | "inventory" | "supplier" | "logistics" | "rag" | "research";
/** Pipeline steps shown in the Copilot: graph nodes that are not specialist agents plus the agents. */
export type PipelineStep = "guard" | "classifier" | AgentId | "approval" | "synthesizer" | "validator";
export type AgentHealth = "operational" | "degraded" | "offline";

export interface AgentInfo {
  id: AgentId;
  name: string;
  purpose: string;
  status: AgentHealth;
  model: string;
  tools: string[];
  avgLatencyMs: number;
  p95LatencyMs: number;
  successRate: number;
  tasksCompleted: number;
  tasksToday: number;
  lastActive: string;
  latencyTrend: number[];
  recentActivity: { timestamp: string; message: string; outcome: "success" | "failed" | "escalated" }[];
}

// ---------------------------------------------------------------- documents / RAG
export type DocumentStatus = "indexed" | "processing" | "failed";
export type DocumentType = "procurement_policy" | "supplier_contract" | "inventory_policy" | "shipping_policy" | "sop";
export type Classification = "public" | "internal" | "restricted";

export interface DocumentItem {
  id: string;
  name: string;
  format: "pdf" | "docx" | "xlsx" | "pptx" | "csv" | "md" | "txt" | "png";
  type: DocumentType;
  classification: Classification;
  updatedAt: string;
  uploadedBy: string;
  chunks: number;
  sizeKb: number;
  status: DocumentStatus;
  ocr: boolean;
  error?: string;
}

export interface DocumentStats {
  total: number;
  indexed: number;
  processing: number;
  failed: number;
  chunks: number;
}

export interface Citation {
  n: number;
  documentId: string;
  source: string;
  location: string;
  snippet: string;
  score: number;
}

export interface DocumentSearchResult {
  answer: string;
  citations: Citation[];
  guard: { status: "grounded" | "flagged" | "refused"; reasons: string[] };
  latencyMs: number;
}

// ---------------------------------------------------------------- activity / notifications
export interface ActivityEvent {
  id: string;
  timestamp: string;
  agent: AgentId | "system" | "user";
  kind: "workflow" | "detection" | "analysis" | "approval" | "document" | "error";
  message: string;
  severity: Severity;
  runId?: string;
  sku?: string;
  durationMs?: number;
}

export interface Notification {
  id: string;
  severity: Severity;
  title: string;
  message: string;
  createdAt: string;
  read: boolean;
  href?: string;
}

// ---------------------------------------------------------------- analytics
export interface AnalyticsData {
  period: string;
  headline: Kpi[];
  costSavings: { label: string; value: number }[];
  forecastAccuracy: { label: string; accuracy: number; target: number }[];
  stockouts: { label: string; withAi: number; baseline: number }[];
  supplierPerformance: { supplier: string; onTime: number; quality: number }[];
  deliveryPerformance: { label: string; onTime: number; late: number }[];
  aiUsage: { label: string; recommendations: number; automated: number; escalated: number }[];
}

// ---------------------------------------------------------------- copilot
export type AgentRunStatus = "waiting" | "running" | "completed" | "failed" | "skipped";

export interface ApprovalRequest {
  id: string;
  runId: string;
  sku: string;
  supplier: string;
  quantity: number;
  unitPrice: number;
  value: number;
  reason: string;
  expiresAt: string;
  status: "pending" | "approved" | "rejected" | "expired";
}

export interface RecommendationReport {
  headline: string;
  riskLevel: RiskLevel;
  summary: string;
  reasoning: string[];
  evidence: { label: string; value: string; source: AgentId }[];
  supplier?: { id: string; name: string; unitPrice: number; leadTimeDays: number; reliability: number };
  impact: string[];
  confidence: { level: "high" | "medium" | "low"; score: number };
  sources: { n: number; title: string; location: string }[];
  agentsInvolved: AgentId[];
  approval?: ApprovalRequest;
  table?: { title: string; columns: string[]; rows: (string | number)[][] };
  forecast?: ForecastPoint[];
  guard: { status: "grounded" | "flagged"; reasons: string[] };
  latencyMs: number;
  requestId: string;
}

export type CopilotEvent =
  | { type: "run_started"; runId: string; requestId: string }
  | { type: "plan"; intent: string; agents: AgentId[]; stages: AgentId[][] }
  | { type: "step"; step: PipelineStep; status: AgentRunStatus; message: string; durationMs?: number }
  | { type: "token"; text: string }
  | { type: "approval_required"; approval: ApprovalRequest }
  | { type: "report"; report: RecommendationReport }
  | { type: "error"; message: string; requestId: string };

export interface ChatRequest {
  message: string;
  sessionId?: string;
}

// ---------------------------------------------------------------- system / user
export interface CurrentUser {
  id: string;
  email: string;
  name: string;
  role: Role;
  initials: string;
}

export interface SystemStatus {
  status: "operational" | "degraded" | "outage";
  environment: Environment;
  version: string;
  services: { name: string; status: "operational" | "degraded" | "outage"; latencyMs: number }[];
}
