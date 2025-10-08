import { createApp, watch } from "vue";
import pinia from "/@/stores/index";
import App from "/@/App.vue";
import router from "/@/router";
import { directive } from "/@/directive/index";
import { i18n } from "/@/i18n/index";
import other from "/@/utils/other";

import ElementPlus from "element-plus";
import "/@/theme/index.scss";
import "@vue-flow/core/dist/style.css";
import "@vue-flow/core/dist/theme-default.css";
import VueGridLayout from "vue-grid-layout";
import globalPolling from "/@/utils/globalPolling";
import { useInstallStateStore } from "/@/stores/installState";

const app = createApp(App);

directive(app);
other.elSvg(app);

app
  .use(pinia)
  .use(router)
  .use(ElementPlus)
  .use(i18n)
  .use(VueGridLayout);

// Initialize global polling based on install state at app boot
const installStore = useInstallStateStore();

// Clear all local client-side caches/state when uninstalling
function clearClientState() {
  try { localStorage.clear(); } catch { /* noop */ }
  try { sessionStorage.clear(); } catch { /* noop */ }
  try { globalPolling.clearHistory?.(); } catch { /* noop */ }
}

// Keep install state in sync with backend periodically
let installStatePollTimer: number | null = null;
function startInstallStateAutoSync(intervalMs = 10000) {
  if (installStatePollTimer) return;
  installStatePollTimer = window.setInterval(async () => {
    try {
      const resp = await fetch("/api/install_state", { method: "GET" });
      const data = await resp.json().catch(() => null as any);
      const state = data && (data.state || data.status);
      if (state === "install" && installStore.status !== "install") {
        installStore.install();
      } else if (state === "uninstall" && installStore.status !== "uninstall") {
        installStore.uninstall();
      }
    } catch {
      // network errors ignored; keep current client state until next tick
    }
  }, Math.max(2000, intervalMs));
}

async function initInstallStateAndPolling() {
  try {
    const resp = await fetch("/api/install_state", { method: "GET" });
    const data = await resp.json().catch(() => null as any);
    const state = data && (data.state || data.status);
    if (state === "install") {
      installStore.install();
      globalPolling.start({ alarmApi: "/api/event_result", interval: 5000 }).catch(() => {});
    } else {
      installStore.uninstall();
      globalPolling.stop();
      clearClientState();
    }
  } catch {
    // If API fails, don't start polling by default
  }

  // Watch for runtime changes to install status to start/stop polling globally
  watch(
    () => installStore.status,
    (val) => {
      if (val === "install") {
        globalPolling.start({ alarmApi: "/api/event_result", interval: 5000 }).catch(() => {});
      } else {
        globalPolling.stop();
        clearClientState();
      }
    },
    { immediate: false }
  );

  // Start background sync so status stays updated with server changes
  startInstallStateAutoSync(10000);
}

initInstallStateAndPolling();

app.mount("#app");
