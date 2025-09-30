<template>
  <div class="chart-container">
    <div ref="container" class="chart-wrapper"></div>
    <div v-if="showEmptyState" class="empty-state">
      <el-icon :size="40">
        <PieChart/>
      </el-icon>
      <p>{{ emptyMessage }}</p>
    </div>
  </div>
</template>

<script>
import {ref, computed, onMounted, onBeforeUnmount, watch, nextTick} from 'vue'
import * as echarts from 'echarts'
import {PieChart} from '@element-plus/icons-vue'

export default {
  name: 'CurveTemplate',
  components: {PieChart},
  props: {
    config: {
      type: Object,
      required: true,
      default: () => ({
        id: '',
        name: '',
        type: 'curve',
        variables: [],
        x_axis: 'Task Index',
        y_axis: ''
      })
    },
    data: {
      type: Array,
      required: true,
      validator: value => {
        return Array.isArray(value) && value.every(item =>
            item.taskId !== undefined
        )
      }
    },
    variableStates: {
      type: Object,
      required: true,
      default: () => ({})
    }
  },

  setup(props) {

    // Refs
    const chart = ref(null)
    const container = ref(null)
    const resizeObserver = ref(null)
    const isMounted = ref(true)
    const forceUpdate = ref(0)

    let renderRetryCount = 0

    const animationConfig = {
      duration: 800,
      easing: 'quarticInOut'
    }

    const cleanChart = () => {
      if (chart.value) {
        chart.value.dispose()
        chart.value = null
      }
    }

    // Utility: measure text width to dynamically allocate grid.left for long y-axis name
    const estimateTextWidth = (text = '', font = '12px sans-serif') => {
      try {
        const canvas = document.createElement('canvas')
        const ctx = canvas.getContext('2d')
        if (!ctx) return 0
        ctx.font = font
        return ctx.measureText(String(text)).width
      } catch (e) {
        return 0
      }
    }

    const computeGridLeft = () => {
      // Base percentage fallback
      if (!container.value) return '8%'
      const width = container.value.clientWidth || 0
      if (!width) return '8%'

      const name = props.config?.y_axis || ''
      // Keep in sync with nameTextStyle below
      const fontSize = 12
      const nameWidth = estimateTextWidth(name, `${fontSize}px sans-serif`)

      // Heuristics: allow tick labels + padding
      const tickLabelReserve = 56 // px
      const padding = 16 // px

      // Desired left in px, clamped to at most 40% of container width
      const desired = Math.min(
          Math.max(width * 0.08, nameWidth + tickLabelReserve + padding),
          width * 0.4
      )

      return `${Math.round(desired)}px`
    }

    // Computed Properties
    const safeData = computed(() => {
      return (props.data || []).map(item => {
        const cleanItem = {taskId: item.taskId}

        props.config.variables?.forEach(varName => {
          const rawValue = item[varName]
          // 转换无效值为0
          cleanItem[varName] = rawValue !== null && rawValue !== undefined ?
              rawValue : 0
        })

        return cleanItem
      })
    })

    const activeVariables = computed(() => {
      return props.config.variables?.filter(varName =>
          props.variableStates[varName] !== false
      ) || []
    })


    const showEmptyState = computed(() => {
      const hasData = safeData.value.length > 0
      const hasValidData = hasData && activeVariables.value.some(v =>
          safeData.value.some(d => d[v] !== undefined)
      )

      return !hasValidData
    })

    const emptyMessage = computed(() => {
      if (!safeData.value.length) return 'No data available'
      if (!activeVariables.value.length) return 'No active variables selected'
      return ''
    })

    // Methods
    const initChart = async () => {
      try {
        // 三重等待确保 DOM 就绪
        await nextTick()
        if (!container.value) return false

        const isVisible = () => {
          const rect = container.value.getBoundingClientRect()
          return !(rect.width === 0 || rect.height === 0)
        }
        let checks = 0
        while (checks < 10) {
          if (isVisible()) break
          await new Promise(r => setTimeout(r, 50))
          checks++
        }

        if (!isVisible()) {
          console.warn('Container remains invisible after retries')
          return false
        }

        // 检查容器可见性
        const style = window.getComputedStyle(container.value)
        if (style.display === 'none' || style.visibility === 'hidden') {
          console.warn('Chart container is hidden')
          return false
        }

        // 清理旧实例
        if (chart.value) {
          chart.value.dispose()
          chart.value = null
        }

        chart.value = echarts.init(container.value, null, {
          renderer: 'canvas',
          useDirtyRect: true
        })

        // 标记容器状态
        container.value.dataset.chartReady = 'true'
        return true
      } catch (e) {
        console.error('Chart init failed:', e)
        return false
      }
    }


    const renderChart = async () => {
      try {

        if (!chart.value) {
          const success = await initChart()
          if (!success) return
        }
        chart.value.setOption(getChartOption(), true)

        // 添加视觉连续性
        chart.value.dispatchAction({
          type: 'downplay',
          seriesIndex: 'all'
        })
        chart.value.dispatchAction({
          type: 'highlight',
          seriesIndex: 0
        })

        renderRetryCount = 0 // 重置计数器
      } catch (e) {
        console.error('Render failed:', e)
      }
    }

    const observer = new MutationObserver(() => {
      forceUpdate.value++
    })


    const valueTypes = computed(() => {
      const types = {}
      activeVariables.value.forEach(varName => {
        const sampleValue = safeData.value[0]?.[varName]
        types[varName] = typeof sampleValue === 'number' ? 'value' : 'category';
      })
      return types
    })

    const discreteValueMap = ref({})
    const getDiscreteValue = (varName, value) => {
      if (!discreteValueMap.value[varName]) {
        discreteValueMap.value[varName] = {}
      }
      const map = discreteValueMap.value[varName]
      if (!(value in map)) {
        map[value] = Object.keys(map).length
      }
      return map[value]
    }
    const getOriginalDiscreteLabel = (varName, code) => {
      const map = discreteValueMap.value[varName] || {}
      const entry = Object.entries(map).find(([, v]) => v === code)
      return entry ? entry[0] : code
    }

    const getChartOption = () => {
      if (activeVariables.value.length === 0 || safeData.value.length === 0) {
        return {}
      }

      const yAxisConfig = {
        type: valueTypes.value[activeVariables.value[0]],
        name: props.config.y_axis,
        nameLocation: 'end',
        nameGap: 20,
        alignTicks: true,
        // Ensure long name doesn't overflow by allowing wrap within reserved grid.left
        nameTextStyle: {
          fontSize: 12,
          overflow: 'breakAll'
        },
        axisLabel: {
          formatter: value => {
            if (valueTypes.value[activeVariables.value[0]] === 'category') {
              const entry = Object.entries(discreteValueMap.value[activeVariables.value[0]])
                  .find(([, v]) => v === value)
              return entry ? entry[0] : value
            }
            return Number(value).toFixed(2)
          }
        }
      }

      const seriesConfig = activeVariables.value.map(varName => {
        const values = safeData.value.map(d => d[varName])

        return {
          name: varName,
          type: 'line',
          yAxisIndex: 0,
          data: values.map(v => {
            if (v === undefined) return null
            return valueTypes.value[varName] === 'category'
                ? getDiscreteValue(varName, v)
                : Number(v)
          }),
          // 新增：空数据跳过渲染
          connectNulls: false,
          // 新增：优化渲染性能
          progressive: 200,
          animation: values.length < 100
        }
      })


      return {
        // 新增动画配置
        animation: true,
        animationDuration: animationConfig.duration,
        animationEasing: animationConfig.easing,
        tooltip: {
          trigger: 'item',
          formatter: params => {
            if (!params) return ''
            const name = params.name
            const seriesName = params.seriesName
            const varType = valueTypes.value[seriesName]
            const yValue = varType === 'category'
                ? getOriginalDiscreteLabel(seriesName, params.value)
                : Number(params.value).toFixed(2)
            return `${name}<br/>${params.marker} ${seriesName}: ${yValue}`
          }
        },
        legend: {
          data: activeVariables.value,
          type: 'scroll'
        },
        grid: {
          left: computeGridLeft(),
          right: '4%',
          bottom: '15%',
          containLabel: true
        },
        xAxis: {
          type: 'category',
          name: props.config.x_axis,
          nameLocation: 'center',
          nameGap: 25,
          data: safeData.value.map(d => d.taskId),
          axisLabel: {
            formatter: value => value.length > 8 ? `${value.slice(0, 8)}...` : value
          },
          axisPointer: {
            type: 'shadow'
          },
          axisLine: {show: true},
          axisTick: {show: true}
        },
        yAxis: yAxisConfig,
        series: seriesConfig
      }
    }

    // Lifecycle Hooks
    onMounted(() => {
      if (!showEmptyState.value) {
        renderChart()
      }
      if (container.value) {
        observer.observe(container.value, {
          attributes: true,
          attributeFilter: ['style', 'class']
        })
        // Observe size changes to recompute grid.left for long y-axis name
        if ('ResizeObserver' in window) {
          resizeObserver.value = new ResizeObserver(() => {
            // debounce via rAF
            requestAnimationFrame(() => {
              if (chart.value && !showEmptyState.value) {
                renderChart()
                chart.value.resize()
              }
            })
          })
          resizeObserver.value.observe(container.value)
        }
      }
      setTimeout(renderChart, 300)
    })

    onBeforeUnmount(() => {
      isMounted.value = false
      if (chart.value) {
        chart.value.dispose()
        chart.value = null
      }
      if (resizeObserver.value) {
        resizeObserver.value.disconnect()
      }
    })

    // Watchers
    watch(showEmptyState, (newVal) => {
      if (newVal) {
        cleanChart()
      } else {
        renderChart()
      }
    })


    watch(() => props.data, () => {
      if (isMounted.value && !showEmptyState.value) {
        renderChart()
      }
    }, {deep: true, flush: 'post'})

    // Re-render when y-axis name or variable visibility changes
    watch(() => props.config.y_axis, () => {
      if (isMounted.value && !showEmptyState.value) {
        renderChart()
      }
    })
    watch(() => props.variableStates, () => {
      if (isMounted.value && !showEmptyState.value) {
        renderChart()
      }
    }, {deep: true})

    return {
      container,
      showEmptyState,
      emptyMessage
    }
  }
}
</script>

<style scoped>
.chart-container {
  position: relative;
  width: 100%;
  height: 100%;
  min-height: 400px;
}

.chart-wrapper {
  width: 100%;
  height: 100%;
  min-height: 300px;
}

.empty-state {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  text-align: center;
  color: var(--el-text-color-secondary);
}

.empty-state p {
  margin-top: 10px;
  font-size: 14px;
}
</style>