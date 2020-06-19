import falcon
import resources.influxProxy as ifpx

BASE_PATH=''

app = falcon.API()
app.add_route(BASE_PATH + '/ping', ifpx.PingResource())
app.add_route(BASE_PATH + '/write', ifpx.WriteResource())
app.add_route(BASE_PATH + '/query', ifpx.QueryResource())
app.add_route(BASE_PATH + '/debug/pprof', ifpx.DebugPprofResource())
app.add_route(BASE_PATH + '/debug/pprof/{profile}', ifpx.DebugPprofParamResource())
app.add_route(BASE_PATH + '/debug/requests', ifpx.DebugRequestsResource())
app.add_route(BASE_PATH + '/debug/vars', ifpx.DebugVarsResource())
