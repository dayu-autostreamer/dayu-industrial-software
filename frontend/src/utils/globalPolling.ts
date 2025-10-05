// filepath: /Users/onecheck/PycharmProjects/dayu-industrial-software/frontend/src/utils/globalPolling.ts
import { ElMessage } from 'element-plus';

export type AlarmItem = any;

interface StartOptions {
  alarmApi?: string;
  interval?: number;
}

// A simple, idempotent global polling singleton
class GlobalPollingService {
  private intervalId: number | null = null;
  private running = false;
  private interval = 5000;
  private alarmApi = '/api/event_result';
  private lastSeen: Set<string> = new Set();
  private lastRun = 0;

  configure(opts: StartOptions) {
    if (opts.alarmApi) this.alarmApi = opts.alarmApi;
    if (opts.interval && opts.interval > 500) this.interval = opts.interval;
  }

  isRunning() {
    return this.running;
  }

  async start(opts: StartOptions = {}) {
    this.configure(opts);
    if (this.running) return;
    this.running = true;

    // Do one poll immediately, then set interval
    await this.doPollOnce().catch(() => {});

    // Use window.setInterval to ensure number id in browsers
    this.intervalId = window.setInterval(() => {
      this.doPollOnce().catch(() => {});
    }, this.interval);
  }

  stop() {
    if (this.intervalId) {
      clearInterval(this.intervalId);
      this.intervalId = null;
    }
    this.running = false;
    this.lastSeen.clear();
  }

  private alarmKey(item: AlarmItem): string {
    try {
      if (!item) return 'null';
      if (item.id !== undefined) return String(item.id);
      if (item.timestamp !== undefined && (item.message !== undefined || item.msg !== undefined)) {
        return `${String(item.timestamp)}|${String(item.message ?? item.msg)}`;
      }
      return JSON.stringify(item);
    } catch {
      return String(item);
    }
  }

  private extractList(data: any): AlarmItem[] {
    if (!data) return [];
    if (Array.isArray(data)) return data;
    if (Array.isArray(data.data)) return data.data;
    return [];
  }

  private async doPollOnce() {
    // Debounce in case of overlapping calls
    const now = Date.now();
    if (now - this.lastRun < 200) return;
    this.lastRun = now;

    const resp = await fetch(this.alarmApi, { method: 'GET' });
    let json: any = null;
    try { json = await resp.json(); } catch { json = null; }
    const alarms = this.extractList(json);
    if (!alarms || alarms.length === 0) return;

    for (const item of alarms) {
      const key = this.alarmKey(item);
      if (this.lastSeen.has(key)) continue;
      this.lastSeen.add(key);
      try {
        const msg = (typeof item === 'string') ? item : (item.message || item.msg || '');
        const text = msg ? `${msg}更多细节请前往事件触发任务查看!` : JSON.stringify(item);
        ElMessage({ message: text, type: 'warning', duration: 6000, showClose: true, grouping: false });
      } catch {
        // fallback
        ElMessage({ message: String(item), type: 'warning', duration: 6000, showClose: true, grouping: false });
      }
    }

    if (this.lastSeen.size > 2000) {
      // keep recent 1000
      this.lastSeen = new Set(Array.from(this.lastSeen).slice(-1000));
    }
  }
}

// Expose a single instance and also attach to window for safety (avoid duplicates)
const w = window as any;
const globalPolling: GlobalPollingService = w.__globalPollingInstance || new GlobalPollingService();
if (!w.__globalPollingInstance) {
  w.__globalPollingInstance = globalPolling;
}

export default globalPolling;

