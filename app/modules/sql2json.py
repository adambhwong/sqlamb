import logging, re, json, copy, time, conf
import sqlparse
from sqlparse.tokens import Keyword, DML, DDL, CTE, Punctuation, Whitespace
from datetime import datetime, timedelta

LOG_CFG=conf.LOG_CFG
SELECT_TEMPLATE = {
    "with": None,
    "select": {
        "distinct": False,
        "columns": []
    },
    "from": [],
    "where": [],
    "orderBy": [],
    "limit": None,
    "offset": None,
    "groupBy": [],
    "having": [],
    "setOperation": None
}
FROM_PART_TEMPLATE = {
    "joinType": None,
    "table": None,
    "subQuery": None,
    "alias": None,
    "on": []
}
OPEN_BRACKETS = ['(', '{', '[']
CLOSE_BRACKETS = [')', '}', ']']
QUOTES = ['"', "'", '`']
EXTENTED_FUNCTION_PATTERNS = {
    "in": re.compile(r'_IN_\(+.*?[^\\]\)_'),
    "timeFilter": re.compile(r'_TMFILTER_\(+.*?[^\\]\)_'),
    "interval": re.compile(r'_INTERVAL_\(+.*?[^\\]\)_')
}
TIME_UNIT_MAP = {
    'd': 'days',
    'h': 'hours',
    'm': 'minutes',
    's': 'seconds'
}
SQL_GROUP_FUNCTIONS = ['COUNT', 'MAX', 'MIN', 'AVG', 'SUM']
DEFAULT_EPOCH=conf.DEFAULT_EPOCH
EPOCH_MAP=conf.EPOCH_MAP

# configure logger
logging.basicConfig(level=LOG_CFG["level"],datefmt=LOG_CFG["datefmt"],format=LOG_CFG["format"])

