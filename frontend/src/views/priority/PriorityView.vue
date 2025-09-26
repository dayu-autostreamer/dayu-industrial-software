<template>
  <div class="priority-view">

    <!-- 服务列表 -->
    <div v-if="serviceNames.length" class="services">
      <div
        v-for="svc in serviceNames"
        :key="svc"
        class="service-card"
      >
        <div class="service-header">
          <div class="service-title">
            <span class="dot"></span>
            <span class="name">{{ svc }}</span>
          </div>
          <div class="service-stats">
            <template v-if="hasDataFor(svc)">
              <span class="stat">队列数：{{ queueCount }}</span>
              <span class="divider">|</span>
              <span class="stat">总任务：{{ summary(svc).total }}</span>
              <span class="divider">|</span>
              <span class="stat">非空队列：{{ summary(svc).nonEmpty }}/{{ queueCount }}</span>
            </template>
            <template v-else>
              <span class="stat muted">暂无数据</span>
            </template>
          </div>
        </div>

        <!-- 每个 service 的优先级队列：P0..P(n-1) -->
        <div
          class="queues-grid"
          :style="{'grid-template-columns': 'repeat(' + Math.max(queueCount, 1) + ', minmax(260px, 1fr))'}"
        >
          <div
            v-for="idx in Math.max(queueCount, 1)"
            :key="idx"
            class="queue-lane"
            :class="{'is-empty': getQueue(svc, idx-1).length === 0}"
          >
            <div class="lane-header">
              <span class="lane-title">P{{ idx - 1 >= 0 ? idx - 1 : 0 }}</span>
              <span v-if="getQueue(svc, idx-1).length === 0" class="lane-badge">空</span>
              <span v-else class="lane-count">{{ getQueue(svc, idx-1).length }} 项</span>
            </div>

            <!-- 轨道：左“队首” → 右“队尾” -->
            <div class="lane-track">
              <div class="arrow-head">队首</div>
              <div class="tasks-scroller">
                <div
                  v-for="(task, tIndex) in getQueue(svc, idx-1)"
                  :key="tIndex"
                  class="task-chip"
                  :title="taskTooltip(task)"
                >
                  <div class="chip-top">
                    <span class="chip-id">#{{ safe(task.task_id) }}</span>
                    <div class="chip-badges">
                      <span
                        class="tag imp"
                        :style="badgeStyle('imp', task.importance)"
                      >
                        I: {{ displayLevel(task.importance) }}
                      </span>
                      <span
                        class="tag urg"
                        :style="badgeStyle('urg', task.urgency)"
                      >
                        U: {{ displayLevel(task.urgency) }}
                      </span>
                    </div>
                  </div>
                  <div class="chip-bottom">
                    <span class="meta">src: {{ safe(task.source_id) }}</span>
                  </div>
                </div>

                <!-- 空队列占位（保证可视形状） -->
                <div v-if="getQueue(svc, idx-1).length === 0" class="empty-placeholder">
                  <span>（空队列）</span>
                </div>
              </div>
              <div class="arrow-tail">队尾</div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 若没有任何 service 名称 -->
    <div v-else class="empty-services">
      <el-empty description="暂无服务可展示" />
    </div>
  </div>
</template>

