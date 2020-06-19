import logging, mysql.connector, conf
import modules.credentialsClient as cm

LOG_CFG=conf.LOG_CFG
CRED_KEY=conf.CRED_KEY

# configure logger
logging.basicConfig(level=LOG_CFG["level"],datefmt=LOG_CFG["datefmt"],format=LOG_CFG["format"])

class MysqlConn:
    def __init__(self, host, port, db, credName, datasource):
        self.datasource = datasource
        self.credential = cm.CredentialInventory(CRED_KEY).get(credName)
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

