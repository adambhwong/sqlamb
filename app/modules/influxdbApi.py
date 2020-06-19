import logging, re, conf
from influxdb import InfluxDBClient
import modules.credentialsClient as cm

LOG_CFG=conf.LOG_CFG
CRED_KEY=conf.CRED_KEY
LOG_CFG=conf.LOG_CFG
DEFAULT_EPOCH=conf.DEFAULT_EPOCH

# configure logger
logging.basicConfig(level=LOG_CFG["level"],datefmt=LOG_CFG["datefmt"],format=LOG_CFG["format"])

class InfluxdbConn:
    def __init__(self, host, port, dbname, credName, datasource, epoch=DEFAULT_EPOCH):
        self.datasource = datasource
        self.epoch = epoch
        self.credential = cm.CredentialInventory(CRED_KEY).get(credName)
        self.db = InfluxDBClient(host, port, self.credential["user"], self.credential["passwd"], dbname)
        logging.info("InfluxDB Datasource '{0}' session created.".format(self.datasource))

    def __del__(self):
        logging.info("Datasouce '{0}' session closed.".format(self.datasource))

    def query(self, q):
        #result = self.db.query(q, epoch="ms", method="POST")
        result = self.db.query(q, epoch=self.epoch, method=u'POST')
        logging.debug("result: \n".format(result))
        raw_json = result.raw
        if "series" not in raw_json:
            return []
        return raw_json["series"]

    def getTagValues(self, measurement, key):
        q = 'SHOW TAG VALUES FROM {0} WITH KEY="{1}"'.format(measurement, key)
        result = self.query(q)
        if len(result) == 0:
            return []
        tagValues = list(map(lambda x: x[1] , result[0]["values"]))
        logging.debug("tagValues: {0}".format(tagValues))
        return tagValues

    def getMeasurementFromQry(self, statement):
        qryWords = statement.split()
        for i in range(len(qryWords)):
            if re.match(r'^from$', qryWords[i], re.IGNORECASE):
                return qryWords[i+1]
        return None