<script>
export default {
  name: 'PriorityView',
  props: {
    // 每个 service 的优先级队列个数（即 level 取值个数）
    priority_num: {
      type: [Number, null],
      default: null
    },
    // 可能是数组（当前节点的服务名列表），也可能是对象（node -> [services]）
    service: {
      type: [Array, Object],
      default: () => []
    },
    // /api/priority_queue/{node} 返回：{ serviceName: [ [task...], [], ... ] }
    queue_result: {
      type: Object,
      default: () => null
    }
  },
  computed: {
    // 需要展示的 service 名列表：优先使用 queue_result 的 key；否则回退到 props.service
    serviceNames() {
      if (this.queue_result && Object.keys(this.queue_result).length) {
        return Object.keys(this.queue_result);
      }
      if (Array.isArray(this.service)) {
        return this.service;
      }
      if (this.service && typeof this.service === 'object') {
        const merged = new Set();
        Object.values(this.service).forEach(arr => {
          if (Array.isArray(arr)) arr.forEach(s => merged.add(s));
        });
        return Array.from(merged);
      }
      return [];
    },
    // 队列数量：优先用 priority_num；否则尝试从 queue_result 推断
    // 注意：level 取值为 0..(queueCount-1)，共 queueCount 个级别
    queueCount() {
      if (typeof this.priority_num === 'number' && this.priority_num > 0) return this.priority_num;
      if (this.queue_result && Object.keys(this.queue_result).length) {
        const firstSvc = Object.keys(this.queue_result)[0];
        const lanes = this.queue_result[firstSvc];
        if (Array.isArray(lanes)) return lanes.length;
      }
      return 0;
    },
    // 最大等级值（用于归一化着色）：0..(queueCount-1)
    maxLevel() {
      return Math.max(this.queueCount - 1, 0);
    }
  },
  methods: {
    hasDataFor(svc) {
      return !!(this.queue_result && this.queue_result[svc]);
    },
    // 获取指定 service 的第 idx 个优先级队列（idx 从 0 开始）
    getQueue(svc, idx) {
      if (this.queue_result && Array.isArray(this.queue_result[svc])) {
        return Array.isArray(this.queue_result[svc][idx]) ? this.queue_result[svc][idx] : [];
      } else if (this.queueCount > 0) {
        // 无数据时也显示空轨道
        return [];
      }
      return [];
    },
    // 汇总统计
    summary(svc) {
      if (!this.hasDataFor(svc)) {
        return { total: 0, nonEmpty: 0 };
      }
      const lanes = this.queue_result[svc] || [];
      let total = 0;
      let nonEmpty = 0;
      lanes.forEach(q => {
        const len = Array.isArray(q) ? q.length : 0;
        total += len;
        if (len > 0) nonEmpty += 1;
      });
      return { total, nonEmpty };
    },
    // 安全显示
    safe(v) {
      return (v === 0 || v) ? v : '-';
    },
    // 展示等级数字（若无值用破折号）
    displayLevel(v) {
      return (v === 0 || v) ? v : '—';
    },
    // 气泡提示
    taskTooltip(task) {
      const sid = this.safe(task?.source_id);
      const tid = this.safe(task?.task_id);
      const imp = this.safe(task?.importance);
      const urg = this.safe(task?.urgency);
      return `task_id: ${tid}\nsource_id: ${sid}\nimportance: ${imp}\nurgency: ${urg}`;
    },
    // 颜色映射：t ∈ [0,1] 越大越深
    hslColor(h, s, t) {
      // 亮度从 85%（低）到 42%（高），保留一定可读性
      const light = 85 - (85 - 42) * t;
      return `hsl(${h}, ${s}%, ${light}%)`;
    },
    // 将 level（0..maxLevel）转换为 t ∈ [0,1]
    to01(level) {
      if (level === 0 || level) {
        if (this.maxLevel <= 0) return (level > 0) ? 1 : 0; // 规避除零
        const t = level / this.maxLevel;
        return Math.max(0, Math.min(1, t));
      }
      return null;
    },
    // 根据重要性/紧急度生成徽章样式
    badgeStyle(kind, level) {
      const t = this.to01(level);
      if (t === null) {
        return {
          background: '#dcdfe6',
          color: '#606266'
        };
      }
      // importance 用红系（h≈0），urgency 用蓝系（h≈210）
      const h = kind === 'imp' ? 0 : 210;
      const s = kind === 'imp' ? 78 : 72;
      return {
        background: this.hslColor(h, s, t),
        color: '#fff'
      };
    }
  }
};
</script>

<style scoped lang="scss">
.priority-view {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 8px 4px 24px;
}

/* 图例条 */
.legend {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: var(--el-color-white);
  border: 1px solid var(--next-border-color-light);
  border-radius: 10px;
  padding: 10px 14px;
  box-shadow: 0 2px 10px var(--next-color-dark-hover);

  .legend-left {
    display: flex;
    align-items: baseline;
    gap: 8px;
    .legend-title {
      font-weight: 700;
      font-size: 16px;
      color: var(--el-text-color-primary);
    }
    .hint {
      font-size: 12px;
      color: var(--el-text-color-secondary);
    }
  }
  .legend-right {
    display: flex;
    align-items: center;
    gap: 10px;
    .range {
      font-size: 12px; color: var(--el-text-color-regular);
      background: #f5f7fa; border: 1px dashed #e4e7ed; padding: 2px 8px; border-radius: 999px;
    }
  }
}

