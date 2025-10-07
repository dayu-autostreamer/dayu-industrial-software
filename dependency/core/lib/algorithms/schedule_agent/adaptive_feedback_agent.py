import abc
from collections import deque
from core.lib.common import ClassFactory, ClassType, KubeConfig, Context, ConfigLoader, LOGGER
from core.lib.estimation import OverheadEstimator
from core.lib.content import Task

from .base_agent import BaseAgent

__all__ = ('AdaptiveFeedbackAgent',)


@ClassFactory.register(ClassType.SCH_AGENT, alias='adaptive_feedback')
class AdaptiveFeedbackAgent(BaseAgent, abc.ABC):
    def __init__(self, system, agent_id: int, latency_constraint, configuration=None):
        super().__init__()

        self.agent_id = agent_id
        self.cloud_device = system.cloud_device

        self.latency_constraint = latency_constraint

        # Bounded history buffer for recent end-to-end delays (seconds)
        self.history_latency_buffer: deque = deque(maxlen=10)

        # Internal adaptive state
        self._pipe_seg: int = None  # initialized on first plan based on config or 0
        self._since_last_adjust: int = 0
        self._high_breach_count: int = 0
        self._low_breach_count: int = 0

        self.alpha = 0.3
        self.hysteresis = 0.07
        self.step = 1
        self.breach_needed = 2
        self.cooldown_steps = 1

        if configuration is None:
            self.fixed_configuration = {}
        elif isinstance(configuration, dict):
            self.fixed_configuration = configuration
        elif isinstance(configuration, str):
            self.fixed_configuration = ConfigLoader.load(Context.get_file_path(configuration))
        else:
            raise TypeError(f'Input "configuration" must be of type str or dict, get type {type(configuration)}')

        self.overhead_estimator = OverheadEstimator('Adaptive_Feedback',
                                                    'scheduler/adaptive_feedback')

    def get_schedule_plan(self, info):
        LOGGER.debug('[SCHEDULE DEBUG] AdaptiveFeedbackAgent get_schedule_plan called.')
        with self.overhead_estimator:
            LOGGER.debug('[SCHEDULE DEBUG] AdaptiveFeedbackAgent overhead estimation start.')
            policy = {}
            policy.update(self.fixed_configuration)

            cloud_device = self.cloud_device
            source_edge_device = info['source_device']
            all_edge_devices = info['all_edge_devices']
            all_devices = [*all_edge_devices, cloud_device]
            service_info = KubeConfig.get_service_nodes_dict()

            LOGGER.debug('[SCHEDULE DEBUG] set basic info done.')

            dag = info['dag']
            # Extract pipeline stages in order
            pipeline = Task.extract_pipeline_deployment_from_dag_deployment(dag)

            LOGGER.debug('[SCHEDULE DEBUG] extract pipeline done.')
            LOGGER.debug(f'[SCHEDULE DEBUG] pipeline: {pipeline}')
            pipeline_len = len(pipeline)

            # Configurable parameters with sane defaults
            init_pipe_seg = 0
            min_edge = 0
            max_edge = pipeline_len

            # Initialize pipe_seg once we know pipeline length
            if self._pipe_seg is None:
                self._pipe_seg = max(min_edge, min(max_edge, init_pipe_seg))

            # Compute smoothed recent delay
            smoothed_delay = None
            if self.history_latency_buffer:
                # EWMA over the buffer (older -> newer)
                val = None
                for d in self.history_latency_buffer:
                    val = d if val is None else self.alpha * d + (1 - self.alpha) * val
                smoothed_delay = val

            upper = self.latency_constraint * (1 + self.hysteresis)
            lower = self.latency_constraint * (1 - self.hysteresis)

            adjusted = False
            if smoothed_delay is not None and pipeline_len > 0:
                # Cooldown gate
                if self._since_last_adjust >= self.cooldown_steps:
                    if smoothed_delay > upper and self._pipe_seg > min_edge:
                        self._high_breach_count += 1
                        self._low_breach_count = 0
                        if self._high_breach_count >= self.breach_needed:
                            self._pipe_seg = max(min_edge, self._pipe_seg - self.step)
                            adjusted = True
                    elif smoothed_delay < lower and self._pipe_seg < max_edge:
                        self._low_breach_count += 1
                        self._high_breach_count = 0
                        if self._low_breach_count >= self.breach_needed:
                            self._pipe_seg = min(max_edge, self._pipe_seg + self.step)
                            adjusted = True
                    else:
                        # within deadband or at bounds
                        self._high_breach_count = 0
                        self._low_breach_count = 0
                # else still cooling down: skip adjustment but reset breach counters to avoid stale triggers
                else:
                    self._high_breach_count = 0
                    self._low_breach_count = 0

            # Update cooldown counter
            if adjusted:
                self._since_last_adjust = 0
            else:
                self._since_last_adjust += 1

            LOGGER.debug(f'[SCHEDULE DEBUG] AdaptiveFeedbackAgent decide pipe_seg={self._pipe_seg}')
            # Build new pipeline deployment according to decided pipe_seg
            ps = max(0, min(self._pipe_seg if self._pipe_seg is not None else 0, pipeline_len))
            new_pipeline = (
                    [{**p, 'execute_device': source_edge_device} for p in pipeline[:ps]] +
                    [{**p, 'execute_device': cloud_device} for p in pipeline[ps:]]
            )

            new_pipeline.insert(0, {'service_name': 'start', 'execute_device': source_edge_device})
            new_pipeline.append({'service_name': 'end', 'execute_device': cloud_device})

            # Build dag deployment back
            new_dag = Task.extract_dag_deployment_from_pipeline_deployment(new_pipeline)

            LOGGER.debug('[SCHEDULE DEBUG] extract new dag done.')
            LOGGER.debug(f'[SCHEDULE DEBUG] new dag: {new_dag}')

            policy.update({'dag': new_dag, 'pipe_seg': ps})

        return policy

    def run(self):
        pass

    def update_scenario(self, scenario):
        # Update bounded delay history. Expect scenario to carry 'delay' (seconds)
        if scenario and 'delay' in scenario and scenario['delay'] is not None:
            try:
                delay = float(scenario['delay'])
                if delay >= 0:
                    self.history_latency_buffer.append(delay)
            except Exception:
                # ignore invalid samples
                pass

    def update_resource(self, device, resource):
        pass

    def update_policy(self, policy):
        pass

    def update_task(self, task):
        pass

    def get_schedule_overhead(self):
        return self.overhead_estimator.get_latest_overhead()
