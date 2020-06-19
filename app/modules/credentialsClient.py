from urllib import request, parse, error
import json, logging, conf

CREDMGR_URL = conf.CREDMGR_URL
CRED_KEY = conf.CRED_KEY
LOG_CFG = conf.LOG_CFG

# configure logger
logging.basicConfig(level=LOG_CFG["level"],datefmt=LOG_CFG["datefmt"],format=LOG_CFG["format"])

class CredentialInventory:
    def __init__(self, key=CRED_KEY, mgrUrl=CREDMGR_URL):
        self.url = mgrUrl
        self.key = key

    def apiInteractor(self, path, data=None, method=None, returnHttpCode=False):
        if data is None:
            bytedata = None
        else:
            if method == 'GET':
                bytedata = parse.urlencode(data)
            else:
                bytedata = json.dumps(data).encode('utf-8')
        req = request.Request(self.url + path, data=bytedata, method=method)
        req.add_header('Authorization', 'Bearer {0}'.format(self.key))
        if req.get_method() in ['POST', 'PATCH']:
            req.add_header('Content-Type', 'application/json; charset=utf-8')
            req.add_header('Content-Length', len(bytedata))
        try:
            resp = request.urlopen(req)
        except error.HTTPError as e:
            errMsg = json.loads(e.read().decode('utf-8'))['error']
            logging.error("HTTP error: Code={0}, Reason='{1}', Error='{2}'".format(e.code, e.reason, errMsg))
            if returnHttpCode:
                return e.code
            return None
        if returnHttpCode:
            return resp.code
        try:
            json_obj = json.loads(resp.read().decode('utf-8'))
        except json.decoder.JSONDecodeError:
            logging.error("JSON load error")
            return None
        return json_obj

    def get(self, credName):
        credential = self.apiInteractor("/creds/{0}".format(credName))
        return credential
