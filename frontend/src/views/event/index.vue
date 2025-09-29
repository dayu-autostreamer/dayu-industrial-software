<template>
  <div class="alarm-detail-page layout-pd">
    <div class="header-row">
      <h3>告警详情查看</h3>
      <div class="controls">
        <el-select v-model="selectedSource" placeholder="选择 数据源 (不选择不显示数据)" clearable style="min-width:220px; margin-right:12px;">
          <el-option
            v-for="sid in sourceList"
            :key="sid"
            :label="sid"
            :value="sid"
          />
        </el-select>

        <el-button size="small" @click="togglePolling" :type="polling ? 'warning' : 'primary'">
          {{ polling ? '停止轮询' : '启动轮询' }}
        </el-button>

        <el-button size="small" @click="manualFetch">手动刷新</el-button>

        <el-select
          v-model="sortOrder"
          size="small"
          placeholder="排序"
          style="min-width:200px; margin-left:8px;"
          @change="onSortChange"
          clearable
        >
          <el-option label="按最旧排序（升序）" value="asc" />
          <el-option label="按最新排序（降序）" value="desc" />
        </el-select>

        <el-button size="small" type="danger" @click="clearStorage" style="margin-left:8px;">
          清空本地存储
        </el-button>
      </div>
    </div>

    <div class="meta-row" style="margin-top:12px;">
      <el-tag :type="polling ? 'success' : 'info'">{{ polling ? '轮询运行中' : '轮询已停止' }}</el-tag>
      <span style="margin-left:12px;">本地已保存告警数：<strong>{{ allAlarms.length }}</strong></span>
      <span style="margin-left:12px;" v-if="selectedSource != null">当前 数据源: <strong>{{ selectedSource }}</strong>（{{ filteredSorted.length }} 条）</span>
    </div>

    <el-card class="alarm-list-card" style="margin-top:16px;">
      <div v-if="selectedSource == null" class="empty-hint">
        请选择一个 数据源 来查看该源的告警详情（上方选择框）。已接收的告警保存在本地，不会被重复请求。
      </div>

      <div v-else>
        <el-collapse v-model="activeKeys" accordion>
          <el-collapse-item
            v-for="alarm in filteredSorted"
            :key="alarm._localKey"
            :name="alarm._localKey"
          >
            <template #title>
              <div class="alarm-title">
                <div>
                  <!-- 标题保留：第<任务序号>个任务：message -->
                  <strong>第{{ alarm.task_id }}个任务：</strong>
                  {{ alarm.message || '(无 message)' }}
                </div>
                <div class="alarm-meta">
                  <span>{{ formatTms(alarm.tms) }}</span>
                  <el-tag size="small" style="margin-left:8px;">数据源: {{ alarm.source_id }}</el-tag>
                </div>
              </div>
            </template>

            <div class="alarm-body">
              <!-- 任务时间：只显示格式化时间 -->
              <div class="detail-row">
                <div class="detail-label">任务时间：</div>
                <div class="detail-value">{{ formatTms(alarm.tms) }}</div>
              </div>

              <div class="detail-row">
                <div class="detail-label">任务序号：</div>
                <div class="detail-value">{{ alarm.task_id }}</div>
              </div>

              <!-- message 在标题已展示，详情中不再重复显示 -->
              <div class="detail-section" v-if="alarm.detailParsed && Object.keys(alarm.detailParsed).length">
                <div class="detail-section-title">详细信息：</div>
                <div class="detail-items">
                  <div v-for="(val, key) in alarm.detailParsed" :key="key" class="detail-item">
                    <div class="detail-key">{{ key }}:</div>
                    <div class="detail-val">
                      <template v-if="isImageKey(key)">
                        <img :src="normalizeImageSrc(val)" class="detail-image" alt="alarm image" />
                      </template>
                      <template v-else>
                        <div class="mono-txt">{{ stringifyVal(val) }}</div>
                      </template>
                    </div>
                  </div>
                </div>
              </div>

              <div v-else class="detail-empty">无额外 detail 信息</div>
            </div>
          </el-collapse-item>
        </el-collapse>

        <div v-if="filteredSorted.length === 0" class="no-data">当前 数据源 没有告警记录。</div>
      </div>
    </el-card>
  </div>
</template>

<script>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue';
import { ElMessage } from 'element-plus';

