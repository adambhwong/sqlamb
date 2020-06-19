import logging, time, sqlite3, json, conf

LOG_CFG=conf.LOG_CFG
SQLITE_DATATYPE_MAP=conf.SQLITE_DATATYPE_MAP
LOG_CFG=conf.LOG_CFG
DEFAULT_EPOCH=conf.DEFAULT_EPOCH
EPOCH_MAP=conf.EPOCH_MAP

# configure logger
logging.basicConfig(level=LOG_CFG["level"],datefmt=LOG_CFG["datefmt"],format=LOG_CFG["format"])

class SqliteConn:
    def __init__(self, epoch=DEFAULT_EPOCH):
        self.epoch = epoch
        self.db = sqlite3.connect(':memory:')

    def __del__(self):
        try:
            self.db.close()
        except e:
            logging.error(e)
        logging.info("SQLite session closed.")

    def getAllTables(self):
        tables = []
        c = self.db.cursor()
        c.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%';")
        tableNames = list(map(lambda x: x[0], c.fetchall()))
        for n in tableNames:
            c.execute("PRAGMA table_info('{0}')".format(n))
            tables.append({"name": n, "struct": list(map(lambda x: [x[1],x[2],x[5]], c.fetchall()))})
        return tables

    def mapSqliteType(self, dataType):
        if dataType == int:
            return SQLITE_DATATYPE_MAP["int"]
        if dataType == float:
            return SQLITE_DATATYPE_MAP["float"]
        if dataType == str:
            return SQLITE_DATATYPE_MAP["str"]
        if dataType == unicode:
            return SQLITE_DATATYPE_MAP["unicode"]
        return None

    def getTsCols(self, tsData):
        cols = []
        if len(tsData) == 0:
            return cols
        if "tags" in tsData[0]:
            for key in sorted(tsData[0]["tags"].keys()):
                cols.append({"name": key, "dataType": "TEXT"})
        for i in range(len(tsData[0]["columns"])):
            colName = tsData[0]["columns"][i]
            try:
                colType = self.mapSqliteType(type(tsData[0]["values"][0][i]))
            except Exception as e:
                logging.debug("failed to get data type from 1st row, assume string type by default.")
                colType = self.mapSqliteType(str)
            cols.append({"name": colName, "dataType": colType})
        logging.debug('cols: \n{0}'.format(cols))
        return cols

    def getTsRows(self, tsData):
        rows = []
        for s in tsData:
            rowTemplate = []
            if "tags" in s:
                vals = [s["tags"][k] for k in sorted(s["tags"].keys())]
                for val in vals:
                    rowTemplate.append(val)
            for v in s["values"]:
                rows.append(tuple(rowTemplate + v))
        logging.debug('rows: \n{0}'.format(rows))
        return rows

    def importTsData(self, name, tsData):
        try:
            self.writeTable(name, self.getTsCols(tsData), self.getTsRows(tsData))
        except Exception as e:
            logging.error(e)

    def getTblCols(self, tblData):
        cols = []
        for i in range(len(tblData["cols"])):
            colName = tblData["cols"][i]
            try:
                colType = self.mapSqliteType(type(tblData["rows"][0][i]))
            except Exception as e:
                logging.debug("failed to get data type from 1st row, assume string type by default.")
                colType = self.mapSqliteType(str)
            cols.append({"name": colName, "dataType": colType})
        return cols

    def getTblRows(self, tblData):
        rows = []
        for r in tblData["rows"]:
            rows.append(tuple(r))
        return rows

    def importTblData(self, name, tblData):
        self.writeTable(name, self.getTblCols(tblData), self.getTblRows(tblData))

    def writeTable(self, name, cols, rows):
        c = self.db.cursor()
        schemaStr = ""
        for col in cols:
            schemaStr += "{0} {1}, ".format(col["name"], col["dataType"])
        if len(schemaStr) == 0:
            logging.error("colums not defined.")
            return False
        schemaStr = schemaStr[:-2]
        createTable = "CREATE TABLE {0} ({1});".format(name, schemaStr)
        c.execute(createTable)
        valTemplate = ""
        for i in range(len(cols)):
            valTemplate += "?,"
        valTemplate = valTemplate[:-1]
        insert = "INSERT INTO {0} VALUES ({1});".format(name, valTemplate)
        c.executemany(insert, rows)
        return True

    def query(self, name, tags, q, tableFormat=False):
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
        except sqlite3.Error as e:
            logging.error("failed to execute query.\n{0}".format(e))
            return None
        if tableFormat:
            return dataSet
        return SqliteConn.toTsData(name, tags, dataSet, self.epoch)

    @staticmethod
    def toTsData(name, tags, tblData, epoch=DEFAULT_EPOCH):
        nowTs = int(time.time() * EPOCH_MAP[epoch])
        series = []
        tagsIdxs = []
        valsIdxs = []
        timeIdx = -1
        for i in range(len(tblData["cols"])):
            if tblData["cols"][i] == "time":
                timeIdx = i
            elif tblData["cols"][i] in tags:
                tagsIdxs.append(i)
            else:
                valsIdxs.append(i)
        for r in tblData["rows"]:
            appended = False
            myTags = {}
            myCols = []
            myVals = []
            for i in tagsIdxs:
                myTags[tblData["cols"][i]] = r[i]
            if timeIdx < 0:
                myCols.append("time")
                myVals.append(nowTs)
            else:
                myCols.append(tblData["cols"][timeIdx])
                if r[timeIdx] is None:
                    myVals.append(nowTs)
                else:
                    myVals.append(r[timeIdx])
            for i in valsIdxs:
                myCols.append(tblData["cols"][i])
                myVals.append(r[i])
            if len(tagsIdxs) > 0:
                for s in series:
                    if s["tags"] == myTags:
                        s["values"].append(myVals)
                        appended = True
                if not appended:
                    series.append({
                        "name": name,
                        "tags": myTags,
                        "columns": myCols,
                        "values": [myVals]
                    })
            else:
                if len(series) == 0:
                    series.append({
                        "name": name,
                        "columns": myCols,
                        "values": [myVals]
                    })
                else:
                    series[0]["values"].append(myVals)
        return series

