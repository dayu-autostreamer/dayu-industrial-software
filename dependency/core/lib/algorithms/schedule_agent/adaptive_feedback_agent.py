import abc
from collections import deque
import math
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
        self.history_latency_buffer: deque = deque(maxlen=20)

        # Internal adaptive state
        self._pipe_seg: int = None  # initialized on first plan based on config or 0
        self._since_last_adjust: int = 0
        self._high_breach_count: int = 0
        self._low_breach_count: int = 0
        # For slower-than-1 additive increase, we accumulate fractional progress
        self._increase_accum: float = 0.0

        self.alpha = 0.3
        self.hysteresis = 0.07
        # Legacy linear step still used as a minimal increment when needed
        self.step = 1
        self.breach_needed = 2
        self.cooldown_steps = 1

        # AIMD parameters (configurable)
        # Multiplicative decrease factor in (0,1]; e.g., 0.5 halves edge segment count on high latency
        self.aimd_decrease_factor: float = 0.5
        # Additive increase rate per eligible low-latency event. Can be <1 for slower-than-1 increases.
        # Example: 0.5 -> +1 every two eligible events on average.
        self.aimd_increase_rate: float = 1.0
        # Optional: initial pipeline edge segment from config
        self.init_pipe_seg = 0

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
        with self.overhead_estimator:
            policy = {}
            policy.update(self.fixed_configuration)

            cloud_device = self.cloud_device
            source_edge_device = info['source_device']

            dag = info['dag']
            # Extract pipeline stages in order
            pipeline = Task.extract_pipeline_deployment_from_dag_deployment(dag)
            pipeline_len = len(pipeline)

            # Configurable parameters with sane defaults
            init_pipe_seg = self.init_pipe_seg
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
                            # Multiplicative Decrease (AIMD): rapidly reduce edge segment count
                            new_seg = int(math.floor(self._pipe_seg * max(0.0, min(1.0, self.aimd_decrease_factor))))
                            # Ensure progress by at least 1 when above min bound
                            if new_seg == self._pipe_seg and self._pipe_seg > min_edge:
                                new_seg = self._pipe_seg - max(1, self.step)
                            self._pipe_seg = max(min_edge, new_seg)
                            adjusted = True
                            # On decrease, optionally reset additive accumulator to avoid immediate growth
                            self._increase_accum = 0.0
                            # Reset breach counter after acting
                            self._high_breach_count = 0
                    elif smoothed_delay < lower and self._pipe_seg < max_edge:
                        self._low_breach_count += 1
                        self._high_breach_count = 0
                        if self._low_breach_count >= self.breach_needed:
                            # Additive Increase (AIMD): slowly increase edge segment count
                            self._increase_accum += max(0.0, self.aimd_increase_rate)
                            inc = int(self._increase_accum)
                            if inc <= 0:
                                # Not enough accumulated to grow this round; keep waiting
                                pass
                            else:
                                new_seg = min(max_edge, self._pipe_seg + inc)
                                # Apply and carry leftover fractional accumulation
                                self._pipe_seg = new_seg
                                self._increase_accum -= inc
                                adjusted = True
                                # Reset breach counter after acting
                                self._low_breach_count = 0
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

            # Build new pipeline deployment according to decided pipe_seg
            ps = max(0, min(self._pipe_seg if self._pipe_seg is not None else 0, pipeline_len))

            new_pipeline = (
                    [{**p, 'execute_device': source_edge_device} for p in pipeline[:ps]] +
                    [{**p, 'execute_device': cloud_device} for p in pipeline[ps:]]
            )

            LOGGER.info(f'[Adaptive Feedback] Adjusting pipeline as "{new_pipeline}"')

            new_pipeline.insert(0, {'service_name': 'start', 'execute_device': source_edge_device})
            new_pipeline.append({'service_name': 'end', 'execute_device': cloud_device})

            # Build dag deployment back
            new_dag = Task.extract_dag_deployment_from_pipeline_deployment(new_pipeline)
            policy.update({'dag': new_dag})

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
