#!/usr/bin/env python
import sys
sys.path.append('/app')
import modules.sql2json as s2j
import json

sqls = []

sqls.append("""
select K.a,K.b from (select H.b from (select G.c from (select F.d from
(select E.e from A, B, C, D, E), F), G), H), I, J, K order by 1,2;
""")

sqls.append("""
SELECT 
  tmp.time as time,
  b.affiliate as affiliate,
  SUM(tmp.InAvg) as InAvg,
  SUM(tmp.OutAvg) as OutAvg
FROM (
  SELECT 
    time as time, 
    IPAddress, 
    AVG(InAveragebps) as InAvg, 
    AVG(OutAveragebps) as OutAvg 
  FROM a 
  WHERE _TMFILTER_(time, time >= now() - 24h)_
  GROUP BY 
    _INTERVAL_(5m, 0)_, 
    IPAddress 
) tmp
LEFT JOIN b
ON tmp.IPAddress = b.ip_address
GROUP BY time, affiliate
ORDER BY time
""")

sqls.append("""
SELECT
  tmp.time as time,
  b.affiliate,
  SUM(tmp.InAvg) as InAvg,
  SUM(tmp.OutAvg) as OutAvg
FROM (
  SELECT
    ts.time as time,
    ts.IPAddress as IPAddress,
    AVG(IFNULL(a.InAveragebps,0)) as InAvg,
    AVG(IFNULL(a.OutAveragebps,0)) as OutAvg
  FROM (
    WITH RECURSIVE
      cnt(x) AS (
         SELECT 1
         UNION ALL
         SELECT x+1 FROM cnt
         LIMIT (
           SELECT ((MAX(time)-MIN(time))/600000)+1 AS lmt FROM a
         )
      )
    SELECT
      (a_time.st + (cnt.x-1)*600000) as time,
      series.IPAddress
    FROM cnt
    LEFT OUTER JOIN (
      SELECT (MIN(time)+(600000-(MIN(time)%600000))) as st
      FROM a
    ) a_time
    LEFT OUTER JOIN (
      SELECT DISTINCT
        IPAddress
      FROM a
    ) series
  ) ts
  LEFT JOIN a
  ON ts.time = a.time+(600000-(a.time%600000))
  AND ts.IPAddress = a.IPAddress
  GROUP BY
    ts.time,
    a.IPAddress
) tmp
LEFT JOIN b
ON tmp.IPAddress = b.ip_address
GROUP BY time, affiliate
ORDER BY time
""")

sqls.append("""
SELECT 
  a.time as time, 
  b.IPAddress, 
  SUM(a.InAveragebps) as InAvg, 
  SUM(a.OutAveragebps) as OutAvg 
FROM a 
LEFT JOIN b
ON a.id = b.id
WHERE _TMFILTER_(a.time, time >= now()-24h)_
GROUP BY 
  _INTERVAL_(5m)_, 
  b.IPAddress 
""")

sqls.append("""
SELECT 
  time, 
  IPAddress, 
  SUM(InAveragebps) as InAvg, 
  SUM(OutAveragebps) as OutAvg 
FROM a 
WHERE _TMFILTER_(time, time >= now()-24h)_
GROUP BY 
  _INTERVAL_(5m)_, 
  IPAddress 
""")

#for sql in sqls:
    #print(json.dumps(s2j.Sql2Json(sql).sqlJson, indent=4))
#    print(s2j.Sql2Json(sql).toTsQry())
sqlj = s2j.Sql2Json(sqls[1])
#print(json.dumps(sqlj.sqlJson, indent=4))
print(sqlj.toTsQry())
