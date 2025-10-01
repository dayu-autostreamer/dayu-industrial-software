<template>
  <div class="home-container layout-pd">
    <!-- Data Source Selection Row -->
    <el-row :gutter="15" class="home-card-two mb15">
      <el-col :xs="24" :sm="24" :md="24" :lg="24" :xl="24">
        <div class="home-card-item data-source-container"
             :class="{ 'source-loading': isSourceLoading }">
          <div class="flex-margin flex w100">
            <div class="flex-auto" style="font-weight: bold">
              选择数据源： &nbsp;
              <el-select
                  v-model="selectedDataSource"
                  :disabled="isSourceLoading"
                  placeholder="请选择数据源"
                  class="compact-select"
              >
                <el-option
                    v-for="item in dataSourceList"
                    :key="item.id"
                    :label="item.label"
                    :value="item.id"
                />
              </el-select>

            </div>
            <div v-if="isSourceLoading" class="loading-overlay">
              <i class="el-icon-loading"></i>
              <span>正在加载可视化...</span>
            </div>
          </div>
        </div>
      </el-col>
    </el-row>

    <!-- Time Range Selection Row (refactored into a single grid) -->
    <el-row :gutter="15" class="time-range-row mb15">
      <el-col :span="24">
        <div class="home-card-item time-range-grid">
          <!-- Row 1: start | end | status -->
          <div class="time-cell time-start">
            <span class="time-range-label">开始时间：</span>
            <el-date-picker
                v-model="timeRange.start"
                type="datetime"
                placeholder="选择开始时间"
                format="YYYY-MM-DD HH:mm:ss"
                value-format="X"
                :disabled-date="disabledStartDate"
                @change="handleTimeRangeChange"
            />
          </div>
          <div class="time-cell time-end">
            <span class="time-range-label">结束时间：</span>
            <el-date-picker
                v-model="timeRange.end"
                type="datetime"
                placeholder="选择结束时间"
                format="YYYY-MM-DD HH:mm:ss"
                value-format="X"
                :disabled-date="disabledEndDate"
                @change="handleTimeRangeChange"
            />
          </div>
          <div class="time-cell time-status">
            <span class="time-range-label">状态：</span>
            <span class="status-full" v-if="isTimeRangeApplied">
              已应用：{{ formatTimeRangeDisplay() }}
            </span>
            <span class="status-full" v-else>
              未应用：请选择时间区间后点击“应用区间”
            </span>
          </div>

          <!-- Row 2: actions spanning all columns -->
          <div class="time-cell time-actions">
            <el-button
                type="primary"
                :disabled="!timeRange.start || !timeRange.end"
                @click="applyTimeRange"
            >
              应用区间
            </el-button>
            <el-button type="info" @click="clearTimeRange">清除区间</el-button>
            <el-button @click="resetTimeRange">重置为当前</el-button>
          </div>
        </div>
      </el-col>
    </el-row>

    <!-- Visualization Controls Row -->
    <el-row class="viz-controls-row mb15">
      <el-col :span="24">
        <div class="viz-controls-panel">
          <div class="control-group">
            <h4>已激活的可视化模块：</h4>
            <el-checkbox-group v-model="currentActiveVisualizationsArray">
              <el-checkbox
                  v-for="viz in currentVisualizationConfig"
                  :key="viz.id"
                  :label="viz.id"
                  class="module-checkbox"
              >
                {{ viz.name }}
              </el-checkbox>
            </el-checkbox-group>
          </div>
        </div>
      </el-col>
    </el-row>

    <!-- Visualization Modules Row -->
    <el-row :gutter="15" class="home-card-two mb15">
      <template v-if="!isSourceLoading">
        <el-col
            v-for="viz in currentVisualizationConfig"
            :key="getVizKey(viz)"
            :xs="24"
            :sm="24"
            :md="getVisualizationSpan(viz.size, 'md')"
            :lg="getVisualizationSpan(viz.size, 'lg')"
            :xl="getVisualizationSpan(viz.size, 'xl')"
            v-show="componentsLoaded && currentActiveVisualizations.has(viz.id)"
        >
          <div class="home-card-item viz-module">
            <div class="viz-module-header">
              <h3 class="viz-title">{{ viz.name }}</h3>
              <component
                  :is="vizControls[viz.type]"
                  :key="viz.type + '-' + viz.variablesHash"
                  v-if="vizControls[viz.type] && selectedDataSource"
                  :config="viz"
                  :variable-states="variableStates[selectedDataSource]?.[viz.id] || {}"
                  @update:variable-states="updateVariableStates(viz.id, $event)"
              />
            </div>

            <component
                :is="visualizationComponents[viz.type]"
                v-if="componentsLoaded && visualizationComponents[viz.type] && selectedDataSource && isTimeRangeApplied"
                :key="`${viz.type}-${selectedDataSource}-${viz.id}-${viz.variablesHash}-${timeRange.start}-${timeRange.end}`"
                :config="viz"
                :data="processedData[viz.id]"
                :variable-states="variableStates[selectedDataSource]?.[viz.id] || {}"
            />
            <div v-else-if="!isTimeRangeApplied" class="no-data-prompt">
              <el-empty description="请先选择并应用时间区间以显示数据"/>
            </div>
          </div>
        </el-col>
      </template>

      <template v-else>
        <el-col :span="24">
          <div class="skeleton-loading">
            <div class="skeleton-item" v-for="n in 3" :key="n"></div>
          </div>
        </el-col>
      </template>
    </el-row>
  </div>
