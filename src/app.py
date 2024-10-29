from flask import Flask, render_template, request, jsonify
from routes.routes import audio
from config.mongodb import iniciarDB
from config.gridfsdb import iniciar_grid_fs
from services.services import cargar_db_grid
import os
from flask_cors import CORS

app = Flask(__name__)


@app.before_request
def before_request():
    headers = {'Access-Control-Allow-Origin': '*',
               'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
               'Access-Control-Allow-Headers': 'Content-Type'}
    if request.method.lower() == 'options':
        return jsonify(headers), 200

CORS(app, resources={r"/api/audioConsulta/*": {"origins": "http://localhost:4200"}})

uri = os.getenv('MONGO_URI')
#uri = "mongodb://localhost:27017/audiosDB"

clave = 'supersecretkey'
app.config['MONGO_URI'] = uri
app.config['SECRET_KEY'] = clave  # Clave secreta para firmar el JWT

mongo = iniciarDB(uri)
grid_fs = iniciar_grid_fs(uri)
cargar_db_grid(mongo, grid_fs)

@app.route('/')
def index():
    return render_template('index.html')

app.register_blueprint(audio, url_prefix='/api')

if __name__ == '__main__':
    app.run(debug=True, port=4000)