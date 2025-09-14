ARG REG=docker.io
FROM ${REG}/dayuhub/tensorrt:trt8

LABEL authors="Wenhui Zhou"

ARG dependency_dir=dependency
ARG lib_dir=dependency/core/lib
ARG base_dir=dependency/core/processor
ARG code_dir=components/processor
ARG app_dir=dependency/core/applications/audio_sampling

# Required to build Ubuntu 20.04 without user prompts with DLFW container
ENV DEBIAN_FRONTEND=noninteractive

ENV TZ=Asia/Shanghai

RUN apt-get update && apt-get install -y \
    wget \
    lsb-release \
    software-properties-common \
    gnupg \
    build-essential


RUN apt-get update && apt-get install -y llvm-9 llvm-9-dev  libsndfile1
ENV LLVM_CONFIG=/usr/bin/llvm-config-9


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