</template>

<script>
import {markRaw, reactive, toRaw, watch} from 'vue'
import mitt from 'mitt'
import {ElMessage} from "element-plus";

const emitter = mitt()

export default {
  data() {
    // 设置默认时间为当天
    const today = new Date();
    const startOfDay = new Date(today.getFullYear(), today.getMonth(), today.getDate());
    const endOfDay = new Date(today.getFullYear(), today.getMonth(), today.getDate(), 23, 59, 59);

    return {
      selectedDataSource: null,
      dataSourceList: [],
      bufferedTaskCache: reactive({}),
      maxBufferedTaskCacheSize: 100000,
      componentsLoaded: false,
      visualizationConfig: {},
      activeVisualizations: {},
      variableStates: {},
      visualizationComponents: {},
      vizControls: {},
      pollingInterval: null,

      isSourceLoading: false,
      isUploading: false,

      // 新增时间区间相关数据
      timeRange: {
        start: Math.floor(startOfDay.getTime() / 1000), // 转换为秒级时间戳
        end: Math.floor(endOfDay.getTime() / 1000)
      },
      isTimeRangeApplied: false, // 标记时间区间是否已应用
      appliedTimeRange: {} // 实际应用的时间区间
    }
  },
  computed: {
    processedData() {
      const result = {}

      // 如果时间区间未应用，返回空数据
      if (!this.isTimeRangeApplied) {
        this.currentVisualizationConfig.forEach(viz => {
          result[viz.id] = []
        })
        return result
      }

      this.currentVisualizationConfig.forEach(viz => {
        result[viz.id] = this.processVizData(viz)
      })
      return result
    },
    currentVisualizationConfig() {
      const configs = this.visualizationConfig[this.selectedDataSource] || [];
      // 过滤掉类型为 'image' 或 'topology' 的可视化配置
      return configs.filter(viz => viz.type !== 'image' && viz.type !== 'topology');
    },
    currentActiveVisualizations() {
      console.log('activeVisualizations:', this.activeVisualizations[this.selectedDataSource])
      return this.activeVisualizations[this.selectedDataSource] || new Set()
    },
    currentActiveVisualizationsArray: {
      get() {
        return Array.from(this.currentActiveVisualizations)
      },
      set(newVal) {
        this.activeVisualizations[this.selectedDataSource] = new Set(newVal)
      }
    },
  },

  async created() {
    this.dataSourceList.forEach(source => {
      this.bufferedTaskCache[source.id] = reactive([])
    })

    watch(
        () => this.bufferedTaskCache,
        (newVal) => {
          // console.log('Cache updated:', newVal)
        },
        {deep: true}
    )

    await this.autoRegisterComponents()
    this.componentsLoaded = true
    await this.fetchDataSourceList()
    // 移除自动轮询，改为手动触发
    // this.setupDataPolling()

    emitter.on('force-update-charts', () => {
      this.$nextTick(() => {
        if (!this.selectedDataSource) return
        this.currentVisualizationConfig.forEach(viz => {
          this.variableStates[this.selectedDataSource][viz.id] =
              {...this.variableStates[this.selectedDataSource][viz.id]}
        })
      })
    })
  },
  watch: {
    selectedDataSource(newVal) {
      if (newVal) {
        this.handleSourceChange(newVal)
      }
    }
  },
  methods: {
    // 时间区间相关方法
    disabledStartDate(time) {
      // 开始时间不能晚于当前结束时间
      if (this.timeRange.end) {
        return time.getTime() / 1000 > this.timeRange.end;
      }
      return false;
    },

    disabledEndDate(time) {
      // 结束时间不能早于当前开始时间
      if (this.timeRange.start) {
        return time.getTime() / 1000 < this.timeRange.start;
      }
      return false;
    },

    handleTimeRangeChange() {
      // 时间选择变化时，自动取消应用状态
      this.isTimeRangeApplied = false;
    },

    applyTimeRange() {
      if (!this.timeRange.start || !this.timeRange.end) {
        ElMessage.warning('请选择完整的时间区间');
        return;
      }

      if (this.timeRange.start >= this.timeRange.end) {
        ElMessage.warning('开始时间必须早于结束时间');
        return;
      }

      this.appliedTimeRange = {
        start: this.timeRange.start,
        end: this.timeRange.end
      };
      this.isTimeRangeApplied = true;

      ElMessage.success(`时间区间已应用: ${this.formatTimeRangeDisplay()}`);

      // 应用时间区间后获取最新数据
      this.getLatestResultData().then(() => {
        // 数据更新后强制更新图表
        this.$nextTick(() => {
          emitter.emit('force-update-charts');
        });
      });
    },

    async resetTimeRange() {
      const now = new Date();
      const endTime = now;
      const startTime = new Date(now.getTime() - 10 * 1000);

      this.timeRange.start = Math.floor(startTime.getTime() / 1000);
      this.timeRange.end = Math.floor(endTime.getTime() / 1000);

      this.applyTimeRange();
    },

    clearTimeRange() {
      this.timeRange.start = null;
      this.timeRange.end = null;
      this.isTimeRangeApplied = false;
      this.appliedTimeRange = {};

      ElMessage.info('时间区间已清除');
    },

    formatTimeRangeDisplay() {
      if (!this.appliedTimeRange.start || !this.appliedTimeRange.end) {
        return '';
      }

      const startDate = new Date(this.appliedTimeRange.start * 1000);
      const endDate = new Date(this.appliedTimeRange.end * 1000);

      const formatTime = (date) => {
        return `${date.getFullYear()}-${(date.getMonth() + 1).toString().padStart(2, '0')}-${date.getDate().toString().padStart(2, '0')} ${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}:${date.getSeconds().toString().padStart(2, '0')}`;
      };

      return `${formatTime(startDate)} 至 ${formatTime(endDate)}`;
    },

    calculateVariablesHash(variables) {
      return [...variables].sort().join('|');
    },

    getVizKey(viz) {
      return `${viz.id}-${viz.variablesHash}-${viz.size}`;
    },

    arraysEqual(a, b) {
      if (a === b) return true;
      if (!Array.isArray(a) || !Array.isArray(b)) return false;
      if (a.length !== b.length) return false;
      const sortedA = [...a].sort();
      const sortedB = [...b].sort();
      return sortedA.every((val, i) => val === sortedB[i]);
    },

    async handleSourceChange(sourceId) {
      if (!sourceId || !this.dataSourceList.some(s => s.id === sourceId)) {
        console.error('Invalid source selection')
        return
      }

      this.isSourceLoading = true

      try {
        await this.fetchVisualizationConfig(sourceId)
        // 切换数据源后，如果已经应用了时间区间，获取数据
        if (this.isTimeRangeApplied) {
          await this.getLatestResultData()
        }
      } catch (e) {
        console.error('Source change failed:', e)
      } finally {
        this.isSourceLoading = false
      }

      // 切换数据源时重置时间区间应用状态
      this.isTimeRangeApplied = false;

      this.$nextTick(() => {
        emitter.emit('force-update-charts')
      })
    },

    getVisualizationSpan(size, breakpoint) {
      const baseSize = size || 1
      switch (breakpoint) {
        case 'xl':
          return Math.min(24, baseSize * 8)
        case 'lg':
          return Math.min(24, (baseSize > 2 ? 24 : baseSize * 8))
        default:
          return baseSize > 1 ? 24 : 8
      }
    },

    async autoRegisterComponents() {
      try {
        const modules = import.meta.glob('./visualization/*Template.vue')
        const controls = import.meta.glob('./visualization/*Controls.vue')

        await Promise.all([
          ...Object.entries(modules).map(async ([path, loader]) => {
            const type = path.split('/').pop().replace('Template.vue', '').toLowerCase()
            try {
              const comp = await loader()
              this.visualizationComponents[type] = markRaw(comp.default)
              console.log('Successfully registered:', type)
            } catch (e) {
              console.error(`Failed to load ${type} template:`, e)
            }
          }),
          ...Object.entries(controls).map(async ([path, loader]) => {
            const type = path.split('/').pop().replace('Controls.vue', '').toLowerCase()
            try {
              const comp = await loader()
              this.vizControls[type] = markRaw(comp.default)
              console.log('Successfully registered control:', type)
            } catch (e) {
              console.error(`Failed to load ${type} control:`, e)
            }
          })
        ])
      } catch (error) {
        console.error('Component auto-registration failed:', error)
      }
    },

    processVizData(vizConfig) {
      const sourceId = this.selectedDataSource
      if (!sourceId || !this.bufferedTaskCache[sourceId]) return []

      const validVizIds = new Set(this.currentVisualizationConfig.map(v => String(v.id)))

      // 根据应用的时间区间过滤数据
      const filteredData = this.bufferedTaskCache[sourceId]
          .filter(task => {
            // 检查任务是否在时间区间内
            const taskTime = task.task_start_time;
            if (taskTime === 'unknown') return false;

            const taskTimestamp = parseInt(taskTime);
            if (isNaN(taskTimestamp)) return false;

            if (this.isTimeRangeApplied && this.appliedTimeRange.start && this.appliedTimeRange.end) {
              if (taskTimestamp < this.appliedTimeRange.start || taskTimestamp > this.appliedTimeRange.end) {
                return false;
              }
            }

            return task.data?.some(item =>
                validVizIds.has(String(item.id)) &&
                String(item.id) === String(vizConfig.id))
          })
          .map(task => {
            const vizDataItem = task.data.find(item => String(item.id) === String(vizConfig.id))
            return {
              taskId: String(task.task_id),
              taskStartTime: task.task_start_time,
              ...(vizDataItem?.data || {})
            }
          })

      return filteredData
    },

    updateVariableStates(vizId, newStates) {
      if (!this.selectedDataSource) return

      const validVars = this.currentVisualizationConfig
          .find(v => v.id === vizId)
          ?.variables || []

      this.variableStates[this.selectedDataSource][vizId] = validVars.reduce((acc, varName) => {
        acc[varName] = newStates[varName] ?? true
        return acc
      }, {})

      emitter.emit('force-update-charts')
    },

    async fetchDataSourceList() {
      try {
        const response = await fetch('/api/source_list')
        const data = await response.json()

        this.dataSourceList = data.map(source => ({
          ...source,
          id: String(source.id)
        }))
        this.dataSourceList.forEach(source => {
          this.bufferedTaskCache[source.id] = reactive([])
        })
      } catch (error) {
        console.error('Failed to fetch data sources:', error)
      }
    },

    async fetchVisualizationConfig(sourceId) {
      try {
        const response = await fetch(`/api/free_visualization_config/`)
        const data = await response.json()

        const processedConfig = data.map(viz => reactive({
          ...viz,
          id: String(viz.id),
          variables: [...(viz.variables || [])],
          size: Math.min(3, Math.max(1, parseInt(viz.size) || 1)),
          variablesHash: this.calculateVariablesHash(viz.variables || [])
        }));

        this.visualizationConfig[sourceId] = processedConfig

        this.activeVisualizations[sourceId] = new Set()
        this.variableStates[sourceId] = reactive({})

        processedConfig.forEach(viz => {
          this.activeVisualizations[sourceId].add(viz.id)

          this.variableStates[sourceId][viz.id] = viz.variables.reduce((acc, varName) => {
            acc[varName] = true
            return acc
          }, {})
        })
        console.log('Initialized variable states:', toRaw(this.variableStates))
      } catch (error) {
        console.error('Failed to fetch visualization config:', error)
      }
    },

    async getLatestResultData() {
      try {
        const response = await fetch('/api/free_task_result')
        const data = await response.json()

        const newCache = {}
        const configUpdates = {}

        Object.entries(data).forEach(([sourceIdStr, tasks]) => {
          const sourceId = String(sourceIdStr)
          if (!Array.isArray(tasks)) return

          const validTasks = tasks
              .filter(task => task?.task_id && Array.isArray(task.data))
              .map(task => ({
                task_id: task.task_id,
                task_start_time: task.task_start_time || 'unknown',
                data: task.data.map(item => ({
                  id: String(item.id) || 'unknown',
                  data: item.data || {}
                }))
              }))

          newCache[sourceId] = validTasks

          tasks.forEach(task => {
            task.data?.forEach(item => {
              const vizId = String(item.id)
              const newVariables = Object.keys(item.data || {})

              const vizConfig = (this.visualizationConfig[sourceId] || [])
                  .find(v => v.id === vizId)

              if (vizConfig && !this.arraysEqual(vizConfig.variables, newVariables)) {
                configUpdates[sourceId] = configUpdates[sourceId] || []
                configUpdates[sourceId].push({
                  vizId,
                  newVariables
                })
              }
            })
          })
        })

        this.bufferedTaskCache = newCache
      } catch (error) {
        console.error('Error fetching task results:', error)
      }
    },

    showMsg(state, msg) {
      if (state === 'success') {
        ElMessage({
          message: msg,
          showClose: true,
          type: "success",
          duration: 3000,
        });
      } else {
        ElMessage({
          message: msg,
          showClose: true,
          type: "error",
          duration: 3000,
        });
      }
    },
  },
}
</script>

