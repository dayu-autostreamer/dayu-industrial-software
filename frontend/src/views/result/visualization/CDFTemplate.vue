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
        type: 'cdf',
        variables: [],
        x_axis: '',
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

    const cleanChart = () => {
      if (chart.value) {
        chart.value.dispose()
        chart.value = null
      }
    }

    // Computed Properties
    const safeData = computed(() => {
      const result = {}
      const currentVariableStates = props.variableStates || {}
      if (!props.config.variables?.length) {
        console.warn('No variables defined in config')
        return result
      }

      props.config.variables?.forEach(varName => {
        if (currentVariableStates[varName] !== true) return
        const allValues = props.data
            .map(d => d[varName])
            .filter(v => v !== undefined && v !== null && !isNaN(v))
            .map(Number)
            .sort((a, b) => a - b)
        if (allValues.length === 0) return

        const n = allValues.length
        const uniqueValues = [...new Set(allValues)]
        result[varName] = uniqueValues.map(value => ({
          value,
          probability: allValues.filter(v => v <= value).length / n
        }))
      })

      return result
    })

    const activeVariables = computed(() => {
      return props.config.variables?.filter(varName =>
          props.variableStates[varName] !== false
      ) || []
    })

    const showEmptyState = computed(() => {
      const hasData = Object.values(safeData.value).some(arr => arr?.length > 0)
      return !(hasData && activeVariables.value.length > 0)
    })

    const emptyMessage = computed(() => {
      if (props.data.length === 0) return 'No data available'
      if (activeVariables.value.length === 0) return 'No active variables selected'
      const hasInvalidData = Object.values(safeData.value).every(arr => arr.length === 0)
      return hasInvalidData ? 'No valid numeric data available' : ''
    })

    // Methods
    const initChart = async () => {
      try {
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
        const style = window.getComputedStyle(container.value)
        if (style.display === 'none' || style.visibility === 'hidden') {
          console.warn('Chart container is hidden')
          return false
        }
        if (chart.value) {
          chart.value.dispose()
          chart.value = null
        }
        chart.value = echarts.init(container.value, null, {
          renderer: 'canvas',
          useDirtyRect: true
        })
        chart.value.resize()
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
        const option = getChartOption()
        chart.value.setOption(option, true)
        chart.value.resize()
        const hasSeries = Array.isArray(option.series) && option.series.length > 0
        if (hasSeries) {
          chart.value.dispatchAction({ type: 'downplay', seriesIndex: 'all' })
          chart.value.dispatchAction({ type: 'highlight', seriesIndex: 0 })
        }
      } catch (e) {
        console.error('Render failed:', e)
      }
    }

    // 监听容器尺寸变化
    const setupResizeObserver = () => {
      if (!window.ResizeObserver) return
      if (resizeObserver.value) resizeObserver.value.disconnect()
      resizeObserver.value = new ResizeObserver(() => {
        if (chart.value) {
          chart.value.resize()
        }
      })
      if (container.value) resizeObserver.value.observe(container.value)
    }

    const getChartOption = () => {
      const hasData = Object.values(safeData.value).some(arr => arr?.length > 0)
      if (!hasData || activeVariables.value.length === 0) {
        return { xAxis: { show: false }, yAxis: { show: false }, series: [] }
      }
      const series = []
      Object.entries(safeData.value).forEach(([varName, points]) => {
        series.push({
          name: varName,
          type: 'line',
          data: points.map(p => [p.value, p.probability]),
          smooth: true,
          areaStyle: { opacity: 0.1 }
        })
      })
      return {
        grid: { left: 50, right: 20, top: 30, bottom: 45 },
        tooltip: {
          trigger: 'item',
          formatter: params => `${params.seriesName}<br/>\n            Value: ${params.value[0].toFixed(2)}<br/>\n            Probability: ${(params.value[1] * 100).toFixed(1)}%`
        },
        xAxis: { name: props.config.x_axis, nameLocation: 'center', nameGap: 25, type: 'value', min: 'dataMin', max: 'dataMax' },
        yAxis: { name: props.config.y_axis, type: 'value', min: 0, max: 1, axisLabel: { formatter: value => `${(value * 100).toFixed(0)}%` } },
        series,
        legend: { data: Object.keys(safeData.value) }
      }
    }

    // Lifecycle Hooks
    onMounted(() => {
      setupResizeObserver()
      if (!showEmptyState.value) {
        renderChart()
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

    watch(() => props.variableStates, () => {
      if (isMounted.value && !showEmptyState.value) {
        renderChart()
      }
    }, {deep: true})

    return { container, showEmptyState, emptyMessage }
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
  color: #909399; /* fallback of var(--el-text-color-secondary) */
  z-index: 10;
}

.empty-state p {
  margin-top: 10px;
  font-size: 14px;
}
</style>