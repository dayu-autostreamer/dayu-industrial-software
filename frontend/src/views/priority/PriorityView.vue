<template>
  <div class="priority-view">
    <!-- 未选择 node：不显示队列，仅展示提示 -->
    <div v-if="!isNodeSelected" class="empty-wrap">
      <el-empty description="请选择节点以查看队列"/>
    </div>

    <!-- 已选择 node -->
    <div v-else>
      <!-- 顶部说明与图例 -->
      <div class="legend">
        <div class="legend-left">
          <span class="legend-title">优先级队列视图</span>
          <span class="hint">（队首 → 队尾；数值越大越优先）</span>
        </div>
        <div class="legend-right">
          <span class="range">优先级数量：0 ~ {{ Math.max(queueCount - 1, 0) }}</span>
        </div>
      </div>

      <!-- 服务横向滚动：service 之间横排，屏幕放不下可横向滑动 -->
      <div class="services-strip">
        <div
            v-for="svc in serviceNames"
            :key="svc"
            class="service-card"
        >
          <!-- service 标题与统计 -->
          <div class="service-header" style="flex-direction: column; align-items: flex-start; gap: 2px;">
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

            <div class="service-actions">
              <label class="toggle">
                <input type="checkbox" v-model="onlyNonEmpty" />
                <span>只看非空</span>
              </label>
              <div class="actions-right">
                <button class="text-btn" @click="expandAll(svc)">展开全部</button>
                <span class="sep">|</span>
                <button class="text-btn" @click="collapseAll(svc)">折叠全部</button>
              </div>
            </div>
          </div>

          <!-- 队列纵向排列；优先显示 priority_num 条（P0..P(n-1)） -->
          <template v-if="queueCount > 0">
            <div class="queues-list">
              <div
                  v-for="idx in queueIndices(svc)"
                  :key="idx"
                  class="queue-lane"
                  :class="{'is-empty': getQueue(svc, idx).length === 0}"
              >
                <div class="lane-header">
                  <span class="lane-title">P{{ idx }}</span>
                  <div class="lane-right">
                    <span v-if="getQueue(svc, idx).length === 0" class="lane-badge">空</span>
                    <span v-else class="lane-count">{{ getQueue(svc, idx).length }} 项</span>
                    <button class="lane-toggle" @click="toggleLane(svc, idx)">{{ isExpanded(svc, idx) ? '收起' : '展开' }}</button>
                  </div>
                </div>

                <!-- 单条优先级队列：队首 → 队尾 -->
                <div class="lane-track">
                  <div class="arrow-head">队首</div>

                  <div class="tasks-scroller" :class="{ wrap: isExpanded(svc, idx) }">
                    <div
                        v-for="(task, tIndex) in getQueue(svc, idx)"
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

                    <!-- 空队列占位，保持“形状” -->
                    <div v-if="getQueue(svc, idx).length === 0" class="empty-placeholder">
                      <span>（空队列）</span>
                    </div>
                  </div>

                  <div class="arrow-tail">队尾</div>
                </div>
              </div>
            </div>
          </template>

          <!-- 未拿到 priority_num 的兜底提示（一般不会发生） -->
          <template v-else>
            <div class="no-priority">
              <el-empty description="未获取到队列级别（priority_num）"/>
            </div>
          </template>
        </div>
        <!-- /service-card -->
      </div>
      <!-- /services-strip -->
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
    // 可能是数组（服务名列表），也可能是对象（node -> [services]）
    service: {
      type: [Array, Object],
      default: () => []
    },
    // /api/priority_queue/{node} 返回：{ serviceName: [ [task...], [], ... ] }
    queue_result: {
      type: Object,
      default: () => null
    },
    // 当前选中的 node 名（来自父组件）
    selectedNode: {
      type: [String, null],
      default: null
    }
  },
  data() {
    return {
      // 只显示非空队列（作用于当前组件内所有 service 卡片）
      onlyNonEmpty: false,
      // 展开状态映射：{ [svc]: { [idx]: true } }
      expanded: {}
    };
  },
  computed: {
    // 是否已选择 node
    isNodeSelected() {
      if (this.selectedNode && String(this.selectedNode).trim() !== '') return true;
      if (this.queue_result && Object.keys(this.queue_result).length > 0) return true;
      return false;
    },
    // service 名列表：在“已选择 node”才展示
    serviceNames() {
      if (!this.isNodeSelected) return [];
      // 若有队列数据，用其 key（更准确）
      if (this.queue_result && Object.keys(this.queue_result).length) {
        return Object.keys(this.queue_result);
      }
      // 其次：根据 selectedNode 在 service 映射中取
      if (this.selectedNode && this.service && typeof this.service === 'object' && !Array.isArray(this.service)) {
        const arr = this.service[this.selectedNode] || [];
        return Array.isArray(arr) ? arr : [];
      }
      // 兜底：service 为数组时直接返回
      if (Array.isArray(this.service)) {
        return this.service;
      }
      return [];
    },
    // 队列数量：优先用 priority_num；否则尝试从 queue_result 推断
    // 取值范围 0..(queueCount-1) 共 queueCount 个
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
        return {total: 0, nonEmpty: 0};
      }
      const lanes = this.queue_result[svc] || [];
      let total = 0;
      let nonEmpty = 0;
      lanes.forEach(q => {
        const len = Array.isArray(q) ? q.length : 0;
        total += len;
        if (len > 0) nonEmpty += 1;
      });
      return {total, nonEmpty};
    },
    // 安全显示（允许 0）
    safe(v) {
      return (v === 0 || v) ? v : '-';
    },
    // 展示等级数字（无值→破折号）
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
      const light = 85 - (85 - 42) * t; // 亮度 85% → 42%
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
    // 根据重要性/紧急度生成徽章样式（红系/蓝系）
    badgeStyle(kind, level) {
      const t = this.to01(level);
      if (t === null) {
        return {background: '#dcdfe6', color: '#606266'};
      }
      const h = kind === 'imp' ? 0 : 210;
      const s = kind === 'imp' ? 78 : 72;
      return {background: this.hslColor(h, s, t), color: '#fff'};
    },
    // ===== 新增：可见队列索引（支持“只看非空”） =====
    queueIndices(svc) {
      const all = Array.from({ length: this.queueCount }, (_, i) => i);
      if (!this.onlyNonEmpty) return all;
      return all.filter(i => this.getQueue(svc, i).length > 0);
    },
    // ===== 新增：展开/折叠状态 & 操作 =====
    isExpanded(svc, idx) {
      return !!(this.expanded[svc] && this.expanded[svc][idx]);
    },
    toggleLane(svc, idx) {
      const svcMap = this.expanded[svc] ? { ...this.expanded[svc] } : {};
      svcMap[idx] = !svcMap[idx];
      this.expanded = { ...this.expanded, [svc]: svcMap };
    },
    expandAll(svc) {
      const map = {};
      for (let i = 0; i < this.queueCount; i++) {
        if (!this.onlyNonEmpty || this.getQueue(svc, i).length > 0) map[i] = true;
      }
      this.expanded = { ...this.expanded, [svc]: map };
    },
    collapseAll(svc) {
      this.expanded = { ...this.expanded, [svc]: {} };
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
  height: 100%;
}