<style scoped>
.home-container {
  overflow: hidden;
  padding: 16px;
}

.data-source-container {
  height: auto;
  padding: 8px 12px;
}

.compact-select {
  width: 70%;
}

.compact-select :deep(.el-input__inner) {
  height: 32px;
  line-height: 32px;
}


/* 时间区间选择器样式（栅格布局） */
.time-range-row {
  margin-top: 15px;
}

/* Grid: 320px | 320px | auto; Buttons row spans all columns */
.time-range-grid {
  padding: 12px;
  display: grid;
  grid-template-columns: 320px 320px 1fr;
  grid-auto-rows: minmax(40px, auto);
  row-gap: 12px;
  column-gap: 12px;
  align-items: center;
  overflow-x: auto; /* 保证三项同一行且完整显示 */
}

/* 小屏仍保持同一行：允许横向滚动显示完整内容 */
@media (max-width: 767.98px) {
  .time-range-grid {
    grid-template-columns: 320px 320px minmax(320px, 1fr);
  }
}

.time-cell {
  display: flex;
  align-items: center;
  min-width: 0;
  white-space: nowrap; /* 保持单行显示 */
}

/* Actions 行独占第二行，跨越所有列 */
.time-actions {
  grid-column: 1 / -1;
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap; /* 窄屏按钮可换行 */
}

