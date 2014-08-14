cd `dirname $0`
path=`pwd`
/usr/local/bin/python $path/confilterd.py stop
ps -ef|grep $path/confilterd.py|grep -v grep|awk '{print $2}'|xargs kill
