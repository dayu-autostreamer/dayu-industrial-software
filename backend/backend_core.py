import copy
import re
from func_timeout import func_set_timeout as timeout
import func_timeout.exceptions as timeout_exceptions

import os
import time
from core.lib.content import Task
from core.lib.common import LOGGER, Context, YamlOps, FileOps, Counter, SystemConstant, KubeConfig, Queue
from core.lib.common import ConfigBoundInstanceCache
from core.lib.network import http_request, NodeInfo, PortInfo, merge_address, NetworkAPIPath, NetworkAPIMethod

from kube_helper import KubeHelper
from template_helper import TemplateHelper


class BackendCore:
    def __init__(self):

        self.template_helper = TemplateHelper(Context.get_file_path(0))

        self.namespace = ''
        self.image_meta = None
        self.schedulers = None
        self.services = None
        self.priority = None
        self.result_visualization_configs = None
        self.system_visualization_configs = None
        self.customized_source_result_visualization_configs = {}
        self.visualization_cache = ConfigBoundInstanceCache(
            factory=lambda vf: Context.get_algorithm(
                'RESULT_VISUALIZER',
                al_name=vf['hook_name'],
                **(dict(eval(vf['hook_params'])) if 'hook_params' in vf else {}),
                variables=vf['variables']
            )
        )

        self.source_configs = []

        self.dags = []

        self.time_ticket = 0
        self.buffered_result_size = 20

        self.result_url = None
        self.result_file_url = None
        self.resource_url = None
        self.log_fetch_url = None
        self.log_clear_url = None

        self.inner_datasource = self.check_simulation_datasource()
        self.source_open = False
        self.source_label = ''

        self.task_results = {}

        self.freetask_results = {}

        self.task_results_for_priority = Queue()

        self.task_results_for_priority = Queue(self.buffered_result_size)

        self.priority_task_buffer = []


        self.is_get_result = False

        self.cur_yaml_docs = None
        self.save_yaml_path = 'resources.yaml'
        self.log_file_path = 'log.json'

        self.default_visualization_image = 'default_visualization.png'

        self.parse_base_info()

    def parse_base_info(self):
        try:
            base_info = self.template_helper.load_base_info()
            self.namespace = base_info['namespace']
            self.image_meta = base_info['default-image-meta']
            self.schedulers = base_info['scheduler-policies']
            self.services = base_info['services']
            self.priority = base_info['priority']
            self.result_visualization_configs = base_info['result-visualizations']
            self.system_visualization_configs = base_info['system-visualizations']
        except KeyError as e:
            LOGGER.warning(f'Parse base info failed: {str(e)}')
            LOGGER.exception(e)

    def get_log_file_name(self):
        base_info = self.template_helper.load_base_info()
        load_file_name = base_info['log-file-name']
        if not load_file_name:
            return None
        return load_file_name.split('.')[0]

    def parse_and_apply_templates(self, policy, source_deploy):
        yaml_dict = {}

        yaml_dict.update(self.template_helper.load_policy_apply_yaml(policy))

        service_dict, source_deploy = self.extract_service_from_source_deployment(source_deploy)
        yaml_dict.update({'processor': self.template_helper.load_application_apply_yaml(service_dict)})

        first_stage_components = ['scheduler', 'distributor', 'monitor', 'controller']
        second_stage_components = ['generator', 'processor']

        LOGGER.info(f'[First Deployment Stage] deploy components:{first_stage_components}')
        first_docs_list = self.template_helper.finetune_yaml_parameters(yaml_dict, source_deploy,
                                                                        priority=self.priority,
                                                                        scopes=first_stage_components)
        try:
            result, msg = self.install_yaml_templates(first_docs_list)
        except timeout_exceptions.FunctionTimedOut as e:
            LOGGER.warning(f'Parse and apply templates failed: {str(e)}')
            LOGGER.exception(e)
            result = False
            msg = '第一阶段下装超过预定时间（60秒）'
        except Exception as e:
            LOGGER.warning(f'Parse and apply templates failed: {str(e)}')
            LOGGER.exception(e)
            result = False
            msg = '未知系统错误，请查看后端容器日志'
        finally:
            self.save_component_yaml(first_docs_list)
        if not result:
            return False, msg

        LOGGER.info(f'[Second Deployment Stage] deploy components:{second_stage_components}')
        second_docs_list = self.template_helper.finetune_yaml_parameters(yaml_dict, source_deploy,
                                                                         priority=self.priority,
                                                                         scopes=second_stage_components)
        try:
            result, msg = self.install_yaml_templates(second_docs_list)
        except timeout_exceptions.FunctionTimedOut as e:
            LOGGER.warning(f'Parse and apply templates failed: {str(e)}')
            LOGGER.exception(e)
            result = False
            msg = '第二阶段下装超过预定时间（60秒）'
        except Exception as e:
            LOGGER.warning(f'Parse and apply templates failed: {str(e)}')
            LOGGER.exception(e)
            result = False
            msg = '未知系统错误，请查看后端容器日志'
        finally:
            self.save_component_yaml(first_docs_list + second_docs_list)
        if not result:
            return False, msg

        return True, 'Install services successfully'

    def parse_and_delete_templates(self):
        docs = self.get_yaml_docs()
        try:
            result, msg = self.uninstall_yaml_templates(docs)
        except timeout_exceptions.FunctionTimedOut as e:
            LOGGER.warning(f'Uninstall services failed: {str(e)}')
            LOGGER.exception(e)
            msg = '超出预定时间（120秒）'
            result = False
        except Exception as e:
            LOGGER.warning(f'Uninstall services failed: {str(e)}')
            LOGGER.exception(e)
            result = False
            msg = f'未知系统错误，请查看后端容器日志'

        return result, msg

    @timeout(120)
    def uninstall_yaml_templates(self, yaml_docs):
        res = KubeHelper.delete_custom_resources(yaml_docs)
        while KubeHelper.check_component_pods_exist(self.namespace):
            time.sleep(1)
        return res, '' if res else 'kubernetes api error'

    @timeout(60)
    def install_yaml_templates(self, yaml_docs):
        if not yaml_docs:
            return False, 'components yaml data is empty'
        _result = KubeHelper.apply_custom_resources(yaml_docs)
        while not KubeHelper.check_pods_running(self.namespace):
            time.sleep(1)
        return _result, '' if _result else 'kubernetes api error'

    def save_component_yaml(self, docs_list):
        self.cur_yaml_docs = docs_list
        YamlOps.write_all_yaml(docs_list, self.save_yaml_path)

    def extract_service_from_source_deployment(self, source_deploy):
        service_dict = {}

        for s in source_deploy:
            dag = s['dag']
            node_set = s['node_set']
            extracted_dag = copy.deepcopy(dag)
            del extracted_dag['_start']

            def get_service_callback(node_item):
                service_id = node_item['id']
                service = self.find_service_by_id(service_id)
                service_name = service['service']
                service_yaml = service['yaml']
                if service_id in service_dict:
                    pre_node_list = service_dict[service_id]['node']
                    service_dict[service_id]['node'] = list(set(pre_node_list + node_set))
                else:
                    service_dict[service_id] = {'service_name': service_name, 'yaml': service_yaml, 'node': node_set}

                extracted_dag[node_item['id']]['service'] = service

            self.bfs_dag(dag, get_service_callback)
            s['dag'] = extracted_dag

        return service_dict, source_deploy

    def get_yaml_docs(self):
        if self.cur_yaml_docs:
            return self.cur_yaml_docs
        elif os.path.exists(self.save_yaml_path):
            return YamlOps.read_all_yaml(self.save_yaml_path)
        else:
            return None

    def clear_yaml_docs(self):
        self.cur_yaml_docs = None
        FileOps.remove_file(self.save_yaml_path)

    def find_service_by_id(self, service_id):
        for service in self.services:
            if service['id'] == service_id:
                return service
        return None

    def find_dag_by_id(self, dag_id):
        for dag in self.dags:
            if dag['dag_id'] == dag_id:
                return dag['dag']
        return None

    def find_scheduler_policy_by_id(self, policy_id):
        for policy in self.schedulers:
            if policy['id'] == policy_id:
                return policy
        return None

    def find_datasource_configuration_by_label(self, source_label):
        for source_config in self.source_configs:
            if source_config['source_label'] == source_label:
                return source_config
        return None

    def fill_datasource_config(self, config):
        config['source_label'] = f'source_config_{Counter.get_count("source_label")}'
        source_list = config['source_list']
        for index, source in enumerate(source_list):
            source['id'] = index
            source['url'] = self.fill_datasource_url(source['url'], config['source_type'], config['source_mode'], index)

        config['source_list'] = source_list
        return config

    def fill_datasource_url(self, url, source_type, source_mode, source_id):
        if not self.inner_datasource:
            return url
        source_hostname = KubeHelper.get_pod_node(SystemConstant.DATASOURCE.value, self.namespace)
        if not source_hostname:
            assert None, 'Datasource pod not exists.'
        source_protocol = source_mode.split('_')[0]
        source_ip = NodeInfo.hostname2ip(source_hostname)
        source_port = PortInfo.get_component_port(SystemConstant.DATASOURCE.value)
        url = f'{source_protocol}://{source_ip}:{source_port}/{source_type}{source_id}'

        return url

    @staticmethod
    def bfs_dag(dag_graph, dag_callback):
        from collections import deque

        source_list = dag_graph['_start']
        queue = deque(source_list)
        visited = set(source_list)
        while queue:
            current_node_item = dag_graph[queue.popleft()]
            dag_callback(current_node_item)
            for child_id in current_node_item['succ']:
                if child_id not in visited:
                    queue.append(child_id)
                    visited.add(child_id)

    @staticmethod
    def check_node_exist(node):
        return node in NodeInfo.get_node_info()

    @staticmethod
    def get_edge_nodes():
        def sort_key(item):
            name = item['name']
            patterns = [
                (r'^edge(\d+)$', 0),
                (r'^edgexn(\d+)$', 1),
                (r'^edgex(\d+)$', 2),
                (r'^edgen(\d+)$', 3),
            ]
            for pattern, group in patterns:
                match = re.match(pattern, name)
                if match:
                    num = int(match.group(1))
                    return group, num
            return len(patterns), 0

        node_role = NodeInfo.get_node_info_role()
        edge_nodes = [{'name': node_name} for node_name in node_role if node_role[node_name] == 'edge']
        edge_nodes.sort(key=sort_key)
        return edge_nodes

    def check_simulation_datasource(self):
        return KubeHelper.check_pod_name('datasource', namespace=self.namespace)

    def check_dag(self, dag):

        def topo_sort(graph):
            in_degree = {}
            for node in graph.keys():
                if node != '_start':
                    in_degree[node] = len(graph[node]['prev'])
            queue = copy.deepcopy(graph['_start'])
            topo_order = []

            while queue:
                parent = queue.pop(0)
                topo_order.append(parent)
                for child in graph[parent]['succ']:
                    parent_service = self.find_service_by_id(parent)
                    child_service = self.find_service_by_id(child)
                    if not parent_service or not child_service:
                        error_msg = f"服务节点缺失： {parent if not parent_service else child}"
                        LOGGER.error(f"DAG Validation Error: {error_msg}")
                        return False, error_msg
                    if child_service['input'] != parent_service['output']:
                        error_msg = (
                            f"前后服务节点不匹配, '{parent}' 输出 '{parent_service['output']}', '{child}' 输入 '{child_service['input']}' "
                        )
                        LOGGER.error(f"DAG Validation Error: {error_msg}")
                        return False, error_msg

                    in_degree[child] -= 1
                    if in_degree[child] == 0:
                        queue.append(child)

            if len(topo_order) != len(in_degree):
                error_msg = "应用拓扑图存在循环"
                LOGGER.warning(f"DAG Validation Error: {error_msg}")
                return False, error_msg

            return True, "DAG validation passed"

        return topo_sort(dag.copy())

    def get_source_ids(self):
        source_ids = []
        source_config = self.find_datasource_configuration_by_label(self.source_label)
        if not source_config:
            return []
        for source in source_config['source_list']:
            source_ids.append(source['id'])

        return source_ids

    def prepare_result_visualization_data(self, task, is_last=False):
        source_id = task.get_source_id()
        if source_id in self.customized_source_result_visualization_configs:
            viz_configs = self.customized_source_result_visualization_configs[source_id]
        else:
            viz_configs = self.result_visualization_configs[task.get_source_type()] \
                if (self.result_visualization_configs['allow-flexible-switch'] and
                    task.get_source_type() in self.result_visualization_configs) \
                else self.result_visualization_configs['base']

        viz_functions = self.visualization_cache.sync_and_get(viz_configs)
        visualization_data = []
        for idx, (viz_config, viz_func) in enumerate(zip(viz_configs, viz_functions)):
            try:
                if 'save_expense' in viz_config and viz_config['save_expense'] and not is_last:
                    LOGGER.debug('**** Save expense for visualization, skip this time.')
                    visualization_data.append({"id": idx, "data": None})
                else:
                    visualization_data.append({"id": idx, "data": viz_func(task)})
            except Exception as e:
                LOGGER.warning(f'Failed to load result visualization data: {e}')
                LOGGER.exception(e)

        return visualization_data

    def prepare_system_visualizations_data(self):
        visualization_data = []
        for idx, vf in enumerate(self.system_visualization_configs):
            try:
                al_name = vf['hook_name']
                al_params = eval(vf['hook_params']) if 'hook_params' in vf else {}
                al_params.update({'variables': vf['variables']})
                vf_func = Context.get_algorithm('SYSTEM_VISUALIZER', al_name=al_name, **al_params)
                visualization_data.append({"id": idx, "data": vf_func()})
            except Exception as e:
                LOGGER.warning(f"Failed to load system visualization data: {e}")
                LOGGER.exception(e)

        return visualization_data

    def parse_task_result(self, results):
        __start = time.time()
        for result in results:
            if result is None or result == '':
                continue

            _start = time.time()
            task = Task.deserialize(result)
            _end = time.time()
            source_id = task.get_source_id()
            
            file_path = self.get_file_result(task.get_file_path())

            LOGGER.debug(f'Parse one task for {_end-_start} s')

            LOGGER.debug(task.get_delay_info())

            if not self.source_open:
                break

            self.task_results[source_id].put(copy.deepcopy(task))
            LOGGER.debug(f'[GET RESULT] Put task result in result queue done.')
            self.task_results_for_priority.put(copy.deepcopy(task))
            LOGGER.debug(f'[GET RESULT] Put task result in priority queue done.')

        __end = time.time()
        LOGGER.debug(f'Parse {len(results)} task for {__end-__start} s')

    def fetch_visualization_data(self, source_id):
        assert source_id in self.task_results, f'Source_id {source_id} not found in task results!'
        tasks = self.task_results[source_id].get_all()
        vis_results = []
        _start = time.time()

        for idx, task in enumerate(tasks):
            file_path = self.get_file_result(task.get_file_path())

            try:
                visualization_data = self.prepare_result_visualization_data(task, idx==len(tasks)-1)
            except Exception as e:
                LOGGER.warning(f'Prepare visualization data failed: {str(e)}')
                LOGGER.exception(e)
                continue

            if os.path.exists(file_path):
                os.remove(file_path)

            vis_results.append([{
                'task_id': task.get_task_id(),
                'data': visualization_data,
            }])

            freetask_data = [item for item in visualization_data if not any(k in item.get('data', {}) for k in ['image', 'topology'])]

            self.freetask_results[source_id].put_all([{
                'task_id': task.get_task_id(),
                'task_start_time': task.get_total_start_time() ,
                'data': freetask_data,
            }])

            self.task_results_for_priority.put_all([copy.deepcopy(task)])

        _end = time.time()
        print('-----visualization data time: ', _end - _start)
        print('-----visualization data size: ', len(vis_results))
        return vis_results


    def run_get_result(self):
        time_ticket = 0
        while self.is_get_result:
            try:
                time.sleep(1)
                LOGGER.debug('[GET RESULT] Start to fetch task result...')
                self.get_result_url()
                LOGGER.debug('[GET RESULT] Fetch result url done.')
                if not self.result_url:
                    LOGGER.debug('[NO RESULT] Fetch result url failed.')
                    continue
                _start = time.time()
                response = http_request(self.result_url,
                                        method=NetworkAPIMethod.DISTRIBUTOR_RESULT,
                                        json={'time_ticket': time_ticket, 'size': self.buffered_result_size})
                LOGGER.debug('[GET RESULT] Fetch results with http done.')
                _end = time.time()
                LOGGER.debug(f'Http request for results cost {_end - _start} s')

                if not response:
                    self.result_url = None
                    self.result_file_url = None
                    LOGGER.debug('[NO RESULT] Request result url failed.')
                    continue

                time_ticket = response["time_ticket"]
                results = response['result']
                LOGGER.debug(f'Fetch {len(results)} tasks from time ticket: {time_ticket}')
                self.parse_task_result(results)

            except Exception as e:
                LOGGER.warning(f'Error occurred in getting task result: {str(e)}')
                LOGGER.exception(e)

    def get_system_parameters(self):
        return [{'data': self.prepare_system_visualizations_data()}]

    def check_datasource_config(self, config_path):
        if not YamlOps.is_yaml_file(config_path):
            return None

        config = YamlOps.read_yaml(config_path)
        try:
            source_name = config['source_name']
            source_type = config['source_type']
            source_mode = config['source_mode']
            for camera in config['source_list']:
                name = camera['name']
                if self.inner_datasource:
                    directory = camera['dir']
                else:
                    url = camera['url']
                metadata = camera['metadata']

        except Exception as e:
            LOGGER.warning(f'Datasource config file format error: {str(e)}')
            LOGGER.exception(e)
            return None

        return config

    def check_visualization_config(self, config_path):
        if not YamlOps.is_yaml_file(config_path):
            return None

        config = YamlOps.read_yaml(config_path)

        try:
            for visualization in config:
                viz_name = visualization['name']
                assert isinstance(viz_name, str), '"name" is not a string'
                viz_type = visualization['type']
                assert isinstance(viz_type, str), '"type" is not a string'
                viz_var = visualization['variables']
                assert isinstance(viz_var, list), '"variables" is not a list'
                viz_size = visualization['size']
                assert isinstance(viz_size, int), '"size" is not an integer'
                if 'hook_name' in visualization:
                    assert isinstance(visualization['hook_name'], str), '"hook_name" is not a string'
                if 'hook_params' in visualization:
                    assert isinstance(visualization['hook_params'], str), '"hook_params" is not a string(dict)'
                    assert isinstance(eval(visualization['hook_params']), dict), '"hook_params" is not a string(dict)'
                if 'x_axis' in visualization:
                    assert isinstance(visualization['x_axis'], str), '"x_axis" is not a string'
                if 'y_axis' in visualization:
                    assert isinstance(visualization['y_axis'], str), '"y_axis" is not a string'
            return config
        except Exception as e:
            LOGGER.warning(f'Visualization config file format error: {str(e)}')
            LOGGER.exception(e)
            return None

    def get_resource_url(self):
        cloud_hostname = NodeInfo.get_cloud_node()
        try:
            scheduler_port = PortInfo.get_component_port(SystemConstant.SCHEDULER.value)
        except AssertionError:
            return
        self.resource_url = merge_address(NodeInfo.hostname2ip(cloud_hostname),
                                          port=scheduler_port,
                                          path=NetworkAPIPath.SCHEDULER_GET_RESOURCE)

    def get_result_url(self):
        cloud_hostname = NodeInfo.get_cloud_node()
        try:
            distributor_port = PortInfo.get_component_port(SystemConstant.DISTRIBUTOR.value)
        except AssertionError:
            return
        self.result_url = merge_address(NodeInfo.hostname2ip(cloud_hostname),
                                        port=distributor_port,
                                        path=NetworkAPIPath.DISTRIBUTOR_RESULT)
        self.result_file_url = merge_address(NodeInfo.hostname2ip(cloud_hostname),
                                             port=distributor_port,
                                             path=NetworkAPIPath.DISTRIBUTOR_FILE)

    def get_log_url(self):
        cloud_hostname = NodeInfo.get_cloud_node()
        try:
            distributor_port = PortInfo.get_component_port(SystemConstant.DISTRIBUTOR.value)
        except AssertionError:
            return
        self.log_fetch_url = merge_address(NodeInfo.hostname2ip(cloud_hostname),
                                           port=distributor_port,
                                           path=NetworkAPIPath.DISTRIBUTOR_ALL_RESULT)
        self.log_clear_url = merge_address(NodeInfo.hostname2ip(cloud_hostname),
                                           port=distributor_port,
                                           path=NetworkAPIPath.DISTRIBUTOR_CLEAR_DATABASE)

    def get_file_result(self, file_name):
        if not self.result_file_url:
            return ''
        response = http_request(self.result_file_url,
                                method=NetworkAPIMethod.DISTRIBUTOR_FILE,
                                no_decode=True,
                                json={'file': file_name},
                                stream=True)
        if response is None:
            self.result_file_url = None
            return ''
        with open(file_name, 'wb') as file_out:
            for chunk in response.iter_content(chunk_size=8192):
                file_out.write(chunk)
        return file_name

    def download_log_file(self):
        self.parse_base_info()
        self.get_log_url()
        if not self.log_fetch_url:
            return ''

        response = http_request(self.log_fetch_url, method=NetworkAPIMethod.DISTRIBUTOR_ALL_RESULT, )
        if response is None:
            self.log_fetch_url = None
            return ''
        results = response['result']

        http_request(self.log_clear_url, method=NetworkAPIMethod.DISTRIBUTOR_CLEAR_DATABASE)

        return results

    def get_result_visualization_config(self, source_id):
        self.parse_base_info()
        source_config = self.find_datasource_configuration_by_label(self.source_label)
        source_type = source_config['source_type']

        if source_id in self.customized_source_result_visualization_configs:
            visualizations = self.customized_source_result_visualization_configs[source_id]
        else:
            visualizations = self.result_visualization_configs[source_type] \
                if (self.result_visualization_configs['allow-flexible-switch'] and
                    source_type in self.result_visualization_configs) \
                else self.result_visualization_configs['base']

        return [{'id': idx, **vf} for idx, vf in enumerate(visualizations)]

    def get_system_visualization_config(self):
        self.parse_base_info()
        return [{'id': idx, **vf} for idx, vf in enumerate(self.system_visualization_configs)]

    def get_priority_info(self):
        """
        :return:
        {
            "nodes": [node1,node2,...],
            "services": {node1:[service1,...], node2:[service2,...]},
            "priority_num":10
        }
        """
        self.parse_base_info()
        node_services = KubeConfig.get_node_services_dict()

        return {
            'nodes': list(node_services.keys()),
            'services': node_services,
            'priority_num': self.priority['priority_levels']
        }

    def get_priority_queue(self, node):
        """
        node: node name
        :return:
        {
            service1:
            [
                # priority queue 1
                [{
                source_id: 1,
                task_id: 1,
                importance: 1
                urgency: 1
                },{},{},{}],
                [],
                [],
                [],
                []
            ],
            service2:
            [
                [],
                [],
                [],
                [],
                []

            ]
        }
        """
        show_time = time.time() - 2
        services = KubeConfig.get_node_services_dict()[node]
        tasks: list[Task] = self.task_results_for_priority.get_all()
        total_time_list = sorted([task.get_real_end_to_end_time() for task in tasks])
        show_time = time.time() - total_time_list[len(total_time_list) // 2] if total_time_list else 0
        print('*** current time: ', time.time())
        print('*** show_time: ', show_time)
        print('*** control interval: ', total_time_list[len(total_time_list) // 2] if total_time_list else 0)
        self.priority_task_buffer.extend(tasks)

        for task in self.priority_task_buffer:
            print(f'---task_id: {task.get_task_id()}, total_end_time: {task.get_total_end_time()}')
        # Filter tasks satisfied time requirements
        self.priority_task_buffer = [task for task in self.priority_task_buffer if
                                     task.get_total_end_time() >= show_time]
        priority_queue = {service: [[] for _ in range(self.priority['priority_levels'])] for service in services}

        for service in services:
            for task in self.priority_task_buffer:
                enter_time, quit_time = task.extract_priority_timestamp(service)
                print(
                    f'---task_id: {task.get_task_id()}, service: {service}, enter_time: {enter_time}, quit_time: {quit_time}')
                if task.get_service(service) and task.get_service(service).get_execute_device() == node and \
                        quit_time >= show_time:
                    priority_queue[service][task.get_service(service).get_priority()].append({
                        'source_id': task.get_source_id(),
                        'task_id': task.get_task_id(),
                        'importance': task.get_source_importance(),
                        'urgency': task.get_service(service).get_urgency(),
                        'priority': task.get_service(service).get_priority()
                    })
                    break

        return priority_queue