.time-range-label {
  font-weight: bold;
  margin-right: 8px;
}

/* 日期选择器宽度与列宽一致 */
.time-start :deep(.el-date-editor),
.time-end :deep(.el-date-editor) {
  width: 100%;
}

/* 完整状态文本：不截断，不省略 */
.status-full {
  color: var(--el-text-color-primary);
}

.viz-controls-row {
  margin-top: 20px;
}

.viz-controls-panel {
  background: var(--el-bg-color);
  border-radius: 4px;
  padding: 15px;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, .1);
}

.control-group {
  margin-bottom: 8px;
}

.control-group h4 {
  margin-bottom: 10px;
  color: var(--el-text-color-primary);
}

.module-checkbox {
  margin-right: 20px;
  margin-bottom: 8px;
}

.viz-module {
  height: 500px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  margin-top: 15px;
  transition: all 0.3s ease;
}

.viz-module-header {
  padding: 12px;
  border-bottom: 1px solid var(--el-border-color-light);
}

.viz-title {
  margin: 0 0 8px 0;
  font-size: 1.1em;
  color: var(--el-text-color-primary);
  text-align: center;
}

.home-card-item {
  background: var(--el-bg-color);
  border-radius: 4px;
  border: 1px solid var(--el-border-color-light);
}

/* 确保容器尺寸正确 */
.viz-module {
  height: 500px !important;
  min-height: 500px;
  transform: translateZ(0);
  contain: strict;
}

