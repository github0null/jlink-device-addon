#!/bin/bash

if [ x"$EIDE_PY3_CMD" == x"" ]; then
    echo "warning: EIDE_PY3_CMD not set, using system python."
    EIDE_PY3_CMD=python
fi

py_pkgs=(click cmsis_pack_manager pyelftools intervaltree dataclasses)

for name in ${py_pkgs[*]}
do
    ${EIDE_PY3_CMD} -m pip --no-cache-dir install $name -t ./ -i http://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com
done

${EIDE_PY3_CMD} ./__main__.py --help

exit $?