.empty-wrap {
  padding-top: 10vh;
}

/* 顶部图例条 */
.legend {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: var(--el-color-white);
  border: 1px solid var(--next-border-color-light);
  border-radius: 10px;
  padding: 10px 14px;
  box-shadow: 0 2px 10px var(--next-color-dark-hover);
  margin-bottom: 28px;

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
      font-size: 12px;
      color: var(--el-text-color-regular);
      background: #f5f7fa;
      border: 1px dashed #e4e7ed;
      padding: 2px 8px;
      border-radius: 999px;
    }
  }
}

/* 服务横向滚动条：service 之间横排，超出可横向滚动 */
.services-strip {
  display: flex;
  flex-direction: row;
  gap: 16px;
  overflow-x: auto;
  overflow-y: hidden;
  padding-bottom: 6px;
  scroll-behavior: smooth;
  min-height: 260px;
}

/* service 卡片（固定最小宽度，便于横向滑动） */
.service-card {
  flex: 0 0 auto;
  min-width: 420px;
  max-width: 520px;
  background: var(--el-color-white);
  border: 1px solid var(--next-border-color-light);
  border-radius: 14px;
  padding: 14px;
  transition: box-shadow .2s ease;
  display: flex;
  flex-direction: column;
  max-height: 78vh; /* 控制卡片高度，内部纵向滚动 */
  &:hover {
    box-shadow: 0 4px 16px var(--next-color-dark-hover);
  }
}

