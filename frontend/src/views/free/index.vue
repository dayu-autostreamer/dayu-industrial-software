<template>
  <div class="home-container layout-pd">
    <!-- Data Source Selection Row -->
    <el-row :gutter="15" class="home-card-two mb15">
      <el-col :xs="24" :sm="24" :md="20" :lg="20" :xl="20">
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

              <el-button
                  ref="uploadButton"
                  type="primary"
                  :disabled="!selectedDataSource"
                  @click="triggerConfigUpload"
                  style="margin-left: 15px"
              >
                上传配置
                <template #loading>
                  <i class="el-icon-loading"></i>
                </template>
              </el-button>

              <input
                  ref="uploadInput"
                  type="file"
                  hidden
                  @change="handleFileUpload"
              >
            </div>
            <div v-if="isSourceLoading" class="loading-overlay">
              <i class="el-icon-loading"></i>
              <span>正在加载可视化...</span>
            </div>
          </div>
        </div>
      </el-col>
      <el-col :xs="24" :sm="24" :md="4" :lg="4" :xl="4">
        <div class="home-card-item export-container">
          <el-button
              type="primary"
              class="export-button"
              @click="exportTaskLog"
          >
            导出日志
          </el-button>
        </div>
      </el-col>
    </el-row>

    <!-- Time Range Selection Row -->
    <el-row :gutter="15" class="time-range-row mb15">
      <el-col :xs="24" :sm="24" :md="12" :lg="8" :xl="6">
        <div class="home-card-item time-range-container">
          <div class="time-range-label">开始时间：</div>
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
      </el-col>
      <el-col :xs="24" :sm="24" :md="12" :lg="8" :xl="6">
        <div class="home-card-item time-range-container">
          <div class="time-range-label">结束时间：</div>
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
      </el-col>
      <el-col :xs="24" :sm="24" :md="24" :lg="8" :xl="12">
        <div class="home-card-item time-range-actions">
          <el-button
              type="primary"
              :disabled="!timeRange.start || !timeRange.end"
              @click="applyTimeRange"
          >
            应用时间区间
          </el-button>
          <el-button
              @click="resetTimeRange"
          >
            重置为当前时间并应用
          </el-button>
          <el-button
              type="info"
              @click="clearTimeRange"
          >
            清除时间区间
          </el-button>
          <span class="time-range-hint" v-if="!isTimeRangeApplied">
            （时间区间未应用）
          </span>
          <span class="time-range-hint applied" v-else>
            （已应用：{{ formatTimeRangeDisplay() }}）
          </span>
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
              <el-empty description="请先选择并应用时间区间以显示数据" />
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
      // 首先获取最新任务数据
      await this.getLatestResultData();
      
      // 获取当前选中数据源的任务
      const tasks = this.bufferedTaskCache[this.selectedDataSource] || [];
      
      // 找到最后一个任务的开始时间
      let lastTaskStartTime = null;
      if (tasks.length > 0) {
        // 按任务开始时间排序（从新到旧）
        const sortedTasks = [...tasks].sort((a, b) => {
          return parseInt(b.task_start_time) - parseInt(a.task_start_time);
        });
        lastTaskStartTime = sortedTasks[0].task_start_time;
      }
      
      // 如果没有任务数据或任务时间无效，使用当前时间
      const now = new Date();
      let endTime, startTime;
      
      if (lastTaskStartTime && !isNaN(parseInt(lastTaskStartTime))) {
        endTime = new Date(parseInt(lastTaskStartTime) * 1000);
      } else {
        endTime = now;
      }
      
      // 开始时间为结束时间前5秒
      startTime = new Date(endTime.getTime() - 5 * 1000);
      
      this.timeRange.start = Math.floor(startTime.getTime() / 1000); // 转换为秒级时间戳
      this.timeRange.end = Math.floor(endTime.getTime() / 1000);
      
      // 重置后自动应用时间区间
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
    
    triggerConfigUpload() {
      if (!this.selectedDataSource) return
      this.$refs.uploadInput.value = null
      this.$refs.uploadInput.click()
    },

    async handleFileUpload(event) {
      const file = event.target.files[0]
      if (!file) return

      try {
        const formData = new FormData()
        formData.append('file', file)

        this.$refs.uploadButton.loading = true

        fetch(`/api/result_visualization_config/${this.selectedDataSource}`, {
          method: 'POST',
          body: formData
        })
            .then(response => response.json())
            .then(data => {
              const state = data['state']
              const msg = data['msg']
              this.fetchVisualizationConfig(this.selectedDataSource)
              this.showMsg(state, msg);
            })
      } catch (error) {
        ElMessage.error("System Error")
        console.log(error);
      } finally {
        this.$refs.uploadButton.loading = false
      }
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
        const response = await fetch(`/api/result_visualization_config/${sourceId}`)
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
        const response = await fetch('/api/freetask_result')
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

          // 🔄 直接替换，不再拼接 slice
          newCache[sourceId] = validTasks

          // 检查可视化配置是否需要更新
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

        if (Object.keys(configUpdates).length > 0) {
          this.handleConfigUpdates(configUpdates)
        }
      } catch (error) {
        console.error('Error fetching task results:', error)
      }
    },


    setupDataPolling() {
      // 仅在初始化时获取一次数据，不设置定时器
      this.getLatestResultData()
      // 移除自动轮询
      // this.pollingInterval = setInterval(() => {
      //   this.getLatestResultData()
      // }, 2000)
    },

    exportTaskLog() {
      fetch('/api/download_log')
          .then(response => response.blob())
          .then(blob => {
            const url = window.URL.createObjectURL(blob)
            const link = document.createElement('a')
            link.href = url
            link.setAttribute('download', 'task_log.json')
            document.body.appendChild(link)
            link.click()
            link.remove()
          })
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

.export-container {
  height: auto;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 8px;
}

.compact-select {
  width: 70%;
}

.compact-select ::v-deep .el-input__inner {
  height: 32px;
  line-height: 32px;
}

.export-button {
  width: 100%;
  padding: 8px 12px;
}

/* 时间区间选择器样式 */
.time-range-row {
  margin-top: 15px;
}

.time-range-container {
  padding: 12px;
  display: flex;
  align-items: center;
}

.time-range-label {
  font-weight: bold;
  margin-right: 10px;
  min-width: 70px;
}

.time-range-actions {
  padding: 12px;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
}

.time-range-hint {
  margin-left: 10px;
  color: #f56c6c;
  font-size: 12px;
}

.time-range-hint.applied {
  color: #67c23a;
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
  color: var(--el-color-primary);
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