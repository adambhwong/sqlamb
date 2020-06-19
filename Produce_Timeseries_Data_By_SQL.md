This document explains how to produce timeseries data by using SQL.  

To produce a timeseriese skeleton with SQL, we have to use a recursive CTE (Common Table Expression) to generate the timestamps as follow:  

```
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
```

In joint statement, you can use the ```_INTERVAL_()_``` to replace the above code:  

```
SELECT
  tmp.time as time,
  b.affiliate,
  SUM(tmp.InAvg) as InAvg,
  SUM(tmp.OutAvg) as OutAvg
FROM (
  SELECT
    time,
    IPAddress,
    AVG(a.InAveragebps) as InAvg,
    AVG(a.OutAveragebps) as OutAvg
  FROM a
  WHERE _TMFILTER_(time, $timeFilter)_
  GROUP BY
    _INTERVAL_(10m, 0)_,
    IPAddress
) tmp
LEFT JOIN b
ON tmp.IPAddress = b.ip_address
GROUP BY time, affiliate
ORDER BY time
```

