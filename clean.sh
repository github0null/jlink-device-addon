#!/bin/bash

pydc_files=`ls -a | grep -E '\.py[dc]$' | xargs`
for v in $pydc_files
do
    echo "del $v"
    rm -f $v
done

py_files=`ls -a | grep -E '\.py$' | xargs`
for v in $py_files
do
    if [ "$v" != "__main__.py" ];then
        echo "del $v"
        rm -f $v
    fi
done

dist_infos=`ls -a | grep -E '\.(dist-info|egg-info)$' | xargs`
for dir in $dist_infos
do
    prod_dirs=`cat $dir/top_level.txt | xargs`
    if [ x"$prod_dirs" != x"" ];then
        echo "del $prod_dirs"
        rm -rf $prod_dirs
    fi
    echo "del $dir"
    rm -rf $dir
done

py_caches=`find . -name '__pycache__' | xargs`
if [ v"$py_caches" != v"" ];then
    echo "del $py_caches"
    rm -rf $py_caches
fi

echo "cleanup done !"
