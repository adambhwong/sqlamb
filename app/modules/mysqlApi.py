import logging, mysql.connector, re, conf
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

class MysqlConn:
    def __init__(self, host, port, db, credName, datasource, epoch=DEFAULT_EPOCH, interval=None):
        self.datasource = datasource
        self.credential = cm.CredentialInventory(CRED_KEY).get(credName)
        self.epoch = epoch
        self.interval = None
        if interval is not None:
            try:
                self.interval = int(interval[:-1]) * INTERVAL_MAP[interval[-1]]
            except:
                logging.error("invalid interval: {0}".format(interval))
        self.db = mysql.connector.connect(
            host=host,
            port=port,
            user=self.credential["user"],
            password=self.credential["passwd"],
            db=db,
            auth_plugin = "mysql_native_password"
        )
        logging.info("MySQL Datasource '{0}' session created.".format(self.datasource))

    def __del__(self):
        try:
            self.db.close()
        except e:
            logging.error(e)
        logging.info("Datasource '{0}' session closed.".format(self.datasource))

    def query(self, q):
        dataSet = {
            "cols": [],
            "rows": []
        }
        q = self.qryTrans(q)
        try:
            mycursor = self.db.cursor()
            mycursor.execute(q)
            dataSet["cols"]=[x[0] for x in mycursor.description]
            myresult = mycursor.fetchall()
            for row in myresult:
                dataSet["rows"].append(row)
        except mysql.connector.Error as e:
            logging.error("failed to execute query.\n{0}".format(e))
            return None
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

