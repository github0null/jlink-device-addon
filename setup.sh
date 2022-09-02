#!/bin/bash

py_pkgs=(click cmsis_pack_manager pyelftools intervaltree dataclasses)

for name in ${py_pkgs[*]}
do
    python3 -m pip --no-cache-dir install $name -t ./ -i http://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com
done

python3 ./__main__.py --help

exit $?