class Sql2Json:
    def __init__(self, sql=None, epoch=DEFAULT_EPOCH):
        self.tmFilter = None
        self.epoch = epoch
        if sql:
            logging.debug('sql={0}'.format(sql))
        self.sql = sql
        if sql is None:
            self.tokens = []
            self.sqlJson = None
            self.sqlJsonPi = None
        else:
            self.tokens = self.dirtyFix(sqlparse.parse(sql)[0].tokens)
            for i,t in enumerate(self.tokens):
                logging.debug('tokens[{0}]: ttype={1}, value={2}'.format(i, t.ttype, t.value))
            self.sqlJson = self.toJson()

    def __str__(self):
        return self.json2str(self.sqlJson)

    def json2str(self, j):
        s = ""
        if j["with"] is not None:
            s += "WITH "
            if j["with"]["recursive"]:
                s += "RECURSIVE "
            for i,cte in enumerate(j["with"]["cteList"]):
                if i > 0:
                    s += ", "
                s +=  "{0} AS ({1}) ".format(cte["name"], cte["query"])
        s += "SELECT "
        if j["select"]["distinct"]:
            s += "DISTINCT "
        s += "{0} ".format(", ".join(j["select"]["columns"]))
        if len(j["from"]) > 0:
            s += "FROM "
            for i,item in enumerate(j["from"]):
                if i > 0:
                    if item["joinType"] is not None:
                        s += "{0} ".format(item["joinType"])
                    else:
                        s += ", "
                if item["table"] is not None:
                    s += "{0} ".format(item["table"])
                if item["subQuery"] is not None:
                    s += "({0}) ".format(self.json2str(item["subQuery"]))
                if item["alias"] is not None:
                    s += "{0} ".format(item["alias"])
                if len(item["on"]) > 0:
                    s += "ON "
                    for cond in item["on"]:
                        if cond["opt"] is not None:
                            s += "{0} ".format(cond["opt"])
                        if cond["val"] is not None:
                            s += "{0} ".format(cond["val"])
        if len(j["where"]) > 0:
            s += "WHERE "
            for ft in j["where"]:
                if ft["opt"] is not None:
                    s += "{0} ".format(ft["opt"])
                if ft["val"] is not None:
                    s += "{0} ".format(ft["val"])
        if len(j["groupBy"]) > 0:
            s += "GROUP BY {0} ".format(", ".join(j["groupBy"]))
        if len(j["having"]) > 0:
            s += "HAVING "
            for ft in j["having"]:
                if ft["opt"] is not None:
                    s += "{0} ".format(ft["opt"])
                if ft["val"] is not None:
                    s += "{0} ".format(ft["val"])
        if len(j["orderBy"]) > 0:
            s += "ORDER BY {0} ".format(", ".join(j["orderBy"]))
        if j["limit"] is not None:
            s += "LIMIT {0} ".format(j["limit"])
        if j["offset"] is not None:
            s += "OFFSET {0} ".format(j["offset"])
        if j["setOperation"] is not None:
            s += "{0} ".format(j["setOperation"]["operator"])
            if j["setOperation"]["all"]:
                s += "ALL "
            s += self.json2str(j["setOperation"]["stmt"])
        return s
    
    def dirtyFix(self, tokens):
        i = 0
        while i < len(tokens):
            t = tokens[i]
            #logging.debug("type: {0}; value: {1}".format(t.ttype, t.value))
            if t.ttype is None and re.match(r'^WHERE ', t.value, re.IGNORECASE):
                tokens[i] = sqlparse.sql.Token(ttype=None, value=re.sub(r'^WHERE ', '', t.value, flags=re.IGNORECASE))
                tokens.insert(i, sqlparse.sql.Token(ttype=Whitespace, value=' '))
                tokens.insert(i, sqlparse.sql.Token(ttype=Keyword, value='WHERE'))
            if t.ttype is Keyword and t.value == 'key':
                tokens[i] = sqlparse.sql.Token(ttype=None, value='key')
            if t.ttype is Keyword and t.value == 'time':
                lnBuff = ""
                while i < len(tokens) and tokens[i].ttype is not None:
                    lnBuff += tokens.pop(i).value
                    #logging.debug("{0}/{1}: {2}".format(i, len(tokens), lnBuff))
                if i >= len(tokens):
                    tokens.append(sqlparse.sql.Token(ttype=None, value=lnBuff))
                else:
                    tokens[i] = sqlparse.sql.Token(ttype=None, value=lnBuff+tokens[i].value)
            i += 1
        return tokens

    def probeNextType(self):
        for t in self.tokens:
            if t.ttype == None and re.match(r'^WHERE ', t.value.strip(), re.IGNORECASE):
                return Keyword
            if t.ttype in [Keyword, DML, DDL, CTE, None, Punctuation]:
                return t.ttype
        return None
        
    def probeNextKey(self):
        for t in self.tokens:
            if t.ttype in [Keyword, DML, DDL, CTE]:
                return t.value.strip().upper()
        return None
        
    def popNextKey(self):
        while len(self.tokens) > 0:
            t = self.tokens.pop(0)
            if t.ttype in [Keyword, DML, DDL, CTE]:
                return t.value.strip().upper()
        return None
        
    def popNextVal(self):
        while len(self.tokens) > 0:
            t = self.tokens.pop(0)
            if t.ttype is None:
                return t.value.replace('\n', '').strip()
        return None

    def popListByKeys(self, keys=[]):
        myList = []
        while self.probeNextKey() in keys:
            myList.append({"opt": self.popNextKey(), "val": self.popNextVal()})
        return myList
    
    def popListVal(self):
        myList = []
        while self.probeNextType() not in [Keyword, DML, DDL, CTE]:
            v = self.popNextVal();
            #logging.debug(json.dumps(v))
            if v is None:
                break
            #if re.match(r'^\(', v):
            #    myList.append(v)
            #    logging.debug("appended '{0}'".format(v))
            else:
                lnBuff = ""
                for item in v.split(','):
                    if lnBuff == "":
                        lnBuff = item.strip()
                    else:
                        lnBuff += ",{0}".format(item)
                    openCount = 0
                    openQuotes = []
                    for c in list(lnBuff):
                        if c in OPEN_BRACKETS:
                            openCount += 1
                        elif c in CLOSE_BRACKETS:
                            openCount -= 1
                        elif c in QUOTES:
                            if c in openQuotes:
                                openQuotes.pop(openQuotes.index(c))
                            else:
                                openQuotes.append(c)
                    #logging.debug('lnBuff="{0}"; openCount={1}'.format(lnBuff, openCount))
                    if (openCount == 0) and (len(openQuotes) == 0):
                        myList.append(lnBuff)
                        lnBuff = ""
        #logging.debug(json.dumps(myList))
        return myList

    def popAllToStr(self):
        strBuff = ""
        while len(self.tokens) > 0:
            t = self.tokens.pop(0)
            strBuff += t.value
        return strBuff
        
    def clearStr(self, s):
        return re.sub(r'\)$', '', re.sub(r'^\(', '', s.strip())).strip()

    def popWithPart(self):
        recursive = False
        cteList = []
        if self.probeNextType() is Keyword:
            if self.popNextKey() == "RECURSIVE":
                recursive = True
        myList = self.popListVal()
        for item in myList:
            splitted = item.split()
            cteList.append({
                "name": splitted.pop(0),
                "query": self.clearStr(" ".join(splitted[1:]))
            })
        return {"recursive": recursive, "cteList": cteList}

    def popSelectPart(self):
        distinct = False
        if self.probeNextType() is Keyword:
            if self.popNextKey() == "DISTINCT":
                distinct = True
        cols = self.popListVal()
        return {"distinct": distinct, "columns": cols}

    def extractTblAlias(self, s):
        returnVal = {
            "table": None,
            "subQuery": None,
            "alias": None
        }
        #logging.debug("s='{0}'".format(s))
        if re.match(r'^\(.*\)$', s):
            if re.match(r'^WITH ', self.clearStr(s), re.IGNORECASE):
                returnVal["subQuery"] = self.clearStr(s)
            else:
                returnVal["subQuery"] = Sql2Json(self.clearStr(s)).sqlJson
                #returnVal["subQuery"] = self.clearStr(s)
            return returnVal
        listBuff = s.split()
        if len(listBuff) == 1:
            returnVal["table"] = s.strip()
            return returnVal
        elif len(listBuff) > 1:
            alias = listBuff.pop().strip()
            if not re.match(r'^[_\W]+$', alias):
                returnVal["alias"] = alias
        if len(listBuff) == 1:
            returnVal["table"] = s.strip()
            return returnVal
        elif len(listBuff) > 1:
            if re.match(r'^WITH$', self.clearStr(listBuff[0]), re.IGNORECASE):
                returnVal["subQuery"] = self.clearStr(' '.join(listBuff))
            else:
                returnVal["subQuery"] = Sql2Json(self.clearStr(' '.join(listBuff))).sqlJson
                #returnVal["subQuery"] = self.clearStr(' '.join(listBuff))
            return returnVal
        return None

    def popFromPart(self):
        myList = []
        fp = copy.deepcopy(FROM_PART_TEMPLATE)
        listValBuff = self.popListVal()
        for lvb in listValBuff:
            v = self.extractTblAlias(lvb)
            if v is not None:
                fp["table"] = v["table"]
                fp["subQuery"] = v["subQuery"]
                fp["alias"] = v["alias"]
                myList.append(fp)
                fp = copy.deepcopy(FROM_PART_TEMPLATE)
            while self.probeNextKey() is not None and self.probeNextKey().find('JOIN') > -1:
                fp["joinType"] = self.popNextKey()
                valBuff = self.popNextVal()
                v = self.extractTblAlias(valBuff)
                if v is not None:
                    fp["table"] = v["table"]
                    fp["subQuery"] = v["subQuery"]
                    fp["alias"] = v["alias"]
                if self.probeNextKey() == 'ON':
                    #logging.debug('length={0}'.format(len(self.tokens)))
                    fp["on"].append({"opt": None, "val": self.popNextVal()})
                    fp["on"].extend(self.popListByKeys(['AND']))
                myList.append(fp)
                fp = copy.deepcopy(FROM_PART_TEMPLATE)
        return myList

    def popSetOpPart(self):
        setAll = False
        if self.probeNextType() is Keyword:
            if self.popNextKey() == "ALL":
                setAll = True
        stmt = Sql2Json(self.popAllToStr()).sqlJson
        return {"all": setAll, "stmt": stmt}
        
    def popWherePart(self):
        myList = []
        myList.append({"opt": None, "val": self.popNextVal()})
        myList.extend(self.popListByKeys(['AND', 'OR']))
        return myList
        
    def popHavingPart(self):
        myList = []
        myList.append({"opt": None, "val": self.popNextVal()})
        myList.extend(self.popListByKeys(['AND', 'OR']))
        return myList
        
    def convertTimestamps(self, s):
        startTs = None
        endTs = int(time.time()*EPOCH_MAP[self.epoch])
        updateTmFilter = False
        ptn = re.compile(r'[0-9]+ms')
        ml = list(re.finditer(ptn, s))
        if len(ml) > 0:
            updateTmFilter = True
        while ml:
            m = ml.pop()
            logging.debug("found: {0}".format(m.group(0)))
            dt = datetime.fromtimestamp(int(m.group(0)[:-2])/EPOCH_MAP[self.epoch])
            ts = int(dt.strftime('%s'))*tsUnit
            if re.match(r'.*time *>=* *$', s[:m.start(0)]):
                startTs = ts
                logging.debug("startTs = {0}".format(startTs))
            elif re.match(r'.*time *<=* *$', s[:m.start(0)]):
                endTs = ts
                logging.debug("endTs = {0}".format(endTs))
            s = s[:m.start(0)] + str(ts) + s[m.end(0):]
        if updateTmFilter:
            self.tmFilter = {
                "start": startTs,
                "end": endTs
            }
        return s.strip()

    def convertTimeDelta(self, s):
        tsUnit = EPOCH_MAP[self.epoch]
        unitMap = TIME_UNIT_MAP
        startTs = None
        endTs = int(time.time()*EPOCH_MAP[self.epoch])
        updateTmFilter = False
        ptn = re.compile(r'now.*[0-9]+[dhms]')
        ml = list(re.finditer(ptn, s))
        if len(ml) > 0:
            updateTmFilter = True
        while ml:
            m = ml.pop()
            logging.debug("found: {0}".format(m.group(0)))
            buff = m.group(0)
            m2 = re.search(r'[0-9]+[dhms]', buff)
            tdelta = m2.group(0)
            deltaUnit = unitMap[tdelta[-1:]]
            code = buff[:m2.start(0)] + 'timedelta({0}={1})'.format(deltaUnit, tdelta[:-1])
            #code = "(" + code.replace("now()", "datetime.now()") + ").strftime('%Y-%m-%d %H:%M:%S')"
            code = code.replace("now()", "datetime.now()")
            logging.debug("code: {0}".format(code))
            dt = eval(code)
            ts = int(dt.strftime('%s'))*EPOCH_MAP[self.epoch]
            if re.match(r'.*time *>=* *$', s[:m.start(0)]):
                startTs = ts
                logging.debug("startTs = {0}".format(startTs))
            elif re.match(r'.*time *<=* *$', s[:m.start(0)]):
                endTs = ts
                logging.debug("endTs = {0}".format(endTs))
            #s = s[:m.start(0)] + "'" + dt.strftime('%Y-%m-%d %H:%M:%S') + "'" + s[m.end(0):]
            s = s[:m.start(0)] + str(ts) + s[m.end(0):]
        if updateTmFilter:
            self.tmFilter = {
                "start": startTs,
                "end": endTs
            }
        return s.strip()

    def removeWhereTmFilter(self):
        tmFilterIdx = []
        for i,f in enumerate(self.sqlJson["where"]):
            if re.match(r'^(.*\.)*time *[><]=*', f["val"]):
                tmFilterIdx.append(i)
        c = len(tmFilterIdx)
        while tmFilterIdx:
            self.sqlJson["where"].pop(tmFilterIdx.pop())
        return c

    def getTimeCol(self, sqlJson):
        for c in sqlJson["select"]["columns"]:
            if c.split()[-1].split('.')[-1] == 'time':
                return c
        return None

    def getAggregatedCols(self, sqlJson):
        aggCols = []
        for c in sqlJson["select"]["columns"]:
            if c.find('(') > -1:
                if c.split('(')[0].upper() in SQL_GROUP_FUNCTIONS:
                    m = re.search(r'\(.*?\)', c)
                    cname = m.group(0).replace('(','').replace(')','')
                    cAlias = None
                    if re.match(r'.* as .*', c, re.IGNORECASE):
                        cAlias = c.split()[-1]
                    aggCols.append({
                        'name': cname,
                        'function': c.split('(')[0].upper(),
                        'alias': cAlias,
                        'pre': c[:m.start(0)],
                        'post': c[m.end(0):]
                    })
        return aggCols

    def getGroupCols(self, sqlJson):
        grpCols = []
        for c in sqlJson["select"]["columns"]:
            if c.find('(') == -1:
                 cname = c.split()[0]
                 if cname.split('.')[-1] != 'time':
                     grpCols.append(c)
            else:
                 if c.split('(')[0].upper() not in SQL_GROUP_FUNCTIONS:
                     grpCols.append(c)
        tmpsj = Sql2Json()
        tmpsj.sqlJson = sqlJson
        #logging.debug("sql = {0}".format(tmpsj))
        #logging.debug("group cols = {0}".format(json.dumps(grpCols)))
        return grpCols
         

    def timeDeltaToSec(self, tdelta):
        if tdelta[-1:] == 's':
            return int(tdelta[:-1])
        elif tdelta[-1:] == 'm':
            return int(tdelta[:-1])*60
        elif tdelta[-1:] == 'h':
            return int(tdelta[:-1])*3600
        elif tdelta[-1:] == 'd':
            return int(tdelta[:-1])*86400
        return None
        
    def genTimeSeriesSubquery(self, sqlJson, interval, groupCols):
        subq = copy.deepcopy(SELECT_TEMPLATE)
        limit = int((self.tmFilter["end"] - self.tmFilter["start"])/interval) + 1
        startTs = self.tmFilter["start"] + (interval - (self.tmFilter["start"] % interval))
        seriesAlias = "series_{0}".format(int(startTs))
        subq["with"] = {
            "recursive": True,
            "cteList": [{
                "name": "cnt(x)",
                "query": "SELECT 1 UNION ALL SELECT x+1 FROM cnt LIMIT {0}".format(limit)
            }]
        }
        subq["select"]["columns"].append("({0} + (cnt.x-1)*{1}) AS time".format(startTs, interval))
        for c in groupCols:
            subq["select"]["columns"].append("{0}.{1}".format(seriesAlias, c.split('.')[-1]))
        fp1 = copy.deepcopy(FROM_PART_TEMPLATE)
        fp1["table"] = 'cnt'
        subq["from"].append(fp1)
        subq1 = copy.deepcopy(SELECT_TEMPLATE)
        subq1["select"] = {
            "distinct": True,
            "columns": groupCols.copy()
        }
        subq1["from"] = copy.deepcopy(sqlJson["from"])
        fp2 = copy.deepcopy(FROM_PART_TEMPLATE)
        fp2["joinType"] = "LEFT OUTER JOIN"
        fp2["alias"] = seriesAlias
        fp2["subQuery"] = subq1
        subq["from"].append(fp2)
        return subq

    def genRawDataSubquery(self, sqlJson):
        subq = copy.deepcopy(SELECT_TEMPLATE)
        subq["select"]["columns"].append(self.getTimeCol(sqlJson))
        subq["select"]["columns"].extend(self.getGroupCols(sqlJson))
        for c in self.getAggregatedCols(sqlJson):
            subq["select"]["columns"].append("{0} AS {1}".format(c["name"], c["name"].replace('.', '_')))
        subq["from"] = copy.deepcopy(sqlJson["from"])
        subq["where"] = copy.deepcopy(sqlJson["where"])
        return subq

    def genTimeSeriesQuery(self, sqlJson, interval, grpCols, fill=None):
        q = copy.deepcopy(SELECT_TEMPLATE)
        startTs = self.tmFilter["start"] + (interval - (self.tmFilter["start"] % interval))
        tsAlias = "timeseries_{0}".format(int(startTs))
        rdAlias = "rawdata_{0}".format(int(startTs))
        if fill is None:
            fill = 'NULL'
        q["select"]["columns"].append("{0}.time AS time".format(tsAlias))
        for c in self.getGroupCols(sqlJson):
            q["select"]["columns"].append("{0}.{1}".format(tsAlias, re.sub(r'^.*?\.', '', c)))
        for c in self.getAggregatedCols(sqlJson):
            #q["select"]["columns"].append("{0}(IFNULL({1}.{2}, {4})) AS {3}".format(c["function"], rdAlias, c["name"].replace('.', '_'), c["alias"], fill))
            q["select"]["columns"].append("{0}(IFNULL({1}.{2}, {3})){4}".format(c["pre"], rdAlias, c["name"].replace('.', '_'), fill, c["post"]))
        fp1 = copy.deepcopy(FROM_PART_TEMPLATE)
        fp1["subQuery"] = self.genTimeSeriesSubquery(sqlJson, interval, grpCols)
        fp1["alias"] = tsAlias
        q["from"].append(fp1)
        fp2 = copy.deepcopy(FROM_PART_TEMPLATE)
        fp2["joinType"] = "LEFT JOIN"
        fp2["subQuery"] = self.genRawDataSubquery(sqlJson)
        fp2["alias"] = rdAlias
        tmCondition = '{0}.time = {1}.time+({2}-({1}.time%{2}))'.format(tsAlias, rdAlias, interval)
        fp2["on"].append({"opt": None, "val": tmCondition})
        for c in self.getGroupCols(sqlJson):
            cAlias = c.split()[-1].split('.')[-1]
            fp2["on"].append({"opt": 'AND', "val": "{0}.{2} = {1}.{2}".format(tsAlias, rdAlias, cAlias)})
        q["from"].append(fp2)
        q["orderBy"].append("{0}.time".format(tsAlias))
        q["limit"] = sqlJson["limit"]
        q["offset"] = sqlJson["offset"]
        q["groupBy"].append("{0}.time".format(tsAlias))
        for c in self.getGroupCols(sqlJson):
            q["groupBy"].append("{0}.{1}".format(tsAlias, c.split()[-1].split('.')[-1]))
        return q
    
    def interpretInterval(self, sqlJson):
        fill = None
        ptn = EXTENTED_FUNCTION_PATTERNS["interval"]
        unitMap = TIME_UNIT_MAP
        cols = sqlJson["groupBy"].copy()
        intervalColIdx = None
        intervalCol = None
        for i,c in enumerate(cols):
            if re.match(ptn, c):
                intervalColIdx = i
                break
        if intervalColIdx is None:
            return sqlJson
        intervalCol = cols.pop(intervalColIdx)
        #self.removeWhereTmFilter()
        intervalArgs = re.sub(r'_INTERVAL_\(', '', intervalCol, re.IGNORECASE).replace(')_','').split(',')
        if len(intervalArgs) > 1:
            fill = intervalArgs[1].strip()
            if re.match(r'none', fill, re.IGNORECASE):
                fill = None
            else:
                try:
                    fill = int(fill)
                except:
                    logging.error('fill not None or integer.')
        m = re.search(r'[0-9]+[dhms]', intervalArgs[0])
        if m is None:
            return sqlJson
        intervalMS = self.timeDeltaToSec(m.group(0))*1000
        qry = self.genTimeSeriesQuery(sqlJson, intervalMS, cols, fill)
        return qry

    def interpretWherePart(self, sqlJson):
        for i,ft in enumerate(sqlJson["where"]):
            if ft["val"] is not None:
                s = ft["val"]
                ptn = EXTENTED_FUNCTION_PATTERNS["in"]
                ml = list(re.finditer(ptn, s))
                while ml:
                    m = ml.pop()
                    logging.debug("found: {0}".format(m.group(0)))
                    buff = re.sub(r'\)_$', "')", m.group(0).replace("'", "''").replace('\.', '.').replace('\+', '+').replace("|","','").replace("_IN_(","IN ('",1))
                    buff = buff.replace("('(", "('").replace(")')", "')")
                    logging.debug("buff: {0}".format(buff))
                    s = s[:m.start(0)] + buff +s[m.end(0):]
                    logging.debug("s: {0}".format(s))
                ptn = EXTENTED_FUNCTION_PATTERNS["timeFilter"]
                ml = list(re.finditer(ptn, s))
                while ml:
                    m = ml.pop()
                    logging.debug("found: {0}".format(m.group(0)))
                    buff = m.group(0).replace('_TMFILTER_(','').replace(')_','')
                    (colName, buff) = buff.split(',')
                    buff = self.convertTimestamps(buff)
                    buff = self.convertTimeDelta(buff)
                    buff = buff.replace("time", colName)
                    s = s[:m.start(0)] + buff +s[m.end(0):]
                sqlJson["where"][i]["val"] = s
        logging.debug(json.dumps(self.tmFilter))
        return sqlJson

    def interpretExtentedFuntion(self, sqlJson):
        if len(sqlJson["from"]) > 0:
            for i,item in enumerate(sqlJson["from"]):
                if item["subQuery"] is not None:
                    subSqlJ = Sql2Json()
                    subSqlJ.sqlJson = copy.deepcopy(item["subQuery"])
                    sqlJson["from"][i]["subQuery"] = copy.deepcopy(subSqlJ.interpretExtentedFuntion(subSqlJ.sqlJson))
        sqlJson = copy.deepcopy(self.interpretWherePart(sqlJson))
        sqlJson = copy.deepcopy(self.interpretInterval(sqlJson))
        return sqlJson

    def toJson(self):
        selectStmt = copy.deepcopy(SELECT_TEMPLATE)
        while len(self.tokens) > 0:
            nextKey = self.popNextKey()
            #logging.debug("nextKey={0}".format(nextKey))
            if nextKey == 'WITH':
                selectStmt["with"] = self.popWithPart()
            elif nextKey == 'SELECT':
                selectStmt["select"] = self.popSelectPart()
            elif nextKey == 'FROM':
                selectStmt["from"] = self.popFromPart()
            elif nextKey == 'WHERE':
                selectStmt["where"] = self.popWherePart()
            elif nextKey == 'ORDER BY':
                selectStmt["orderBy"] = self.popListVal()
            elif nextKey == 'LIMIT':
                selectStmt["limit"] = self.popNextVal()
            elif nextKey == 'OFFSET':
                selectStmt["offset"] = self.popNextVal()
            elif nextKey == 'GROUP BY':
                selectStmt["groupBy"] = self.popListVal()
            elif nextKey == 'HAVING':
                selectStmt["having"] = self.popHavingPart()
            elif nextKey in ['UNION', 'INTERSECT', 'EXCEPT']:
                op = self.popSetOpPart()
                selectStmt["setOperation"] = {
                    "operator": nextKey,
                    "all": op["all"],
                    "stmt": op["stmt"]
                }
            elif nextKey is None:
                break
        #logging.debug(json.dumps(selectStmt, indent=4))
        return selectStmt
        
        

    def toTsQry(self):
        return self.json2str(self.interpretExtentedFuntion(self.sqlJson))
