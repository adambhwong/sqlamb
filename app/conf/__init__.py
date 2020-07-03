import logging, os

# logger configuration
DEBUG = int(os.getenv('DEBUG', 0))
if DEBUG == 0:
    dbg_lvl = logging.INFO
else:
    dbg_lvl = logging.DEBUG
LOG_CFG = {
    "level": dbg_lvl,
    "datefmt": '%Y-%m-%d %H:%M:%S',
    "format": '%(asctime)s [%(levelname)s] %(module)s.%(funcName)s: %(message)s'
}

# inventroy file for credential manager
CRED_KEY = os.getenv('CREDENTIAL_KEY')

# credential manager URL
CREDMGR_URL = os.getenv('CREDMGR_URL', "http://hk-kwn-iacpoc01.ap.elcompanies.net:8081/v1/credMgr")

# InfluxQL forward target
INFLUXQL_FW_TARGET = os.getenv('INFLUXQL_FW_TARGET', "http://hk-kwn-iacpoc01.ap.elcompanies.net:8086")

# available data source
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
        "host": os.getenv("DATASOURCES_3_HOST", "us-azr-pudapi01"),
        "port": 17778,
        "credential": "solarwinds"
    },
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

# data type mapping
SQLITE_DATATYPE_MAP = {
    "int": "INTEGER",
    "float": "REAL",
    "str": "TEXT",
    "unicode": "TEXT"
}

# epoch settings for timeseries data
DEFAULT_EPOCH='ms'

EPOCH_MAP={
    'h': 1/3600.0,
    'm': 1/60.0,
    's': 1.0,
    'ms': 1000.0,
    'u': 1000000.0,
    'ns': 1000000000.0
}

