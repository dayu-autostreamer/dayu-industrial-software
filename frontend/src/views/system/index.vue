<template>
  <div class="home-container layout-pd">
    <!-- Visualization Controls Row -->
    <el-row class="viz-controls-row mb15">
      <el-col :span="24">
        <div class="viz-controls-panel">
          <div class="control-group">
            <h4>Active Visualizations:</h4>
            <el-checkbox-group v-model="currentActiveVisualizationsArray">
              <el-checkbox
                  v-for="viz in visualizationConfig"
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
      <template v-if="componentsLoaded">
        <el-col
            v-for="viz in visualizationConfig"
            :key="getVizKey(viz)"
            :xs="24"
            :sm="24"
            :md="getVisualizationSpan(viz.size, 'md')"
            :lg="getVisualizationSpan(viz.size, 'lg')"
            :xl="getVisualizationSpan(viz.size, 'xl')"
            v-show="currentActiveVisualizations.has(viz.id)"
        >
          <div class="home-card-item viz-module">
            <div class="viz-module-header">
              <h3 class="viz-title">{{ viz.name }}</h3>
              <component
                  :is="vizControls[viz.type]"
                  :key="viz.type + '-' + viz.variablesHash"
                  :config="viz"
                  :variable-states="variableStates[viz.id] || {}"
                  @update:variable-states="updateVariableStates(viz.id, $event)"
              />
            </div>

            <component
                :is="visualizationComponents[viz.type]"
                v-if="visualizationComponents[viz.type]"
                :key="`${viz.type}-${viz.id}-${viz.variablesHash}`"
                :config="viz"
                :data="processedData[viz.id]"
                :variable-states="variableStates[viz.id] || {}"
            />
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
import {markRaw, reactive, toRaw} from 'vue'
import mitt from 'mitt'

const emitter = mitt()

