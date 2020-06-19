# sqlamb
SQL Alliance Metrics Blender (SQLamb)  
---

This project aims to implment a data blender for multiple datasources to serve Grafana as camouflaged Influxdb datasource. To reduce the administration overhead and simplify the development work on dashboard, it should avoid involving any backend coding on doing queries, and provide a common query language support to serve as grab-n-go style. As a result, SQLamb is designed to take a combination of JSON and originated ?QL to fufill the requirement. It provides following features:

- join queries results by using SQL  
- forward all requests other then "query" to the provided influxdb in the request parameter (debug/pprof, debug/requests, debug/vars, ping, write)  
- for "query" requests, only intercept if query string is a valid JSON structure  
- datasource support can be expended, currently support InfluxQL, MySQL, Solarwinds (SWQL)
- provide "group by time interval" translation in joint query statement to perform time-series like group by interval feature
- optional parameter 'table' in query end point to allow returning result in table form instead of time series by setting it with 'true'.
 
SQLamb works by saving results from list of queries including time series data set or SQL data set to an in-memory SQLite db. For time series result set, it will be transformed to data frame format before writing to SQLite. And then use joint statement to blend the data from saved tables in the SQLite db, and the result will be returned as time series result set by default or data frame if 'table' paramter is set to 'true'.  

Below is the JSON query structure:
```
{
    "queries": [
        {
            "alias": "",                      #an alias to be used as table name in sqlite db
            "datasource": "",                 #datasource defined in config file
            "statement": ""                   #query statement
        }[,...]
    ],
    "joint": {                                #"joint" is optional
          "alias": "",                        #an alias to be used as the name in the result set data
          "tags": ["",...],                   #list of columns from query result to be treated as tags in returned time series data
          "statement": ""                     #sqlite query statement
     }
}
```

You have to deifne the datasources in config file:
```
DATASOURCES = {
    "telegraf": {
        "dbtype": "influxdb",
        "host": os.getenv("DATASOURCES_0_HOST", "hk-kwn-iacpoc01.ap.elcompanies.net"),
        "port": 8086,
        "db": "telegraf",
        "credential": "telegraf_db"
    },
    "chronograf": {
        "dbtype": "influxdb",
        "host": os.getenv("DATASOURCES_1_HOST", "hk-kwn-iacpoc01.ap.elcompanies.net"),
        "port": 8086,
        "db": "chronograf",
        "credential": "telegraf_db"
    },
    "cmdb": {
        "dbtype": "mysql",
        "host": os.getenv("DATASOURCES_2_HOST", "hk-kwn-iacpoc01.ap.elcompanies.net"),
        "port": 3306,
        "db": "iac_cmdb",
        "credential": "cmdb"
    },
    "solarwinds": {
        "dbtype": "solarwinds",
        "host": os.getenv("DATASOURCES_3_HOST", "us-smy-wpswweb1"),
        "port": 17778,
        "credential": "solarwinds"
    }
    "vpn_conn": {
        "dbtype": "influxdb",
        "host": os.getenv("DATASOURCES_4_HOST", "hk-kwn-iacpoc01.ap.elcompanies.net"),
        "port": 8086,
        "db": "vpn_conn",
        "credential": "telegraf_db"
    },
    "rubrik": {
        "dbtype": "influxdb",
        "host": os.getenv("DATASOURCES_5_HOST", "hk-kwn-iacpoc01.ap.elcompanies.net"),
        "port": 8086,
        "db": "rubrik",
        "credential": "telegraf_db"
    },
    "sentinelone": {
        "dbtype": "influxdb",
        "host": os.getenv("DATASOURCES_6_HOST", "hk-kwn-iacpoc01.ap.elcompanies.net"),
        "port": 8086,
        "db": "sentinelone",
        "credential": "telegraf_db"
    }
}
```

Special pattern interpretations:

| Pattern | Description |
| --- | --- |
| ```" IN _(.*)_"``` | This will be tranaslated from influxql pattern match syntax to SQL list syntax. |
| ```"_TMFILTER_(<Column>, <timer_filter>)_"``` | This will be translated from grafana time filter to SQL filter using 'column' as time. |
| ```"_INTERVAL_(<interval>[, <fill>])_"``` | This pattern only apply to joint query statement, it will translate the sql to group data by interval and allow you fill "none", or "0" for any missing data points. It must be used with ```_TMFILTER_``` pattern to specify the time range. For detailed explaination, please refer to the document "Produce_Timeseries_Data_By_SQL.md" |


Sample queries
1. count alerts by dcname, and get 0 for no data.
```
{
    "queries": [
        {
            "alias": "a",
            "datasource": "chronograf",
            "statement": "SELECT count(\"value\") FROM \"alerts\" WHERE \"dcname\" != '' AND time>=now()-7d GROUP BY \"dcname\""
        },
        {
            "alias": "b",
            "datasource": "chronograf",
            "statement": "SHOW TAG VALUES FROM \"alerts\" WITH KEY=\"dcname\""
        }
    ],
    "joint": {
          "alias": "count_alerts_by_dcname",
          "tags": ["dcname"],
          "statement": "SELECT b.value as dcname, IFNULL(a.count, 0) as count FROM b LEFT JOIN a ON b.value = a.dcname;"
     }
}
```