export default {
  name: 'SvcAlarmDetail',
  setup() {
    const ALARM_API = '/api/event_detail';
    const STORAGE_KEY = 'svc_alarms_store';

    const polling = ref(true);
    const pollingInterval = ref(5000);

    const selectedSource = ref(null);
    const sortOrder = ref('desc'); // 默认最新优先
    const activeKeys = ref([]);

    const allAlarms = ref([]);
    const intervalId = ref(null);

    function toMs(tms) {
      const num = (typeof tms === 'number') ? tms : Number(tms);
      if (!isFinite(num)) return Date.now();
      return num < 1e12 ? Math.round(num * 1000) : Math.round(num);
    }

    const sourceList = computed(() => {
      const s = new Set();
      allAlarms.value.forEach(a => {
        let sid = (a.source_id !== undefined ? a.source_id : (a.source !== undefined ? a.source : null));
        if ((sid === null || sid === undefined || String(sid).trim() === '') && a.detailParsed) {
          sid = a.detailParsed.source_id ?? a.detailParsed.source ?? a.detailParsed.sourceId ?? null;
        }
        if (sid !== null && sid !== undefined && String(sid).trim() !== '') {
          s.add(sid);
        }
      });
      return Array.from(s).sort((a, b) => String(a).localeCompare(String(b)));
    });

    function loadFromStorage() {
      try {
        const raw = localStorage.getItem(STORAGE_KEY);
        if (!raw) {
          allAlarms.value = [];
          return;
        }
        const arr = JSON.parse(raw) || [];
        allAlarms.value = arr.map((it) => {
          const copy = Object.assign({}, it);
          copy._localKey = generateLocalKey(copy);
          copy.detailParsed = parseDetail(copy.detail);
          return copy;
        });
      } catch (e) {
        console.warn('loadFromStorage error', e);
        allAlarms.value = [];
      }
    }

    function saveToStorage() {
      try {
        const toSave = allAlarms.value.map(a => ({
          message: a.message,
          source_id: a.source_id,
          task_id: a.task_id,
          detail: a.detail,
          tms: a.tms
        }));
        localStorage.setItem(STORAGE_KEY, JSON.stringify(toSave));
      } catch (e) {
        console.warn('saveToStorage error', e);
      }
    }

    function generateLocalKey(item) {
      const msg = typeof item.message === 'string' ? item.message : JSON.stringify(item.message || '');
      const base = `${item.source_id ?? ''}|${item.task_id ?? ''}|${item.tms ?? ''}|${msg.slice(0,50)}`;
      try {
        return btoa(unescape(encodeURIComponent(base))).slice(0, 24);
      } catch {
        return String(base).slice(0, 24);
      }
    }

    function parseDetail(detail) {
      if (!detail) return {};
      if (typeof detail === 'object') return detail;
      try {
        return JSON.parse(detail);
      } catch {
        return { text: String(detail) };
      }
    }

    async function fetchAlarms() {
      try {
        const resp = await fetch(ALARM_API, { method: 'GET' });
        if (!resp.ok) {
          console.warn('fetchAlarms non-ok', resp.status);
          return;
        }
        const data = await resp.json().catch(() => null);
        const alarms = Array.isArray(data) ? data : (data && Array.isArray(data.data) ? data.data : []);
        if (!alarms || alarms.length === 0) return;

        let added = 0;
        for (const raw of alarms) {
          if (!raw) continue;
          const hasAnyIdentity = (raw.source_id !== undefined && raw.source_id !== null) || (raw.task_id !== undefined && raw.task_id !== null) || (raw.tms !== undefined && raw.tms !== null) || (raw.message !== undefined && raw.message !== null);
          if (!hasAnyIdentity) continue;

          const candidate = {
            message: raw.message ?? '',
            source_id: (raw.source_id !== undefined ? raw.source_id : (raw.source !== undefined ? raw.source : '')),
            task_id: (raw.task_id !== undefined ? raw.task_id : (raw.task ?? '')),
            detail: raw.detail ?? raw.details ?? null,
            tms: raw.tms ?? Date.now()
          };

          candidate._localKey = generateLocalKey(candidate);
          if (allAlarms.value.find(a => a._localKey === candidate._localKey)) {
            continue;
          }
          candidate.detailParsed = parseDetail(candidate.detail);
          allAlarms.value.push(candidate);
          added++;
        }

        console.log('allAlarms.value:', allAlarms.value);
        console.log('sourceList.value:', sourceList.value);
        console.log('selectedSource.value:', selectedSource.value);

        if (added > 0) {
          saveToStorage();
          ElMessage.success(`接收 ${added} 条新告警并已保存`);
        }
      } catch (err) {
        console.warn('fetchAlarms error', err);
      }
    }

    async function manualFetch() {
      await fetchAlarms();
    }

    function startPolling() {
      if (intervalId.value) return;
      intervalId.value = setInterval(() => {
        fetchAlarms();
      }, pollingInterval.value);
      polling.value = true;
    }
    function stopPolling() {
      if (intervalId.value) {
        clearInterval(intervalId.value);
        intervalId.value = null;
      }
      polling.value = false;
    }
    function togglePolling() {
      if (polling.value) stopPolling(); else startPolling();
    }

    const filteredSorted = computed(() => {
      if (selectedSource.value == null) return [];
      const list = allAlarms.value.filter(a => String(a.source_id) === String(selectedSource.value));
      list.forEach(it => {
        it._tmsNum = toMs(it.tms);
      });
      list.sort((a, b) => {
        if (sortOrder.value === 'asc') return a._tmsNum - b._tmsNum;
        return b._tmsNum - a._tmsNum;
      });
      return list;
    });

    function onSortChange(val) {
      if (val === 'asc' || val === 'desc') {
        sortOrder.value = val;
        ElMessage.success(`已切换为：${val === 'asc' ? '最旧优先' : '最新优先'}`);
      }
    }

    function stringifyVal(val) {
      if (val === null || val === undefined) return '';
      if (typeof val === 'object') return JSON.stringify(val);
      return String(val);
    }

    function isImageKey(key) {
      return String(key).toLowerCase() === 'image' || String(key).toLowerCase().includes('img');
    }

    function normalizeImageSrc(val) {
      if (!val) return '';
      const s = String(val).trim();
      if (s.startsWith('data:')) return s;
      if (/^[A-Za-z0-9+/=\s]+$/.test(s) && s.length > 50) {
        return `data:image/jpg;base64,${s}`;
      }
      try {
        const maybe = typeof val === 'string' ? JSON.parse(val) : null;
        if (maybe && typeof maybe === 'object') {
          for (const k of Object.keys(maybe)) {
            const v = maybe[k];
            if (typeof v === 'string' && v.length > 50 && /^[A-Za-z0-9+/=\s]+$/.test(v)) {
              return `data:image/jpg;base64,${v}`;
            }
          }
        }
      } catch {}
      return s;
    }

    function formatTms(tms) {
      const ms = toMs(tms);
      const d = new Date(ms);
      return d.toLocaleString();
    }

    function clearStorage() {
      allAlarms.value = [];
      localStorage.removeItem(STORAGE_KEY);
      ElMessage.success('本地告警存储已清空');
    }

    onMounted(() => {
      loadFromStorage();
      fetchAlarms();
      startPolling();
    });

    onBeforeUnmount(() => {
      stopPolling();
    });

    const sortLabel = computed(() => (sortOrder.value === 'asc' ? '最旧优先' : '最新优先'));

    return {
      polling,
      selectedSource,
      sourceList,
      allAlarms,
      filteredSorted,
      activeKeys,
      sortLabel,
      sortOrder,

      manualFetch,
      togglePolling,
      onSortChange,
      clearStorage,
      stringifyVal,
      isImageKey,
      normalizeImageSrc,
      formatTms
    };
  }
};
</script>

