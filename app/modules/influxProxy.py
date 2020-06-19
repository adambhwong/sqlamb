import logging, re, json, copy, conf
from urllib import request, error
from modules.influxdbApi import InfluxdbConn
from modules.mysqlApi import MysqlConn
from modules.solarwindsApi import SolarwindsConn
from modules.sqliteApi import SqliteConn
import modules.credentialsClient as cm
import modules.sql2json as s2j

LOG_CFG=conf.LOG_CFG
DATASOURCES=conf.DATASOURCES
INFLUXQL_FW_TARGET=conf.INFLUXQL_FW_TARGET
DEFAULT_EPOCH=conf.DEFAULT_EPOCH

# configure logger
logging.basicConfig(level=LOG_CFG["level"],datefmt=LOG_CFG["datefmt"],format=LOG_CFG["format"])

class GenericQueryResult:
    def __init__(self, alias, dsName, statement, epoch=DEFAULT_EPOCH):
        self.dbConn = None
        self.errMsg = None
        self.resultSet = None
        self.alias = alias
        self.dsName = dsName
        self.statement = statement
        self.epoch = epoch
        if self.dsName not in DATASOURCES:
            logging.error("Data source '{0}' not defined.".format(self.dsName))
            return None
        self.ds = DATASOURCES[self.dsName]
        self.resultType = self.ds["dbtype"]
        #logging.debug("alias={0}, dsName={1}, epoch={2}".format(alias, dsName, epoch))
        self.query()
    
    @staticmethod
    def qryTrans(qryStatement):
        q = qryStatement
        ptn = re.compile(r' [Ii][Nn] _\(+.*?[^\\]\)_')
        ml = list(re.finditer(ptn, q))
        while ml:
            m = ml.pop()
            logging.debug("found: {0}".format(m.group(0)))
            buff = re.sub(r'\)_$', "')", m.group(0).replace("'", "''").replace('\.', '.').replace('\+', '+').replace("|","','").replace("_(","('",1))
            buff = buff.replace("('(", "('").replace(")')", "')")
            logging.debug("buff: {0}".format(buff))
            q = q[:m.start(0)] + buff +q[m.end(0):]
            logging.debug("statement: {0}".format(q))
        return q

    def query(self):
        ds = self.ds
        if ds["dbtype"] == "influxdb":
            self.dbConn = InfluxdbConn(ds["host"], ds["port"], ds["db"], ds["credential"], self.dsName, self.epoch)
        elif ds["dbtype"] == "mysql":
            self.dbConn = MysqlConn(ds["host"], ds["port"], ds["db"], ds["credential"], self.dsName)
        elif ds["dbtype"] == "solarwinds":
            self.dbConn = SolarwindsConn(ds["host"], ds["credential"], self.dsName)
        if ds["dbtype"] in ["mysql", "solarwinds"]:
            self.statement = GenericQueryResult.qryTrans(self.statement)
        if self.dbConn is not None:
            self.resultSet = self.dbConn.query(self.statement)
        logging.debug("{0} query reslt: \n{1}".format(self.dsName, json.dumps(self.resultSet, indent=4)))
        
class InfluxdbHttpApi:
    def __init__(self, url=INFLUXQL_FW_TARGET):
        self.url = url

    def forward(self, path, orgReq, method=None, reqData=None):
        if method in [ 'GET', 'HEAD' ]:
            bytedata = None
        else:
            if reqData is None:
                bytedata = orgReq.stream.read(orgReq.content_length or 0)
            else:
                bytedata = reqData
        req = request.Request(self.url + path, data=bytedata, method=method)
        if orgReq.auth is not None:
            req.add_header('Authorization', orgReq.auth)
        if bytedata is not None:
            req.add_header('Content-Type', orgReq.content_type)
            req.add_header('Content-Length', orgReq.content_length)
        logging.debug("req = {0}".format(req))
        try:
            resp = request.urlopen(req)
        except error.HTTPError as e:
            logging.error("HTTP error: Code={0}, Reason='{1}'".format(e.code, e.reason))
            return e
        logging.debug("code = {0}".format(resp.code))
        return resp

class HttpForwarder:
    def __init__(self, path, req, method="GET", reqData=None):
        self.path = path
        self.req = req
        self.method = method
        self.reqData = reqData

    def submit(self):
        resp = InfluxdbHttpApi().forward("{0}?{1}".format(self.path, self.req.query_string), self.req, method=self.method, reqData=self.reqData)
        logging.debug("resp = {0}".format(resp))
        return resp

class JsonQueryHandler:
    def __init__(self, query, auth=None, epoch=DEFAULT_EPOCH, tableFormat=False):
        self.auth = auth
        self.epoch = epoch
        self.tableFormat = tableFormat
        self.jsonQuery = json.loads(query)
        logging.debug("jsonQuery: \n{0}".format(json.dumps(self.jsonQuery, indent=4)))

    def execute(self):
        genericQryRsts = {}
        combinedQryRsts = []
        finnalSets = []
        result = { "results": [{ "statement_id": 0, "series": [] }] }
        sqliteConn = SqliteConn(epoch=self.epoch)
        for q in self.jsonQuery["queries"]:
            genericQryRsts[q["alias"]] = GenericQueryResult(q["alias"], q["datasource"], q["statement"])
            if "joint" in self.jsonQuery:
                if genericQryRsts[q["alias"]].resultType in ["influxdb"]:
                    sqliteConn.importTsData(q["alias"], genericQryRsts[q["alias"]].resultSet)
                elif genericQryRsts[q["alias"]].resultType in ["mysql", "solarwinds"]:
                    sqliteConn.importTblData(q["alias"], genericQryRsts[q["alias"]].resultSet)
        logging.debug("SQLite tables: \n{0}".format(json.dumps(sqliteConn.getAllTables(), indent=4)))
        if "joint" in self.jsonQuery:
            try:
                self.jsonQuery["joint"]["statement"] = GenericQueryResult.qryTrans(self.jsonQuery["joint"]["statement"])
                self.jsonQuery["joint"]["statement"] = s2j.Sql2Json(self.jsonQuery["joint"]["statement"]).toTsQry()
                logging.debug('final sql: {0}'.format(self.jsonQuery["joint"]["statement"]))
            except Exception as e:
                logging.error(e)
            if self.tableFormat:
                result.pop("results")
                result["dataFrame"] = sqliteConn.query(
                    self.jsonQuery["joint"]["alias"], 
                    self.jsonQuery["joint"]["tags"], 
                    self.jsonQuery["joint"]["statement"],
                    tableFormat=self.tableFormat 
                )
            else:
                result["results"][0]["series"] = sqliteConn.query(
                    self.jsonQuery["joint"]["alias"], 
                    self.jsonQuery["joint"]["tags"], 
                    self.jsonQuery["joint"]["statement"] 
                )
        else:
            if len(genericQryRsts) > 1:
                logging.error("Mutiple query result sets({0}) returned.".format(len(genericQryRsts)))
            else:
                r = next(iter(genericQryRsts.values()))
                if r.ds["dbtype"] in ["mysql", "solarwinds"]:
                    result["results"][0]["series"] = SqliteConn.toTsData("anonymous", [], r.resultSet, epoch=self.epoch)
                else:
                    result["results"][0]["series"] = r.resultSet
        return result