/* 服务卡片 */
.services {
  display: flex;
  flex-direction: column;
  gap: 18px;
}
.service-card {
  background: var(--el-color-white);
  border: 1px solid var(--next-border-color-light);
  border-radius: 14px;
  padding: 14px;
  transition: box-shadow .2s ease;
  &:hover { box-shadow: 0 4px 16px var(--next-color-dark-hover); }
}
.service-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;

  .service-title {
    display: inline-flex; align-items: center; gap: 8px;
    .dot {
      width: 10px; height: 10px; border-radius: 50%;
      background: linear-gradient(135deg, #409eff, #53d1ff);
      box-shadow: 0 0 6px rgba(83,209,255,.6);
    }
    .name {
      font-weight: 700; font-size: 16px; color: var(--el-text-color-primary);
    }
  }
  .service-stats {
    display: inline-flex; align-items: center; gap: 8px; font-size: 13px;
    .stat { color: var(--el-text-color-regular); }
    .muted { color: var(--el-text-color-secondary); }
    .divider { color: var(--el-text-color-disabled); }
  }
}

/* 队列网格：每列一个优先级 */
.queues-grid {
  display: grid;
  gap: 12px;
  width: 100%;
}

/* 单条优先级队列（一条“轨道”） */
.queue-lane {
  border: 1px solid var(--next-border-color-light);
  border-radius: 10px;
  background: var(--next-bg-color);
  overflow: hidden;
  display: flex;
  flex-direction: column;

  &.is-empty {
    border-style: dashed;
    .lane-track { background-image: repeating-linear-gradient(45deg, transparent 0 10px, rgba(0,0,0,0.03) 10px 20px); }
  }
}

.lane-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 8px 10px;
  background: rgba(64,158,255,.08);
  border-bottom: 1px solid var(--next-border-color-light);

  .lane-title {
    font-weight: 700; color: var(--el-text-color-primary);
  }
  .lane-count {
    font-size: 12px; color: var(--el-text-color-secondary);
  }
  .lane-badge {
    font-size: 12px; color: #909399; background: #f2f6fc;
    padding: 2px 8px; border-radius: 999px; border: 1px dashed #dcdfe6;
  }
}

/* 轨道：左“队首” → 右“队尾” */
.lane-track {
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: stretch;
  gap: 8px;
  padding: 10px;

  .arrow-head, .arrow-tail {
    display: flex; align-items: center; justify-content: center;
    font-size: 12px; color: var(--el-text-color-secondary);
    min-width: 36px;
  }
}

/* 任务水平滚动区（展示队首→队尾） */
.tasks-scroller {
  position: relative;
  display: flex;
  align-items: center;
  gap: 8px;
  overflow-x: auto;
  padding: 6px;
  border-radius: 8px;
  background: var(--el-color-white);
  border: 1px dashed var(--next-border-color-light);

  /* 小箭头装饰，强调方向 */
  &::after {
    content: '→';
    position: sticky;
    right: 6px;
    margin-left: auto;
    font-size: 12px;
    color: var(--el-text-color-secondary);
  }
}

/* 单个任务芯片（队列中的一个元素） */
.task-chip {
  flex: 0 0 auto;
  min-width: 170px;
  max-width: 230px;
  border: 1px solid var(--next-border-color-light);
  background: #fff;
  border-radius: 10px;
  padding: 8px;
  box-shadow: 0 2px 8px rgba(0,0,0,.04);
  transition: transform .15s ease, box-shadow .15s ease;

  &:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 18px rgba(0,0,0,.08);
  }

  .chip-top {
    display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px;
    .chip-id { font-weight: 700; color: var(--el-text-color-primary); }
    .chip-badges { display: inline-flex; gap: 6px; }
  }
  .chip-bottom {
    display: flex; align-items: center; gap: 8px; font-size: 12px; color: var(--el-text-color-secondary);
    .meta { white-space: nowrap; }
  }

  .tag {
    font-size: 11px; line-height: 1; padding: 4px 6px; border-radius: 999px; color: #fff; font-weight: 600;
  }
}

/* 空队列占位 */
.empty-placeholder {
  flex: 1 0 auto;
  min-width: 140px;
  display: inline-flex; align-items: center; justify-content: center;
  padding: 12px 8px;
  color: var(--el-text-color-disabled);
  font-size: 12px;
  border-radius: 8px;
  border: 1px dashed var(--next-border-color-light);
  background: #fafafa;
}

/* 没有 service 可展示 */
.empty-services {
  margin-top: 16px;
}
</style>
