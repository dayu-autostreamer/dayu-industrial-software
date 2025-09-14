ARG REG=docker.io
FROM ${REG}/dayuhub/tensorrt:trt8

LABEL authors="Wenhui Zhou"

ARG dependency_dir=dependency
ARG lib_dir=dependency/core/lib
ARG base_dir=dependency/core/processor
ARG code_dir=components/processor
ARG app_dir=dependency/core/applications/edge_eye_stage1

ENV DEBIAN_FRONTEND=noninteractive

ENV TZ=Asia/Shanghai

COPY ${lib_dir}/requirements.txt ./lib_requirements.txt
COPY ${base_dir}/requirements.txt ./base_requirements.txt
COPY ${app_dir}/requirements.txt ./app_requirements.txt


RUN pip3 install --upgrade pip && \
    pip3 uninstall -y numpy && \
    pip3 install -r lib_requirements.txt --ignore-installed -i https://mirrors.aliyun.com/pypi/simple && \
    pip3 install -r base_requirements.txt -i https://mirrors.aliyun.com/pypi/simple && \
    pip3 install -r app_requirements.txt -i https://mirrors.aliyun.com/pypi/simple

COPY ${dependency_dir} /home/dependency
ENV PYTHONPATH="/home/dependency"

WORKDIR /app
COPY  ${code_dir}/* /app/


CMD ["gunicorn", "main:app", "-c", "./gunicorn.conf.py"]