/* 修复ECharts容器尺寸 */
.chart-wrapper {
  width: 100% !important;
  height: 100% !important;
  min-height: 400px !important;
}

/* 无数据提示样式 */
.no-data-prompt {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #909399;
}

.source-loading {
  position: relative;
}

.source-loading:after {
  content: "Loading...";
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
}

.loading-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(255, 255, 255, 0.9);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10;
}

.loading-overlay i {
  font-size: 24px;
  margin-right: 8px;
  animation: rotating 2s linear infinite;
}

.loading-overlay span {
  color: #409EFF;
  font-weight: 500;
}

/* 骨架屏加载动画 */
.skeleton-loading {
  padding: 20px;
}

.skeleton-loading .skeleton-item {
  height: 200px;
  background: #f5f7fa;
  border-radius: 4px;
  margin-bottom: 15px;
  position: relative;
  overflow: hidden;
}

.skeleton-loading .skeleton-item::after {
  content: "";
  position: absolute;
  top: 0;
  left: -100%;
  width: 100%;
  height: 100%;
  background: linear-gradient(
      90deg,
      transparent,
      rgba(255, 255, 255, 0.6),
      transparent
  );
  animation: skeleton-flash 1.5s infinite;
}

/* 动画定义 */
@keyframes rotating {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

@keyframes skeleton-flash {
  100% {
    left: 100%;
  }
}

/* 原有数据源容器添加定位 */
.data-source-container {
  position: relative;
  min-height: 60px;
}

.upload-config-btn {
  transition: opacity 0.3s ease;
}

.upload-config-btn.is-disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
</style>