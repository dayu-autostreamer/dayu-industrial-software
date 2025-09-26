<template>
  <div class="priority-view">
    <div v-if="service && service.length > 0">
      <div v-for="(serviceQueue, serviceName) in service" :key="serviceName" class="service-block">
        <h3>{{ serviceName }} - 优先级队列</h3>

        <div v-for="(queue, index) in priority_num" :key="index" class="priority-queue">
          <h4>优先级队列 {{ index + 1 }}</h4>
          <div class="queue-items">
            <div v-for="(task, taskIndex) in queue" :key="taskIndex" class="task-item">
              <div class="task-header">
                <span>任务ID: {{ task.task_id }}</span>
                <span class="importance" :style="getImportanceStyle(task.importance)">
                  重要性: {{ task.importance }}
                </span>
                <span class="urgency" :style="getUrgencyStyle(task.urgency)">
                  紧急度: {{ task.urgency }}
                </span>
              </div>
              <div class="task-details">
                <p>来源ID: {{ task.source_id }}</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
    <div v-else>
      <p>没有可显示的服务数据。</p>
    </div>
  </div>
</template>

<script>
export default {
  props: {
    priority_num: {
      type: Number,
      required: true
    },
    service: {
      type: Array,
      required: true
    },
    queue_result: {
      type: Object,
      required: true
    }
  },
  methods: {
    // 获取任务重要性样式
    getImportanceStyle(importance) {
      if (importance === 1) return { color: 'red' }; // 高重要性
      if (importance === 2) return { color: 'orange' }; // 中等重要性
      return { color: 'green' }; // 低重要性
    },
    // 获取任务紧急度样式
    getUrgencyStyle(urgency) {
      if (urgency === 1) return { backgroundColor: 'red' }; // 高紧急度
      if (urgency === 2) return { backgroundColor: 'orange' }; // 中等紧急度
      return { backgroundColor: 'green' }; // 低紧急度
    }
  }
}
</script>

<style scoped lang="scss">
.priority-view {
  display: flex;
  flex-direction: column;
  gap: 30px;
  padding: 20px;

  .service-block {
    border: 1px solid #ccc;
    padding: 15px;
    border-radius: 8px;
    background-color: #f9f9f9;
    box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);

    h3 {
      margin-bottom: 15px;
      font-size: 20px;
      font-weight: bold;
    }

    .priority-queue {
      margin-bottom: 20px;

      h4 {
        font-size: 18px;
        margin-bottom: 10px;
        color: #333;
      }

      .queue-items {
        display: flex;
        flex-direction: column;
        gap: 10px;

        .task-item {
          background-color: #fff;
          padding: 10px;
          border-radius: 5px;
          box-shadow: 0 1px 5px rgba(0, 0, 0, 0.1);
          transition: all 0.3s ease;

          &:hover {
            background-color: #f5f5f5;
          }

          .task-header {
            display: flex;
            justify-content: space-between;
            margin-bottom: 10px;

            .importance,
            .urgency {
              font-weight: bold;
            }
          }

          .task-details {
            font-size: 14px;
            color: #666;
          }
        }
      }
    }
  }
}
</style>
