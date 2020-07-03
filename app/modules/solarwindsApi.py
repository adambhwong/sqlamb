import logging, orionsdk, re, conf
import modules.credentialsClient as cm
from datetime import datetime, timedelta

LOG_CFG=conf.LOG_CFG
CRED_KEY=conf.CRED_KEY
DEFAULT_EPOCH=conf.DEFAULT_EPOCH
EPOCH_MAP = {
    'h': 1/3600.0,
    'm': 1/60.0,
    's': 1.0,
    'ms': 1000.0,
    'u': 1000000.0,
    'ns': 1000000000.0
}
INTERVAL_MAP = {
    'h': 3600,
    'm': 60,
    's': 1
}

# configure logger
logging.basicConfig(level=LOG_CFG["level"],datefmt=LOG_CFG["datefmt"],format=LOG_CFG["format"])

class SolarwindsConn:
    def __init__(self, host, credName, datasource, epoch=DEFAULT_EPOCH, interval=None):
        self.datasource = datasource
        self.credential = cm.CredentialInventory(CRED_KEY).get(credName)
        self.epoch = epoch
        self.interval = None
        if interval is not None:
            try:
                self.interval = int(interval[:-1]) * INTERVAL_MAP[interval[-1]]
            except:
                logging.error("invalid interval: {0}".format(interval))
        self.db = orionsdk.SwisClient(
            host,
            self.credential["user"],
            self.credential["passwd"]
        )
        logging.info("Solarwinds Datasource '{0}' session created.".format(self.datasource))

    def __del__(self):
        logging.info("Datasource '{0}' session closed.".format(self.datasource))

    def query(self, q):
        dataSet = {
            "cols": [],
            "rows": []
        }
        tmColIdx = -1
        q = self.qryTrans(q)
        resp = self.db.query(q)
        if "results" in resp:
            for r in resp["results"]:
                if len(dataSet["cols"]) == 0:
                    dataSet["cols"] = list(r.keys())
                    if 'time' in dataSet["cols"]:
                        tmColIdx = dataSet["cols"].index('time')
                dataSet["rows"].append(list(r.values()))
                if tmColIdx >= 0 :
                    lastIdx = len(dataSet["rows"]) - 1
                    #logging.debug("time = {0}".format(dataSet["rows"][lastIdx][tmColIdx]))
                    #dataSet["rows"][lastIdx][tmColIdx] = re.sub(r'\.[0-9]+', 'Z', dataSet["rows"][lastIdx][tmColIdx])
                    try:
                        dataSet["rows"][lastIdx][tmColIdx] = int(datetime.fromisoformat(dataSet["rows"][lastIdx][tmColIdx][:-1]).strftime("%s"))*1000
                    except Exception as e:
                        #logging.warn(e)
                        tmpDtStr = re.search(r'[0-9]+\-[0-9]+\-[0-9]+[A-Z][0-9]+:[0-9]+:[0-9]+', dataSet["rows"][lastIdx][tmColIdx]).group(0)
                        dataSet["rows"][lastIdx][tmColIdx] = int(datetime.fromisoformat(tmpDtStr).strftime("%s"))*1000
        return dataSet

    def convertTimestamps(self, s):
        ptn = re.compile(r'[0-9]+{0}'.format(self.epoch))
        ml = list(re.finditer(ptn, s))
        while ml:
            m = ml.pop()
            logging.debug("found: {0}".format(m.group(0)))
            tmstamp = int(m.group(0)[:-2])/EPOCH_MAP[self.epoch]
            if self.interval is not None and re.search(r'>=* *$', s[:m.start(0)]):
                tmstamp -= self.interval
            s = s[:m.start(0)] + "'" + datetime.fromtimestamp(tmstamp).strftime('%Y-%m-%d %H:%M:%S') + "'" + s[m.end(0):]
        return s

    def convertTimeDelta(self, s):
        unitMap = {
            'd': 'days',
            'h': 'hours',
            'm': 'minutes',
            's': 'seconds'
        }
        ptn = re.compile(r'now.*[0-9]+[dhms]')
        ml = list(re.finditer(ptn, s))
        while ml:
            m = ml.pop()
            logging.debug("found: {0}".format(m.group(0)))
            buff = m.group(0)
            m2 = re.search(r'[0-9]+[dhms]', buff)
            tdelta = m2.group(0)
            deltaUnit = unitMap[tdelta[-1:]]
            code = buff[:m2.start(0)] + 'timedelta({0}={1})'.format(deltaUnit, tdelta[:-1])
            if self.interval is not None and re.search(r'>=* *$', s[:m.start(0)]):
                code = code + '-timedelta(seconds={0})'.format(self.interval)
            code = "(" + code.replace("now()", "datetime.now()") + ").strftime('%Y-%m-%d %H:%M:%S')"
            logging.debug("code: {0}".format(code))
            s = s[:m.start(0)] + "'" + eval(code) + "'" + s[m.end(0):]
        return s
        
    def qryTrans(self, q):
        ptn = re.compile(r'_TMFILTER_\(+.*?[^\\]\)_')
        ml = list(re.finditer(ptn, q))
        while ml:
            m = ml.pop()
            logging.debug("found: {0}".format(m.group(0)))
            buff = m.group(0).replace('_TMFILTER_(','').replace(')_','')
            (colName, buff) = buff.split(',')
            buff = self.convertTimestamps(buff)
            buff = self.convertTimeDelta(buff)
            buff = buff.replace("time", colName)
            q = q[:m.start(0)] + buff +q[m.end(0):]
            logging.debug("statement: {0}".format(q))
        return q