.service-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;

  .service-title {
    display: inline-flex;
    align-items: center;
    gap: 8px;

    .dot {
      width: 10px;
      height: 10px;
      border-radius: 50%;
      background: linear-gradient(135deg, #409eff, #53d1ff);
      box-shadow: 0 0 6px rgba(83, 209, 255, .6);
    }

    .name {
      font-weight: 700;
      font-size: 16px;
      color: var(--el-text-color-primary);
    }
  }

  .service-stats {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    font-size: 13px;

    .stat {
      color: var(--el-text-color-regular);
    }

    .muted {
      color: var(--el-text-color-secondary);
    }

    .divider {
      color: var(--el-text-color-disabled);
    }
  }

  /* 新增：视图控制条 */
  .service-actions {
    width: 100%;
    margin-top: 6px;
    display: flex;
    align-items: center;
    justify-content: space-between;

    .toggle {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      font-size: 12px;
      color: var(--el-text-color-secondary);
      input { transform: translateY(1px); }
    }

    .actions-right {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      .sep { color: var(--el-text-color-disabled); }
      .text-btn {
        font-size: 12px;
        color: var(--el-text-color-regular);
        background: transparent;
        border: none;
        cursor: pointer;
        padding: 2px 4px;
      }
      .text-btn:hover {
        color: var(--el-text-color-primary);
        text-decoration: underline;
      }
    }
  }
}

/* 队列纵向列表：service 卡片内部可纵向滚动 */
.queues-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  overflow-y: auto;
  padding-right: 6px; /* 为滚动条留白 */
}

/* 单条优先级队列（轨道） */
.queue-lane {
  border: 1px solid var(--next-border-color-light);
  border-radius: 10px;
  background: var(--next-bg-color);
  overflow: hidden;
  display: flex;
  flex-direction: column;

  &.is-empty {
    border-style: dashed;

    .lane-track {
      background-image: repeating-linear-gradient(45deg, transparent 0 10px, rgba(0, 0, 0, 0.03) 10px 20px);
    }
  }
}

.lane-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 10px;
  background: rgba(64, 158, 255, .08);
  border-bottom: 1px solid var(--next-border-color-light);

  .lane-title {
    font-weight: 700;
    color: var(--el-text-color-primary);
  }

  .lane-count {
    font-size: 12px;
    color: var(--el-text-color-secondary);
  }

  .lane-badge {
    font-size: 12px;
    color: #909399;
    background: #f2f6fc;
    padding: 2px 8px;
    border-radius: 999px;
    border: 1px dashed #dcdfe6;
  }

  .lane-right {
    display: inline-flex;
    align-items: center;
    gap: 8px;
  }

  .lane-toggle {
    font-size: 12px;
    background: #fff;
    border: 1px solid var(--next-border-color-light);
    border-radius: 999px;
    padding: 2px 8px;
    cursor: pointer;
  }
}

/* 轨道：左“队首” → 右“队尾”；任务横向滚动 */
.lane-track {
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: start; /* 允许中间区域按需增高 */
  gap: 8px;
  padding: 10px;

  .arrow-head, .arrow-tail {
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 12px;
    color: var(--el-text-color-secondary);
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

  /* 展开态：多行换行 + 纵向滚动，完整展示内容 */
  &.wrap {
    flex-wrap: wrap;
    align-content: flex-start;
    overflow-x: hidden;
    overflow-y: auto;
    max-height: 260px; /* 展开后的最大高度，可按需调整 */
    row-gap: 8px;
    padding-right: 10px;
  }
}

/* 单个任务芯片（队列元素） */
.task-chip {
  flex: 0 0 auto;
  min-width: 170px;
  max-width: 230px;
  border: 1px solid var(--next-border-color-light);
  background: #fff;
  border-radius: 10px;
  padding: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, .04);
  transition: transform .15s ease, box-shadow .15s ease;

  &:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 18px rgba(0, 0, 0, .08);
  }

  .chip-top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 6px;

    .chip-id {
      font-weight: 700;
      color: var(--el-text-color-primary);
    }

    .chip-badges {
      display: inline-flex;
      gap: 6px;
    }
  }

  .chip-bottom {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 12px;
    color: var(--el-text-color-secondary);

    .meta {
      white-space: nowrap;
    }
  }

  .tag {
    font-size: 11px;
    line-height: 1;
    padding: 4px 6px;
    border-radius: 999px;
    color: #fff;
    font-weight: 600;
  }
}

/* 空队列占位 */
.empty-placeholder {
  flex: 1 0 auto;
  min-width: 140px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 12px 8px;
  color: var(--el-text-color-disabled);
  font-size: 12px;
  border-radius: 8px;
  border: 1px dashed var(--next-border-color-light);
  background: #fafafa;
}

/* 没拿到 priority_num 的兜底 */
.no-priority {
  padding: 8px 0;
}
</style>
