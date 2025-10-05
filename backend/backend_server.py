import copy
import json
import threading
import time
from datetime import datetime

from fastapi import FastAPI, UploadFile, File, Body, BackgroundTasks
from fastapi.routing import APIRoute
from starlette.responses import JSONResponse, FileResponse

from fastapi.middleware.cors import CORSMiddleware

from core.lib.common import LOGGER, Counter, Queue, FileOps
from core.lib.network import http_request, NetworkAPIMethod, NetworkAPIPath

from backend_core import BackendCore
from kube_helper import KubeHelper


class BackendServer:
    def __init__(self):

        self.server = BackendCore()

        self.app = FastAPI(routes=[
            APIRoute(NetworkAPIPath.BACKEND_GET_POLICY,
                     self.get_all_schedule_policies,
                     response_class=JSONResponse,
                     methods=[NetworkAPIMethod.BACKEND_GET_POLICY]
                     ),
            APIRoute(NetworkAPIPath.BACKEND_INSTALL_SERVICE,
                     self.install_service,
                     response_class=JSONResponse,
                     methods=[NetworkAPIMethod.BACKEND_INSTALL_SERVICE]
                     ),
            APIRoute(NetworkAPIPath.BACKEND_GET_INSTALLED,
                     self.get_installed_services,
                     response_class=JSONResponse,
                     methods=[NetworkAPIMethod.BACKEND_GET_INSTALLED]
                     ),
            APIRoute(NetworkAPIPath.BACKEND_GET_DAG,
                     self.get_dag_workflows,
                     response_class=JSONResponse,
                     methods=[NetworkAPIMethod.BACKEND_GET_DAG]
                     ),
            APIRoute(NetworkAPIPath.BACKEND_GET_ALL_SERVICES,
                     self.get_all_services,
                     response_class=JSONResponse,
                     methods=[NetworkAPIMethod.BACKEND_GET_ALL_SERVICES]
                     ),
            APIRoute(NetworkAPIPath.BACKEND_POST_DAG,
                     self.update_dag_workflows,
                     response_class=JSONResponse,
                     methods=[NetworkAPIMethod.BACKEND_POST_DAG]
                     ),
            APIRoute(NetworkAPIPath.BACKEND_DELETE_DAG,
                     self.delete_dag_workflow,
                     response_class=JSONResponse,
                     methods=[NetworkAPIMethod.BACKEND_DELETE_DAG]
                     ),
            APIRoute(NetworkAPIPath.BACKEND_POST_DATASOURCE,
                     self.upload_datasource_config_file,
                     response_class=JSONResponse,
                     methods=[NetworkAPIMethod.BACKEND_POST_DATASOURCE]
                     ),
            APIRoute(NetworkAPIPath.BACKEND_GET_SERVICE_INFO,
                     self.get_service_info,
                     response_class=JSONResponse,
                     methods=[NetworkAPIMethod.BACKEND_GET_SERVICE_INFO]
                     ),
            APIRoute(NetworkAPIPath.BACKEND_GET_DATASOURCE,
                     self.get_datasource_info,
                     response_class=JSONResponse,
                     methods=[NetworkAPIMethod.BACKEND_GET_DATASOURCE]
                     ),
            APIRoute(NetworkAPIPath.BACKEND_DELETE_DATASOURCE,
                     self.delete_datasource_info,
                     response_class=JSONResponse,
                     methods=[NetworkAPIMethod.BACKEND_DELETE_DATASOURCE]),
            APIRoute(NetworkAPIPath.BACKEND_SUBMIT_QUERY,
                     self.submit_query,
                     response_class=JSONResponse,
                     methods=[NetworkAPIMethod.BACKEND_SUBMIT_QUERY]
                     ),
            APIRoute(NetworkAPIPath.BACKEND_UNINSTALL_SERVICE,
                     self.uninstall_service,
                     response_class=JSONResponse,
                     methods=[NetworkAPIMethod.BACKEND_UNINSTALL_SERVICE]
                     ),
            APIRoute(NetworkAPIPath.BACKEND_STOP_QUERY,
                     self.stop_query,
                     response_class=JSONResponse,
                     methods=[NetworkAPIMethod.BACKEND_STOP_QUERY]
                     ),
            APIRoute(NetworkAPIPath.BACKEND_INSTALL_STATE,
                     self.get_install_state,
                     response_class=JSONResponse,
                     methods=[NetworkAPIMethod.BACKEND_INSTALL_STATE]
                     ),
            APIRoute(NetworkAPIPath.BACKEND_QUERY_STATE,
                     self.get_query_state,
                     response_class=JSONResponse,
                     methods=[NetworkAPIMethod.BACKEND_QUERY_STATE]
                     ),
            APIRoute(NetworkAPIPath.BACKEND_SOURCE_LIST,
                     self.get_source_list,
                     response_class=JSONResponse,
                     methods=[NetworkAPIMethod.BACKEND_SOURCE_LIST]
                     ),
            APIRoute(NetworkAPIPath.BACKEND_TASK_RESULT,
                     self.get_task_result,
                     response_class=JSONResponse,
                     methods=[NetworkAPIMethod.BACKEND_TASK_RESULT]
                     ),
            APIRoute(NetworkAPIPath.BACKEND_FREE_VISUALIZATION_CONFIG,
                     self.get_free_visualization_config,
                     response_class=JSONResponse,
                     methods=[NetworkAPIMethod.BACKEND_FREE_VISUALIZATION_CONFIG]
                     ),
            APIRoute(NetworkAPIPath.BACKEND_FREE_TASK_RESULT,
                     self.get_free_task_result,
                     response_class=JSONResponse,
                     methods=[NetworkAPIMethod.BACKEND_FREE_TASK_RESULT]
                     ),
            APIRoute(NetworkAPIPath.BACKEND_EVENT_RESULT,
                     self.get_event_result,
                     response_class=JSONResponse,
                     methods=[NetworkAPIMethod.BACKEND_EVENT_RESULT]
                     ),
            APIRoute(NetworkAPIPath.BACKEND_EVENT_DETAIL,
                     self.get_event_detail,
                     response_class=JSONResponse,
                     methods=[NetworkAPIMethod.BACKEND_EVENT_DETAIL]
                     ),
            APIRoute(NetworkAPIPath.BACKEND_SYSTEM_PARAMETERS,
                     self.get_system_parameters,
                     response_class=JSONResponse,
                     methods=[NetworkAPIMethod.BACKEND_SYSTEM_PARAMETERS]
                     ),
            APIRoute(NetworkAPIPath.BACKEND_POST_RESULT_VISUALIZATION_CONFIG,
                     self.upload_result_visualization_config,
                     response_class=JSONResponse,
                     methods=[NetworkAPIMethod.BACKEND_POST_RESULT_VISUALIZATION_CONFIG]
                     ),
            APIRoute(NetworkAPIPath.BACKEND_GET_RESULT_VISUALIZATION_CONFIG,
                     self.get_result_visualization_config,
                     response_class=JSONResponse,
                     methods=[NetworkAPIMethod.BACKEND_GET_RESULT_VISUALIZATION_CONFIG]
                     ),
            APIRoute(NetworkAPIPath.BACKEND_GET_SYSTEM_VISUALIZATION_CONFIG,
                     self.get_system_visualization_config,
                     response_class=JSONResponse,
                     methods=[NetworkAPIMethod.BACKEND_GET_SYSTEM_VISUALIZATION_CONFIG]
                     ),
            APIRoute(NetworkAPIPath.BACKEND_DOWNLOAD_LOG,
                     self.download_log,
                     response_class=FileResponse,
                     methods=[NetworkAPIMethod.BACKEND_DOWNLOAD_LOG]
                     ),
            APIRoute(NetworkAPIPath.BACKEND_EDGE_NODE,
                     self.get_edge_nodes,
                     response_class=JSONResponse,
                     methods=[NetworkAPIMethod.BACKEND_EDGE_NODE]
                     ),
            APIRoute(NetworkAPIPath.BACKEND_DATASOURCE_STATE,
                     self.get_datasource_state,
                     response_class=JSONResponse,
                     methods=[NetworkAPIMethod.BACKEND_DATASOURCE_STATE]
                     ),
            APIRoute(NetworkAPIPath.BACKEND_RESET_DATASOURCE,
                     self.reset_datasource,
                     response_class=JSONResponse,
                     methods=[NetworkAPIMethod.BACKEND_RESET_DATASOURCE]
                     ),
            APIRoute(NetworkAPIPath.BACKEND_PRIORITY_INFO,
                     self.get_priority_info,
                     response_class=JSONResponse,
                     methods=[NetworkAPIMethod.BACKEND_PRIORITY_INFO]
                     ),
            APIRoute(NetworkAPIPath.BACKEND_PRIORITY_QUEUE,
                     self.get_priority_queue,
                     response_class=JSONResponse,
                     methods=[NetworkAPIMethod.BACKEND_PRIORITY_QUEUE]
                     ),

        ], log_level='trace', timeout=6000)

        self.app.add_middleware(
            CORSMiddleware, allow_origins=["*"], allow_credentials=True,
            allow_methods=["*"], allow_headers=["*"],
        )

    async def get_all_schedule_policies(self):
        """
        :return:
        display all scheduled policies
        {
            policy_id:id,
            policy_name：name
        }
        """
        self.server.parse_base_info()
        cur_policy = []
        for policy in self.server.schedulers:
            cur_policy.append(
                {'policy_id': policy['id'],
                 'policy_name': policy['name']})
        return cur_policy

    async def get_installed_services(self):
        """
        get current installed services
        :return:
        ["face_detection", "..."]
        """
        service_list = [service['id'] for service in self.server.services]
        current_service_list = []

        if KubeHelper.check_pods_running(self.server.namespace):
            for service_id in service_list:
                if KubeHelper.check_pod_name(service_id, namespace=self.server.namespace):
                    current_service_list.append(service_id)
        return current_service_list

    async def get_dag_workflows(self):
        """
        get current dag workflows
        [
                    {
                        "dag_id":1,
                        "dag_name":"headup",
                        "dag":{
                            "node_id_A":{
                                "id" : "skyrim's node",
                                "prev" : [],
                                "succ" : ["node_id_B", ...],
                                "service_id" : "car_detection"
                            },
                            "node_id_B":{
                                "id" : "skyrim's node",
                                "prev" : ["node_id_A"],
                                "succ" : [],
                                "service_id" : "plate_recognition"
                            }
                        }
                    },
                    {
                        "dag_id":2,
                        "dag_name":"headup",
                        "dag":{
                            "node_id_A":{
                                "id" : "skyrim's node",
                                "prev" : [],
                                "succ" : ["node_id_B", ...],
                                "service_id" : car_detection
                            },
                            "node_id_B":{
                                "id" : "skyrim's node",
                                "prev" : ["node_id_A"],
                                "succ" : [],
                                "service_id" : plate_recognition
                            }
                        }
                    }
                ],
        :return:
        """

        return self.server.dags

    async def get_all_services(self):
        """
        get all service containers

        [
        {
            "name": "face_detection",
            "description": "face detection"
        },
        {
            "name": "car_detection"，
            "description": "car detection"
        }
    ]
        :return:
        """
        self.server.parse_base_info()
        service_dict = {}
        services = self.server.services
        for service in services:
            service['description'] = (service['description'] + ' (in:' + service['input']
                                      + ', out: ' + service['output'] + ')')
            service_dict[service['id']] = service if service['id'] not in service_dict else service_dict[service['id']]
        return [service_dict[service_id] for service_id in service_dict]

    async def update_dag_workflows(self, data=Body(...)):
        """
        add new dag workflows
        body
        {
            "dag_name":"headup",
            "dag":{
                "_start" : [node_id_A...],//需要是一个列表 支持多个begin
                "service_id":{
                    "prev" : [],
                    "succ" : ["node_id_B", ...],
                    "service_id" : car_detection
                },
                "service_id":{
                    "prev" : ["node_id_A"],
                    "succ" : [],
                    "service_id" : plate_recognition
                }
            }
        },
        :return:
            {'state':success/fail, 'msg':'...'}
        """
        dag_name = data['dag_name']
        dag = data['dag']
        state, msg = self.server.check_dag(dag)
        if state:
            self.server.dags.append({
                'dag_id': Counter.get_count('dag_id'),
                'dag_name': dag_name,
                'dag': dag
            })

            return {'state': 'success', 'msg': '添加新应用成功'}
        else:
            return {'state': 'fail', 'msg': f'添加新应用失败：{msg}'}

    async def delete_dag_workflow(self, data=Body(...)):
        """
        delete dag workflow
        body:
        {
            "dag_id":1
        }
        :return:
        {'state':success/fail, 'msg':'...'}
        """

        data = json.loads(str(data, encoding='utf-8'))
        dag_id = int(data['dag_id'])
        for index, dag in enumerate(self.server.dags):
            if dag['dag_id'] == dag_id:
                del self.server.dags[index]
                return {'state': 'success', 'msg': '删除应用成功'}

        return {'state': 'fail', 'msg': '删除应用失败：应用不存在'}

    async def get_service_info(self, service):
        """
        get information of installed service container
        :param service:
        :return:
        [
            {
                "ip":114.212.81.11
                "hostname"
                “cpu”:
                "memory":
                "bandwidth"
                "age"
            }
        ]

        """
        try:
            if service == 'null':
                return []
            info = KubeHelper.get_service_info(service_name=service, namespace=self.server.namespace)

            self.server.get_resource_url()
            if not self.server.resource_url:
                return []
            resource_data = http_request(self.server.resource_url, method=NetworkAPIMethod.SCHEDULER_GET_RESOURCE)
            if resource_data:
                bandwidth = '-'
                for hostname in resource_data:
                    single_resource_info = resource_data[hostname]
                    if 'bandwidth' in single_resource_info and single_resource_info['bandwidth'] != 0:
                        bandwidth = f"{single_resource_info['bandwidth']:.2f}Mbps"
                for single_info in info:
                    single_info['bandwidth'] = bandwidth
        except Exception as e:
            LOGGER.exception(e)
            return []

        return info

    async def upload_datasource_config_file(self, file: UploadFile = File(...)):
        """
        body: file
        :return:
            {'state':success/fail, 'msg':'...'}
        """
        file_data = await file.read()
        with open('datasource_config.yaml', 'wb') as buffer:
            buffer.write(file_data)

        config = self.server.check_datasource_config('datasource_config.yaml')
        FileOps.remove_file('datasource_config.yaml')
        if config:

            self.server.source_configs.append(self.server.fill_datasource_config(config))
            return {'state': 'success', 'msg': '数据源配置成功'}
        else:
            return {'state': 'fail', 'msg': '数据源配置失败，请检查上传文件格式'}

    async def get_datasource_info(self):
        """
        :return:

            [
            {
                "source_label": "car"
                "source_name": "config1",
                “source_type”: "video",
                "source_mode": "http_video",
                "camera_list":[
                    {
                        "name": "camera1",
                        "url": "rtsp/114.212.81.11...",
                        "describe":""
                        “resolution”: "1080p"
                        "fps":"25fps"
                        "importance": 4

                    },
                    {}
                ]
            }
        ]
        """
        return self.server.source_configs

    async def delete_datasource_info(self, data=Body(...)):
        """
        delete dag source info
        body:
        {
            "source_label":...
        }
        :return:
        {'state':success/fail, 'msg':'...'}
        """

        data = json.loads(str(data, encoding='utf-8'))
        source_label = data['source_label']
        for index, datasource in enumerate(self.server.source_configs):
            if datasource['source_label'] == source_label:
                del self.server.source_configs[index]
                return {'state': 'success', 'msg': '删除数据源成功'}

        return {'state': 'fail', 'msg': '删除数据源失败: 数据源不存在'}

    async def install_service(self, data=Body(...)):
        """
        install system components to prepare for executing dags
        body
        {
            "dag_id": (id),
            "policy_id": (id)
        }

        content = {
            source_config_label: source_config_label,
            policy_id: policy_id,
            source: this.selectedSources,
        };

        source = [
            { id: 0, name: "s1", dag_selected: "", node_selected: [] },
            { id: 1, name: "s2", dag_selected: "", node_selected: [] }...
        ],

        :return:
        {'msg': 'service start successfully'}
        {'msg': 'Invalid service name!'}
        """

        data = json.loads(str(data, encoding='utf-8'))

        source_label = data['source_config_label']
        policy_id = data['policy_id']
        source_map_list = data['source']

        dag_list = [x['dag_selected'] for x in source_map_list]
        node_set_list = [x['node_selected'] for x in source_map_list]

        source_deploy = []

        policy = self.server.find_scheduler_policy_by_id(policy_id)
        if policy is None:
            return {'state': 'fail', 'msg': '下装服务失败: 调度策略不存在'}

        source_config = self.server.find_datasource_configuration_by_label(source_label)
        if source_config is None:
            return {'state': 'fail', 'msg': '下装服务失败: 数据源配置不存在'}

        if len(source_config) != len(dag_list) != len(node_set_list):
            return {'state': 'fail', 'msg': '下装服务失败: 数据源映射失败'}

        for source, dag_id, node_set in zip(source_config['source_list'], dag_list, node_set_list):

            dag = self.server.find_dag_by_id(dag_id)
            if dag is None:
                return {'state': 'fail', 'msg': '下装服务失败: 拓扑应用不存在'}

            for node in node_set:
                if not self.server.check_node_exist(node):
                    return {'state': 'fail', 'msg': f'下装应用失败: 边缘节点 "{node}" 不存在'}

            source.update({'source_type': source_config['source_type'], 'source_mode': source_config['source_mode']})

            source_deploy.append({'source': source, 'dag': dag, 'node_set': node_set})

        try:
            result, msg = self.server.parse_and_apply_templates(policy, source_deploy)
        except Exception as e:
            LOGGER.warning(f'Parse and apply templates failed: {str(e)}')
            LOGGER.exception(e)
            result = False
            msg = '未知系统错误，请查看后端容器日志'

        if result:
            return {'state': 'success', 'msg': '下装服务成功'}
        else:
            return {'state': 'fail', 'msg': f'下装服务失败: {msg}'}

    async def uninstall_service(self):
        """
        {'state':"success/fail",'msg':'...'}
        :return:
        """
        try:
            result, msg = self.server.parse_and_delete_templates()

        except Exception as e:
            LOGGER.warning(f'卸载服务失败: {str(e)}')
            LOGGER.exception(e)
            result = False
            msg = f'未知系统错误，请查看后端容器日志'

        self.server.clear_yaml_docs()

        if result:
            return {'state': 'success', 'msg': '卸载服务成功'}
        else:
            return {'state': 'fail', 'msg': f'卸载服务失败: {msg}'}

    async def get_install_state(self):
        """
        :return:
        {'state':'install/uninstall'}
        """

        state = 'install' if KubeHelper.check_component_pods_exist(self.server.namespace) else 'uninstall'
        return {'state': state}

    async def submit_query(self, data=Body(...)):
        """
        body
        {
            "source_label": "..."
        }
        :return:
        {'msg': 'Datasource open successfully'}
        {'msg': 'Invalid service name'}
        """

        data = json.loads(str(data, encoding='utf-8'))

        source_label = data['source_label']
        if not self.server.find_datasource_configuration_by_label(source_label):
            return {'state': 'fail', 'msg': '数据源打开失败：数据源配置不存在'}

        self.server.source_open = True
        self.server.source_label = source_label
        source_ids = self.server.get_source_ids()
        for source_id in source_ids:
            self.server.task_results[source_id] = Queue(self.server.buffered_result_size)

        time.sleep((len(source_ids) - 1) * 4)

        self.server.is_get_result = True
        threading.Thread(target=self.server.run_get_result).start()

        return {'state': 'success', 'msg': '数据源打开成功'}

    async def stop_query(self):
        """
        {'source_label':'...'}
        :return:
        {'state':"success/fail",'msg':'...'}
        """

        self.server.source_open = False
        self.server.source_label = ''
        self.server.is_get_result = False
        self.server.task_results.clear()
        self.server.customized_source_result_visualization_configs.clear()
        time.sleep(1)

        return {'state': 'success', 'msg': '数据源关闭成功'}

    async def get_query_state(self):
        """
        :return:
        {'state':'open/close','source_label':''}
        """
        if self.server.inner_datasource:
            state = 'open' if self.server.source_open else 'close'
        else:
            state = 'disabled'

        return {'state': state,
                'source_label': self.server.source_label
                }

    async def get_source_list(self):
        """
        [
            {
                "id":"video_source1",
                "label":"source1"
            },
            ...
        ]
        :return:
        """
        if not self.server.source_open:
            return []

        source_config = self.server.find_datasource_configuration_by_label(self.server.source_label)
        if not source_config:
            return []

        return [{'id': source['id'], 'label': source['name']} for source in source_config['source_list']]

    async def get_edge_nodes(self):
        return self.server.get_edge_nodes()

    async def get_task_result(self):
        """
        20 lasted results
        {
        'datasource1':[
            task_id: 12,
            data: {0:{"delay":"0.5"},1:{"image":"xxx"}}

        ],
        'datasource2':[]
        }
        :return:
        """
        if not self.server.source_open:
            return {}
        ans = {}
        source_config = self.server.find_datasource_configuration_by_label(self.server.source_label)
        for source in source_config['source_list']:
            source_id = source['id']
            ans[source_id] = self.server.fetch_visualization_data(source_id)

        return ans

    async def get_free_visualization_config(self):
        """
        get free visualization configuration
        """
        return self.server.get_free_visualization_config()

    async def get_free_task_result(self, start_time: str = None, end_time: str = None):
        """
        Get free query results within a time window
        :param start_time: optional, float unix timestamp or ISO8601 string
        :param end_time: optional, float unix timestamp or ISO8601 string
        :return:
            {
            'datasource1':[
                task_id: 12,
                data: {0:{"delay":"0.5"}...}

            ],
            'datasource2':[]
            }
        """
        if not self.server.source_open:
            return {}

        # helper to parse time parameter
        def parse_time(t):
            if t is None:
                return None
            try:
                return float(t)
            except Exception:
                try:
                    ts = t.strip()
                    # Handle trailing Z (UTC)
                    if ts.endswith('Z'):
                        ts = ts[:-1] + '+00:00'
                    return datetime.fromisoformat(ts).timestamp()
                except Exception:
                    LOGGER.warning(f'Invalid time format for parameter: {t}')
                    return None

        start_ts = parse_time(start_time)
        end_ts = parse_time(end_time)

        if start_ts is None or end_ts is None or start_ts > end_ts:
            LOGGER.warning(f'Invalid start time "{start_ts}" and end time "{end_ts}"')
            return {}

        ans = {}
        source_config = self.server.find_datasource_configuration_by_label(self.server.source_label)
        for source in source_config['source_list']:
            source_id = source['id']
            ans[source_id] = self.server.fetch_free_task_visualization_data(start_ts, end_ts, source_id)

        return ans

    async def get_event_result(self):
        """
        Query event alert interface
        :return:
        {
            'datasource1': [
                'task_id':
                'massage':
            ],
            'datasource2':[]
        }
        """
        if not self.server.source_open:
            return {}

        ans = []
        for idx, event_res in self.server.event_results.items():
            for info in event_res:
                if info['is_read']:
                    continue
                info['is_read'] = True
                ans.append(info)

        return ans

    async def get_event_detail(self):
        if not self.server.source_open:
            return []
        ans = copy.deepcopy(self.server.full_event_results)
        self.server.full_event_results = []
        return ans

    async def get_system_parameters(self):
        return self.server.get_system_parameters()

    async def get_result_visualization_config(self, source_id):
        """
        get visualization configuration
        """
        source_id = int(source_id)
        return self.server.get_result_visualization_config(source_id)

    async def upload_result_visualization_config(self, source_id, file: UploadFile = File(...)):
        """
        body: file
        :return:
        {'state': success / fail, 'msg': '...'}
        """

        source_id = int(source_id)
        file_data = await file.read()
        with open('result_visualization_config.yaml', 'wb') as buffer:
            buffer.write(file_data)

        config = self.server.check_visualization_config('result_visualization_config.yaml')
        FileOps.remove_file('result_visualization_config.yaml')
        if config:
            self.server.customized_source_result_visualization_configs[source_id] = copy.deepcopy(config)
            return {'state': 'success', 'msg': '可视化模块配置成功'}
        else:
            return {'state': 'fail', 'msg': '可视化模块配置失败，请检查上传文件格式'}


    async def get_system_visualization_config(self):
        """
        get visualization configuration
        """
        return self.server.get_system_visualization_config()


    async def get_datasource_state(self):
        state = 'open' if self.server.source_open else 'close'
        if state == 'close':
            return {'state': state}
        source_label = self.server.source_label
        config = self.server.find_datasource_configuration_by_label(source_label)
        if config is None:
            LOGGER.warning(f'Config of "{source_label}" does not exist.')
            return {'state': 'close'}
        return {'state': state, **config}


    async def reset_datasource(self):
        self.server.source_open = False


    async def download_log(self, backtask: BackgroundTasks):
        """
        :return:
        file
        """
        file_name = self.server.get_log_file_name()
        if not file_name:
            formatted_time = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
            file_name = f'LOG_SYSTEM_DAYU_NAMESPACE_{self.server.namespace}_TIME_{formatted_time}'

        log_content = self.server.download_log_file()
        with open(self.server.log_file_path, 'w') as f:
            json.dump(log_content, f)
        backtask.add_task(FileOps.remove_file, self.server.log_file_path)
        return FileResponse(
            path=self.server.log_file_path,
            filename=f'{file_name}.json',
            background=backtask.add_task(FileOps.remove_file, self.server.log_file_path)
        )


    async def get_priority_info(self):
        """
        :return:
        {
            "nodes": [node1, node2, ...],
            "services": {node1: [service1, ...], node2: [service2, ...]},
            "priority_num": 10
        }
        """
        return self.server.get_priority_info()


    async def get_priority_queue(self, node):
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
                    }, {}, {}, {}],
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
        return self.server.get_priority_queue(node)
