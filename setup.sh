#!/bin/bash

py_pkgs=(click cmsis_pack_manager pyelftools)

for var in "$py_pkgs"
do
    python3 -m pip --no-cache-dir install $var -t ./ -i http://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com
done
