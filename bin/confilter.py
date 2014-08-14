#encoding:utf-8
#!/usr/bin/python 
#Author: Cheng Tong
#Email: frostmourn716@gmail.com

import ConfigParser
import ahocorasick
import logging
import logging.config
import json
import sys
import os
import gevent.socket as socket
from gevent import wsgi, pool
from urllib import unquote

# define somg global variables
CUR_PATH = sys.path[0] + os.sep
DICT_PATH = CUR_PATH + "../data/"
CONFIG_FILE = CUR_PATH + "../conf/confilter.cfg"
LOG_CONFIG = CUR_PATH + "../conf/logger.cfg"

# get logger
logging.config.fileConfig(LOG_CONFIG)
log = logging.getLogger("confilter")

# define config file parser class
class Config(object):

    def __init__(self):
        self.__parser = ConfigParser.ConfigParser()
        self.__configFile = CONFIG_FILE
        self.__info = "info"
        self.__dictGroup = "dict_groups"
        self.__dictGroupPrefix = "dict_group_"

    def __getValue(self,sec,key):
        if not sec or not key:
            log.error("Invalid parameter. [sec]: %s, [key]: %s" % (sec, key))
            return False

        try:
            fp = open(self.__configFile)
            self.__parser.readfp(fp)
            value = self.__parser.get(sec, key)
            fp.close()
        except Exception,e:
            log.critical("Exception caught. [Exception]: %s" % e)
            return False
        else:
            return value

    def get(self,key):
        return self.__getValue(self.__info, key)

    def getDict(self):
        # get dict group keys
        keys = self.__getValue(self.__dictGroup, 'keys')
        if not keys:
            log.error("Config file parse error. No value set for [dict_groups]:keys")
            return False
        
        # according group keys, get dicts from each group
        result = {}
        for dictGroup in keys.split(','):
            if not dictGroup:
                continue

            result[dictGroup] = {}
            for dictName, dic in self.__parser.items(self.__dictGroupPrefix \
                    + dictGroup):
                result[dictGroup][dictName] = dic

        return result.iteritems()
     
# define keyword matching class
class Confilter(object):

    def __init__(self, dictFile):
        self.__tree = ahocorasick.KeywordTree()
        try:
            fp = open(dictFile)
            for line in fp:
                self.__tree.add(line.rstrip("\n"))
            fp.close()
            self.__tree.make()
        except Exception,e:
            log.critical("Exception caught in Confilter.__init__ function. \
            [Exception]: %s" % e)
            return None

    def findall(self, content):
        hitList = []
        for start, end in self.__tree.findall(content):
            hitList.append(content[start:end])
        return hitList

# init environment
config = Config()

def initConfilters():
    dicts = config.getDict()
    if not dicts:
        log.error("No dicts found according config file.")
        return False

    result = {}
    for dictGroup, dictList in dicts:
        result[dictGroup] = {}
        for dictName, dic in dictList.iteritems():
            result[dictGroup][dictName] = Confilter(DICT_PATH + dic)

    return result

confilters = initConfilters()
if not confilters:
    log.critical("Confilters init failed.")
    exit(1)

# processor of request
def confilterApp(env, start_response):
    # get dict group from uri
    dictGroup = env['PATH_INFO'][1:]
    if not dictGroup:
        start_response('200 OK',[('Content-Type', 'text/plain')])
        return ["supported uri(%s)" % (','.join(confilters.keys()))]
    if not confilters.has_key(dictGroup):
        log.error("404 Not Found. uri(%s) not support" % (dictGroup))
        start_response('404 Not Found',[('Content-Type', 'text/plain')])
        return ["404 Not Found! uri(%s) not support" % (dictGroup)]
    # get post data from request body
    request_body_size = int(env.get('CONTENT_LENGTH',0))
    request_body = env['wsgi.input'].read(request_body_size)
    if not request_body:
        log.error("400 Bad Request. request_body should not empty")
        start_response('400 Bad Request',[('Content-Type', 'text/plain')])
        return ['Bad Request! request_body should not empty.']
    # get content from post data
    text = request_body
    content_type = env.get('CONTENT_TYPE', 'text/plain')
    #log.info("content_type:%r, find('urlencoded')=%r" % (content_type,content_type.find('urlencoded')))
    if 'urlencoded' in content_type:
        text = unquote(text)
    #start_response('201 OK',[('Content-Type', 'text/plain')])
    #return ["request_body(%s)" % (request_body), "\ntext(%s)" % (text), "\nenv(%r)" % (env), "\n"]

    hitCount = 0
    hitWords = {}
    for dictName, confilter in confilters[dictGroup].iteritems():
        result = confilter.findall(text)
        hitCount = hitCount + len(result)
        hitWords[dictName] = result
    hitWords['hit'] = hitCount

    # response
    response_body = json.dumps(hitWords)
    start_response('200 OK', [('Content-Type','application/json'),\
            ('Content-Length', str(len(response_body)))])
    log.info("200 OK.[hitWords]: %s" % hitWords)
    log.info("From text: %s" % text)
    return [response_body,]

# start the server
def runConfilter():
    host = config.get('host')
    port = int(config.get('port'))
    poolSize = int(config.get('poolSize'))

    p = pool.Pool(poolSize)
    log.info("Start server on %s:%s with pool size %s" % (host, port, poolSize))
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
    listener.bind((host, port))
    listener.listen(5)
    for _ in range(5):
        pid = os.fork()
        if pid == 0:
            wsgi.WSGIServer(listener, confilterApp, spawn = p).serve_forever()
            sys.exit(0)
        elif pid > 0:
            continue

#    wsgi.WSGIServer((host, port), confilterApp, spawn = p).serve_forever()
    wsgi.WSGIServer(listener, confilterApp, spawn = p).serve_forever()

if __name__ == "__main__":
    runConfilter()
