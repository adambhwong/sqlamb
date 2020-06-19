import re, json, falcon, logging, conf
import modules.influxProxy as ifpx
from requests.exceptions import HTTPError
from urllib import request, parse, error
from falcon.util.uri import parse_query_string

LOG_CFG = conf.LOG_CFG

# configure logger
logging.basicConfig(level=LOG_CFG["level"],datefmt=LOG_CFG["datefmt"],format=LOG_CFG["format"])

def utf8Decode(data):
    try:
       s = data.decode("utf-8")
    except:
       return data
    return s

class PingResource:

    def on_get(self, req, resp):
        result = ifpx.HttpForwarder("/ping", req).submit()
        logging.debug(type(result))
        resp.status = eval("falcon.HTTP_{0}".format(result.code))
        resp.set_headers(result.getheaders())
        resp.body = utf8Decode(result.read())

    def on_head(self, req, resp):
        result = ifpx.HttpForwarder("/ping", req, method="HEAD").submit()
        resp.status = eval("falcon.HTTP_{0}".format(result.code))
        resp.set_headers(result.getheaders())

class WriteResource:

    def on_post(self, req, resp):
        result = ifpx.HttpForwarder("/write", req, method="POST").submit()
        resp.status = eval("falcon.HTTP_{0}".format(result.code))
        resp.set_headers(result.getheaders())
        resp.body = utf8Decode(result.read())

class DebugPprofResource:

    def on_get(self, req, resp):
        result = ifpx.HttpForwarder("/debug/pprof", req).submit()
        resp.status = eval("falcon.HTTP_{0}".format(result.code))
        resp.set_headers(result.getheaders())
        resp.body = utf8Decode(result.read())

class DebugPprofParamResource:

    def on_get(self, req, resp, profile):
        result = ifpx.HttpForwarder("/debug/pprof/{0}".format(profile), req).submit()
        resp.status = eval("falcon.HTTP_{0}".format(result.code))
        resp.set_headers(result.getheaders())
        resp.body = utf8Decode(result.read())


class DebugRequestsResource:

    def on_get(self, req, resp):
        result = ifpx.HttpForwarder("/debug/requests", req).submit()
        resp.status = eval("falcon.HTTP_{0}".format(result.code))
        resp.set_headers(result.getheaders())
        resp.body = utf8Decode(result.read())

class DebugVarsResource:

    def on_get(self, req, resp):
        result = ifpx.HttpForwarder("/debug/vars", req).submit()
        resp.status = eval("falcon.HTTP_{0}".format(result.code))
        resp.set_headers(result.getheaders())
        resp.body = utf8Decode(result.read())

class QueryResource:

    def on_get(self, req, resp):
        query = req.get_param("q").strip()
        logging.debug("query: \n{0}".format(query))
        if re.match(r'^\{', query):
            try:
                jqh = ifpx.JsonQueryHandler(query, req.auth)
            except:
                resp.status = falcon.HTTP_400
                resp.body = json.dumps({"error": "JSON query parse error."})
                return True
            result = jqh.execute()
            if type(result) is error.HTTPError:
                resp.status = eval("falcon.HTTP_{0}".format(result.code))
                resp.body = utf8Decode(result.read())
            else:
                resp.status = falcon.HTTP_200
                resp.body = json.dumps(result)
        else:
            result = ifpx.HttpForwarder("/query", req).submit()
            resp.status = eval("falcon.HTTP_{0}".format(result.code))
            resp.body = utf8Decode(result.read())

    def on_post(self, req, resp):
        tableFormat = False
        epoch = 'ms'
        reqData = req.stream.read(req.content_length or 0)
        postParams = falcon.util.uri.parse_query_string(reqData.decode('ascii'), csv=False)
        if 'q' not in postParams:
            if 'q' not in req.params:
                logging.debug('request params missing "q", request dump: \n{0}'.format({"post_params": postParams, "req_params": req.params}))
                resp.status = falcon.HTTP_400
                resp.body = json.dumps({"error": 'POST params missing "q".'})
                return True
            else:
                query = re.sub(r'\\\.', '\\\\\.', req.params["q"].strip())
        else:
            query = re.sub(r'\\\.', '\\\\\.', postParams["q"].strip())
        query = re.sub(r'\\\(', '\\\\\(', query)
        query = re.sub(r'\\\)', '\\\\\)', query)
        query = re.sub(r'\\\+', '\\\\\+', query)
        logging.debug("query: \n{0}".format(query))
        if 'epoch' in req.params:
            epoch = req.params["epoch"]
        elif 'epoch' in postParams:
            epoch = postParams["epoch"]
        logging.debug("epoch: {0}".format(epoch))
        if 'table' in postParams:
            logging.debug("table parameter set: {0}".format(postParams["table"]))
            if postParams["table"] == "true":
                tableFormat = True
        if re.match(r'^\{', query):
            try:
                jqh = ifpx.JsonQueryHandler(query, req.auth, epoch, tableFormat)
                result = jqh.execute()
            except json.decoder.JSONDecodeError as e:
                resp.status = falcon.HTTP_400
                resp.body = json.dumps({"error": "{0}".format(e)})
                return True
            except HTTPError as e:
                resp.status = falcon.HTTP_400
                resp.body = json.dumps({"error": "{0}".format(e)})
                return True
            except:
                resp.status = falcon.HTTP_400
                resp.body = json.dumps({"error": "JSON query parse error."})
                return True
            if type(result) is error.HTTPError:
                resp.status = eval("falcon.HTTP_{0}".format(result.code))
                resp.body = utf8Decode(result.read())
            else:
                resp.status = falcon.HTTP_200
                resp.body = json.dumps(result)
        else:
            result = ifpx.HttpForwarder("/query", req, method="POST", reqData=reqData).submit()
            resp.status = eval("falcon.HTTP_{0}".format(result.code))
            resp.body = utf8Decode(result.read())
