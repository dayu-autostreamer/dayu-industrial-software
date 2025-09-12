from core.lib.common import Context


class GeneratorServer:

    @staticmethod
    def run():
        source_id = Context.get_parameter('SOURCE_ID', direct=False)
        source_type = Context.get_parameter('SOURCE_TYPE')
        source_importance = Context.get_parameter('SOURCE_IMPORTANCE', direct=False)
        source_priority = Context.get_parameter('SOURCE_PRIORITY', direct=False)
        source_url = Context.get_parameter('SOURCE_URL')
        source_metadata = Context.get_parameter('SOURCE_METADATA', direct=False)
        dag = Context.get_parameter('DAG', direct=False)

        generator = Context.get_algorithm('GENERATOR', al_name=source_type,
                                          source_id=source_id, source_type=source_type,
                                          priority_coefficients=source_priority,
                                          source_importance=source_importance, source_url=source_url,
                                          source_metadata=source_metadata, dag=dag)
        generator.run()