<style scoped>
.alarm-detail-page {
  padding: 18px;
}

.header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.header-row h3 {
  margin: 0;
  font-size: 18px;
  color: var(--el-text-color-primary);
}

.controls {
  display: flex;
  align-items: center;
}

.meta-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.alarm-list-card {
  min-height: 320px;
}

.empty-hint {
  color: var(--el-text-color-placeholder);
  padding: 24px;
  text-align: center;
}

.alarm-title {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.alarm-meta {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.alarm-body {
  padding: 12px 0;
}

.detail-row {
  display: flex;
  margin-bottom: 8px;
}

.detail-label {
  width: 100px;
  color: var(--el-text-color-secondary);
}

.detail-value {
  flex: 1;
  word-break: break-all;
}

.detail-section-title {
  font-weight: 600;
  margin: 8px 0;
}

.detail-items {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.detail-item {
  display: flex;
  gap: 12px;
  align-items: flex-start;
}

.detail-key {
  width: 120px;
  color: var(--el-text-color-secondary);
  font-weight: 500;
}

.detail-val {
  flex: 1;
}

.detail-image {
  max-width: 640px;
  max-height: 480px;
  border-radius: 6px;
  border: 1px solid #eee;
}

.mono-txt {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, "Roboto Mono", "Segoe UI Mono", monospace;
  white-space: pre-wrap;
  word-break: break-word;
  background: #fafafa;
  padding: 6px;
  border-radius: 4px;
  border: 1px solid #f0f0f0;
}

.no-data {
  padding: 12px;
  color: var(--el-text-color-placeholder);
}
</style>