2. calculate CPU allocation percentage by affiliate (using metrics from influxdb and relation info from MySQL).
```
{
    "queries": [
        {
            "alias": "a",
            "datasource": "telegraf",
            "statement": "SELECT sum(last) as cpu_cap FROM (SELECT last(totalCapacity_average) FROM vsphere_host_cpu WHERE time>now()-15m GROUP BY esxhostname,dcname) GROUP BY dcname"
        },
        {
            "alias": "b",
            "datasource": "telegraf",
            "statement": "SELECT sum(last) as cpu_alloc FROM (SELECT last(entitlement_latest) FROM vsphere_vm_cpu WHERE time>now()-15m GROUP BY vmname,dcname) GROUP BY dcname"
        },
        {
            "alias": "c",
            "datasource": "cmdb",
            "statement": "SELECT `affiliate`, `dcname` FROM `vs_dc_info`"
        }
    ],
    "joint": {
          "alias": "cpu_usage",
          "tags": ["affiliate"],
          "statement": "SELECT c.affiliate as affiliate, sum(b.cpu_alloc)*100/sum(a.cpu_cap) as usage FROM c LEFT JOIN a on c.dcname = a.dcname LEFT JOIN b on c.dcname = b.dcname GROUP BY c.affiliate"
    }
}
```

3. get a network switch link stat from solarwinds using grafana built-in time filter in time series format.
```
{
    "queries": [
        {
            "alias": "a",
            "datasource": "solarwinds",
            "statement": "SELECT b.DateTime as time, a.NodeID, a.InterfaceID, a.Caption as InterfaceName, c.Caption as NodeName, b.InAveragebps, b.OutAveragebps FROM Orion.NPM.Interfaces a LEFT JOIN Orion.NPM.InterfaceTraffic b ON a.InterfaceID = b.InterfaceID LEFT JOIN Orion.Nodes c ON a.NodeID = c.NodeID WHERE a.InterfaceID=12128 AND _TMFILTER_(b.DateTime, $timeFilter)_"
        }
    ],
    "joint": {
          "alias": "test_chart",
          "tags": ["NodeID", "InterfaceID", "NodeName", "InterfaceName"],
          "statement": "SELECT a.time as time, a.NodeID as NodeID, a.InterfaceID as InterfaceID, a.NodeName as NodeName, a.InterfaceName as InterfaceName, a.InAveragebps as InAveragebps, a.OutAveragebps as OutAveragebps from a order by a.time desc"
    }
}
```

4. get partner VPN traffic and group by 10min interval  
```  
{
    "queries": [
        {
            "alias": "a",
            "datasource": "solarwinds",
            "statement": "SELECT time, IPAddress, AVG(InAveragebps) as InAveragebps, AVG(OutAveragebps) as OutAveragebps FROM ( SELECT DATETRUNC('minute', b.DateTime) as time, c.IPAddress, b.InAveragebps, b.OutAveragebps FROM Orion.NPM.Interfaces a LEFT JOIN Orion.NPM.InterfaceTraffic b ON a.InterfaceID = b.InterfaceID LEFT JOIN Orion.Nodes c ON a.NodeID = c.NodeID WHERE c.IPAddress IN _($vpnIP)_ AND a.InterfaceName LIKE '%outside%' AND _TMFILTER_(b.DateTime, $timeFilter)_ ) tmp GROUP BY time, IPAddress"
        },
        {
            "alias": "b",
            "datasource": "cmdb",
            "statement": "SELECT UPPER(name) as name, ip_address, CASE WHEN SUBSTR(UPPER(name), 1, 5) = 'CH-SH' THEN 'CN' WHEN SUBSTR(UPPER(name), 1, 5) = 'CN-HK' THEN 'HK' ELSE SUBSTR(UPPER(name), 1,2) END as affiliate FROM network_device_tbl WHERE UPPER(name) IN _($vpnGw)_"
        }
    ],
    "joint": {
          "alias": "s2s_traffic",
          "tags": ["affiliate"],
          "statement": "SELECT tmp.time as time, b.affiliate, SUM(tmp.InAvg) as InAvg, SUM(tmp.OutAvg) as OutAvg FROM ( SELECT time, IPAddress, AVG(a.InAveragebps) as InAvg, AVG(a.OutAveragebps) as OutAvg FROM a WHERE _TMFILTER_(time, $timeFilter)_ GROUP BY _INTERVAL_(10m, 0)_, IPAddress ) tmp LEFT JOIN b ON tmp.IPAddress = b.ip_address GROUP BY time, affiliate ORDER BY time"
    }
}
```  

Limitations:  

- no authentication supported in current release  
- query translation only support select statments  


Todo:  

- externalize datasource configuration  
- add interface for datasources administration  
- adopt plugin based design for datasoruce type support  
- add RBAC support to control datasources access permission  
- add debug endpoint to provide performance statistics based on each query execution  
