import json
import time

from core.lib.content import Task


class PriorityEstimator:
    def __init__(self, importance_weight, urgency_weight, priority_levels, deadline):
        self.priority_level_num = priority_levels
        self.importance_weight = importance_weight
        self.urgency_weight = urgency_weight
        self.deadline = deadline

    def calculate_priority(self, task: Task):
        importance = task.get_source_importance()
        urgency = self.calculate_urgency(task)

        return round(importance * self.importance_weight + urgency * self.urgency_weight)

    def calculate_urgency(self, task: Task):
        service_name = task.get_current_service_info()[0]

        remaining_time = self.get_relative_remaining_time(task.get_total_start_time())
        urgency_threshold_list = self.get_urgency_threshold(service_name)
        self.update_urgency_history(service_name, remaining_time)

        if urgency_threshold_list is None:
            return 0
        else:
            urgency = 0
            for value in urgency_threshold_list:
                if remaining_time >= value:
                    urgency += 1
                else:
                    break
        return urgency

    def get_urgency_threshold(self, service_name):
        urgency_list = self.get_urgency_history(service_name)
        if len(urgency_list) < self.priority_level_num - 1:
            return None
        else:
            # collect last num of each urgency unit as threshold
            urgency_threshold = self.split_list_into_chunks_last(urgency_list, self.priority_level_num - 1)
            return urgency_threshold

    def get_urgency_history(self, service_name):
        try:
            with open(f'{service_name}.json') as f:
                urgency_history = json.load(f)
            return urgency_history
        except FileNotFoundError:
            return []

    def update_urgency_history(self, service_name, urgency):
        urgency_history = self.get_urgency_history(service_name)
        urgency_history.append(urgency)
        with open(f'{service_name}.json', 'w') as f:
            json.dump(urgency_history, f)

    def get_relative_remaining_time(self, start_time):
        return (time.time() - start_time) / self.deadline

    def split_list_into_chunks_last(self, list_input, n):
        chunk_size, remainder = divmod(len(list_input), n)
        chunks_last = []
        start = 0
        for i in range(n):
            end = start + chunk_size + (1 if i < remainder else 0)
            chunks_last.append(list_input[end - 1])
            start = end

        return chunks_last
