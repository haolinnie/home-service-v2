import time
import datetime
import sqlite3
from flask import Flask, jsonify
from flask import make_response, render_template
from flask_restful import Resource, Api, reqparse
from werkzeug.middleware.proxy_fix import ProxyFix

from home_service.get_db import get_db, execute_db, init_app

parser = reqparse.RequestParser()
parser.add_argument('n', type=int, help="ERROR: empty length of data")
# For POST requests, only one name
parser.add_argument('name', type=str)
# For GET requests, can have multiple names
parser.add_argument('names', action='append', type=str)
parser.add_argument('temperature', type=float)
parser.add_argument('humidity', type=float)


def insert_name_temperature(table_name, name, data):
    timestamp = int(time.time())
    if 'humidity' in table_name:
        var = 'humidity'
    else:
        var = 'temperature'
    try:
        with get_db() as connection:
            cursor = connection.cursor()
            cursor.execute('''
            INSERT INTO {}
            VALUES (?,?,?)'''.format(table_name),
                           (name, timestamp, data))
            cursor.close()
    except Exception as e:
        return {"Exception Type": str(type(e)),
                "Args": str(e.args),
                "__str__": str(e.__str__)}
    return {
        'status': True,
        'name': name,
        var: data 
    }


def select_names_npoints(table_name, names, n_points):
    ''' If n_points is None, select data from the last day.
        If names is None, select all.
    '''
    if 'humidity' in table_name:
        var = 'humidity'
    else:
        var = 'temperature'

    cmd = '''SELECT name, timestamp, {} FROM {} '''.format(var, table_name)

    if names is not None:
        nm = "'" + "', '".join(names) + "'"
        cmd += ''' WHERE name in ({})
        '''.format(nm)

    if n_points is None:
        if 'WHERE' in cmd:
            cmd += 'AND'
        else:
            cmd += 'WHERE'
        cmd += ''' timestamp BETWEEN {} AND {}'''.format(
                int((datetime.datetime.now()-datetime.timedelta(days=1)).timestamp()),
                int(datetime.datetime.now().timestamp()))
        n_points = 2000

    cmd += ''' ORDER BY timestamp DESC LIMIT {} '''.format(n_points)
    try:
        data = execute_db(cmd)
    except Exception as e:
        return {"Exception Type": str(type(e)),
                "Args": str(e.args),
                "__str__": str(e.__str__)}

    names = set(v[0] for v in data)
    res = {}
    for name in names:
        res[name] = []
    for v in data:
        res[v[0]].append({
            'x': v[1],
            'y': v[2]
        })
    return res


class SensorTemp(Resource):
    def get(self):
        args = parser.parse_args()
        n_points = args.get('n')
        names = args.get('names')

        return select_names_npoints('sensor_temp', names, n_points)

    def post(self):
        args = parser.parse_args()
        name = args["name"]
        temperature = args["temperature"]

        if name is None or temperature is None:
            return {"error": "Missing arguments"}

        return insert_name_temperature('sensor_temp', name, temperature)

class SensorHumidity(Resource):
    def get(self):
        args = parser.parse_args()
        n_points = args.get('n')
        names = args.get('names')

        return select_names_npoints('sensor_humidity', names, n_points)

    def post(self):
        args = parser.parse_args()
        name = args["name"]
        humidity = args["humidity"]

        if name is None or humidity is None:
            return {"error": "Missing arguments"}

        return insert_name_temperature('sensor_humidity', name, humidity)


class PiTemp(Resource):
    def get(self):
        args = parser.parse_args()
        n_points = args.get('n')
        names = args.get('names')

        return select_names_npoints('pi_temp', names, n_points)

    def post(self):
        parser.add_argument('name', type=str)
        parser.add_argument('temperature', type=float)
        args = parser.parse_args()
        name = args["name"]
        temperature = args["temperature"]
        timestamp = int(time.time())

        if name is None or temperature is None:
            return {"error": "Missing arguments"}

        return insert_name_temperature('pi_temp', name, temperature)


class GitPull(Resource):
    def get(self, repo_name):
        if repo_name == "tigernie_website":
            res = os.popen("cd /var/www/tigernie-website && git pull").readline().strip()
            return jsonify({"status": res})


def create_app():

    # Instantiate flask app
    app = Flask(__name__, instance_relative_config=True)
    init_app(app)

    # Proxy support for NGINX
    app.wsgi_app = ProxyFix(app.wsgi_app)

    # Configure to see multiple errors in response
    app.config['BUNDLE_ERRORS'] = True

    @app.route('/')
    def index():
        return render_template('index.html')

    @app.route('/debug')
    def debug():
        return render_template('debug.html')

    @app.errorhandler(404)
    def not_found(error):
        return make_response(jsonify({'error': "Not found"}), 404)

    # Flask_restful API
    api = Api(app)
    api.add_resource(SensorTemp, '/home_api/sensor_temp')
    api.add_resource(SensorHumidity, '/home_api/sensor_humidity')
    api.add_resource(PiTemp, '/home_api/pi_temp')
    api.add_resource(GitPull, '/home_api/gitpull/<string:repo_name>')

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(port="6969", debug=True)