export default {
  data() {
    return {
      bufferedTaskCache: reactive([]),
      maxBufferedTaskCacheSize: 20,
      componentsLoaded: false,
      visualizationConfig: [],
      activeVisualizations: new Set(),
      variableStates: {},
      visualizationComponents: {},
      vizControls: {},
      pollingInterval: null,
    }
  },
  computed: {
    processedData() {
      const result = {}
      this.visualizationConfig.forEach(viz => {
        result[viz.id] = this.processVizData(viz)
      })
      return result
    },
    currentActiveVisualizations() {
      return this.activeVisualizations || new Set()
    },
    currentActiveVisualizationsArray: {
      get() {
        return Array.from(this.activeVisualizations)
      },
      set(newVal) {
        this.activeVisualizations = new Set(newVal)
      }
    },
  },

  async created() {
    await this.autoRegisterComponents()
    this.componentsLoaded = true
    await this.fetchVisualizationConfig()
    this.setupDataPolling()

    emitter.on('force-update-charts', () => {
      this.$nextTick(() => {
        this.visualizationConfig.forEach(viz => {
          this.variableStates[viz.id] =
              {...this.variableStates[viz.id]}
        })
      })
    })
  },

  methods: {
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
            const comp = await loader()
            this.visualizationComponents[type] = markRaw(comp.default)
          }),
          ...Object.entries(controls).map(async ([path, loader]) => {
            const type = path.split('/').pop().replace('Controls.vue', '').toLowerCase()
            const comp = await loader()
            this.vizControls[type] = markRaw(comp.default)
          })
        ])
      } catch (error) {
        console.error('Component registration failed:', error)
      }
    },

    processVizData(vizConfig) {
      if (!this.bufferedTaskCache.length) return []

      try {
        return this.bufferedTaskCache
            .filter(task => {
              return task.data?.some(item =>
                  String(item.id) === String(vizConfig.id))
            })
            .map(task => {
              const vizDataItem = task.data.find(
                  item => String(item.id) === String(vizConfig.id))
              return {
                timestamp: task.timestamp,
                ...(vizDataItem?.data || {})
              }
            })
      } catch (error) {
        console.error('Data process error:', error)
      }

    },

    updateVariableStates(vizId, newStates) {
      const validVars = this.visualizationConfig.find(v => v.id === vizId)?.variables || [];
      this.variableStates[vizId] = validVars.reduce((acc, varName) => {
        acc[varName] = newStates[varName] ?? true;
        return acc;
      }, {});

      emitter.emit('force-update-charts')
    },

    async fetchVisualizationConfig() {
      try {
        const response = await fetch('/api/system_visualization_config')
        const data = await response.json()

        this.visualizationConfig = data.map(viz => reactive({
          ...viz,
          id: String(viz.id),
          size: Math.min(3, Math.max(1, parseInt(viz.size) || 1)),
          variables: [...(viz.variables || [])],
          variablesHash: this.calculateVariablesHash(viz.variables)
        }));

        this.activeVisualizations = new Set(this.visualizationConfig.map(viz => viz.id))

        this.variableStates = this.visualizationConfig.reduce((acc, viz) => {
          acc[viz.id] = viz.variables.reduce((vars, varName) => {
            vars[varName] = true
            return vars
          }, {})
          return acc
        }, {})
      } catch (error) {
        console.error('Failed to fetch visualization config:', error)
      }
    },

    async getLatestSystemData() {
      try {
        const response = await fetch('/api/system_parameters')
        const data = await response.json()

        const now = new Date();
        const hours = String(now.getHours()).padStart(2, '0');
        const minutes = String(now.getMinutes()).padStart(2, '0');
        const seconds = String(now.getSeconds()).padStart(2, '0');

        const newTasks = data.flatMap(task => ({
          ...task,
          timestamp: `${hours}:${minutes}:${seconds}`,
          data: task.data.map(item => ({
            id: String(item.id),
            data: item.data
          }))
        }))

        newTasks.forEach(task => {
          task.data.forEach(item => {
            const vizId = item.id;
            const newVariables = Object.keys(item.data);

            if (newVariables && Array.isArray(newVariables)) {
              const vizIndex = this.visualizationConfig.findIndex(v => v.id === vizId);
              if (vizIndex !== -1) {
                const currentViz = this.visualizationConfig[vizIndex];

                // 比较variables差异
                if (!this.arraysEqual(currentViz.variables, newVariables)) {
                  // 更新可视化配置
                  const updatedViz = {
                    ...currentViz,
                    variables: [...newVariables],
                    variablesHash: this.calculateVariablesHash(newVariables)
                  };
                  this.visualizationConfig.splice(vizIndex, 1, updatedViz);

                  // 同步更新变量状态
                  const currentState = this.variableStates[vizId] || {};
                  this.variableStates[vizId] = newVariables.reduce((acc, varName) => {
                    acc[varName] = varName in currentState ? currentState[varName] : true;
                    return acc;
                  }, {});
                }
              }
            }
          });
        });

        this.bufferedTaskCache = reactive([
          ...this.bufferedTaskCache,
          ...newTasks
        ].slice(-this.maxBufferedTaskCacheSize))

        this.$nextTick(() => {
          emitter.emit('force-update-charts')
        })
      } catch (error) {
        console.error('Data fetch failed:', error)
      }
    },

    setupDataPolling() {
      this.getLatestSystemData()
      this.pollingInterval = setInterval(() => {
        this.getLatestSystemData()
      }, 2000)
    },
  },

  beforeUnmount() {
    clearInterval(this.pollingInterval)
    emitter.off('force-update-charts')
  }
}
</script>

<style scoped>
.home-container {
  overflow: hidden;
  padding: 16px;
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

.skeleton-loading {
  padding: 20px;
}

.skeleton-item {
  height: 200px;
  background: #f5f7fa;
  border-radius: 4px;
  margin-bottom: 15px;
  position: relative;
  overflow: hidden;
}

.skeleton-item::after {
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

@keyframes skeleton-flash {
  100% {
    left: 100%;
  }
}
</style>