export interface PingTargetStat {
  name: string; // 电信 / 联通 / 移动
  latency_ms: number;
  loss_rate: number;
}

export interface NodeMetrics {
  cpu_percent: number;
  ram_used_bytes: number;
  ram_total_bytes: number;
  swap_used_bytes: number;
  swap_total_bytes: number;
  disk_used_bytes: number;
  disk_total_bytes: number;
  load_1: number;
  load_5: number;
  load_15: number;
  net_rx_rate: number; // bytes/sec
  net_tx_rate: number; // bytes/sec
  net_rx_total: number; // bytes
  net_tx_total: number; // bytes
  uptime_seconds: number;
  uptime_days: number;
  kernel_version?: string | null;
  agent_version?: string | null;
  auto_update?: boolean;
  ping_stats: PingTargetStat[];
  ping_history?: PingTargetStat[][]; // 最近 30 次测速样本
}

export interface MonitorNode {
  id: number;
  token: string | null;
  name: string;
  country: string; // hk, jp, us, sg, de, gb, etc.
  group_name: string;
  tags: string[];
  os_type: string; // debian, ubuntu, centos, alpine, arch, windows
  os_version?: string | null;
  arch?: string | null;
  cpu_cores: number;
  price: number | null;
  currency: string;
  billing_cycle: string;
  expires_at: string | null;
  days_left: number | null;
  expire_notify_enabled?: boolean | null;
  expire_notify_stages?: number[] | null;
  notified_expire_stages?: number[];
  traffic_limit_gb: number | null;
  remaining_gb: number | null;
  is_online: boolean;
  is_demo: boolean;
  is_public: boolean;
  uptime_days: number;
  last_seen_at: string | null;
  created_at: string;
  metrics: NodeMetrics;
}

export interface NotificationChannel {
  id: string;
  name: string;
  target?: string | null;
  enabled: boolean;
  status: "active" | "coming_soon" | "disabled";
  is_primary: boolean;
}

export interface MonitorSettings {
  expire_notify_enabled: boolean;
  expire_notify_stages: number[];
  email: string;
  channels: NotificationChannel[];
}

export interface MonitorSummary {
  online_count: number;
  total_count: number;
  online_segments: boolean[];
  bandwidth: {
    rx_rate: number;
    tx_rate: number;
    total_rate: number;
  };
  traffic: {
    rx_total: number;
    tx_total: number;
    total: number;
  };
  asset: {
    total_cost_cny: number;
    currency: string;
  };
  groups: Array<{ name: string; count: number }>;
  countries: Array<{ code: string; count: number }>;
}

export interface MonitorUserInfo {
  email?: string;
  is_owner: boolean;
  public_enabled: boolean;
  share_token: string | null;
}

export interface MonitorApiResponse {
  nodes: MonitorNode[];
  summary: MonitorSummary;
  user_info: MonitorUserInfo;
}

export interface HistoryPoint {
  timestamp: string;
  cpu_percent: number;
  ram_percent: number;
  disk_percent: number;
  load_1: number;
  net_rx_rate: number;
  net_tx_rate: number;
  ping_stats: PingTargetStat[];
}

export interface NodeHistoryResponse {
  node_id: number;
  name: string;
  points: HistoryPoint[];
}

export type ViewMode = "large" | "compact" | "mini" | "list";

export type SortMode = "default" | "cpu" | "ram" | "bandwidth" | "expires" | "uptime";
