from flask import request, Response, jsonify
from functools import wraps
from bson import Binary, json_util, ObjectId
import os
import random
import tempfile
from scipy.io import wavfile
import io
import re
import numpy as np
import jwt
import datetime
from speechbrain.inference import SpeakerRecognition
import torchaudio

torchaudio.set_audio_backend("soundfile")

# cargar el modelo preentrenado de SpeechBrain
modelo = SpeakerRecognition.from_hparams(source="speechbrain/spkrec-ecapa-voxceleb", savedir="src/pretrained_model", use_auth_token=False)

mongo = None
grid_fs = None

def cargar_db_grid(mongo_, grid_fs_):
    global mongo
    global grid_fs
    mongo = mongo_
    grid_fs = grid_fs_


# subir un audio al sistema
def upload_audio_file_in_storage_service(username):
    try:
        if 'archivo' not in request.files:
            return jsonify({'error': 'No se ha enviado el archivo'}), 400

        # Obtener el archivo enviado en el formulario
        archivo = request.files['archivo']

        title = request.form.get('title')
        full_filename = str(title)
        mimetype = archivo.mimetype
        file_binary = Binary(archivo.read())
        size = len(file_binary)

        # Subir el archivo a GridFS
        file_id = grid_fs.put(file_binary, filename=full_filename, content_type=mimetype)

        mongo.db.users.update_one(
            {"username": username},          # Filtro para encontrar el documento del usuario
            {"$push": {"audios": file_id}}  # Agregar el nuevo ObjectId a la lista 'audios'
        )

        # Responder con el ID del archivo subido y los metadatos
        return jsonify({
            'message': 'Archivo subido correctamente',
            'file_id': str(file_id),
            'metadata': {
                'filename': full_filename,
                'mimetype': mimetype,
                'size': size,
                # 'sizeUnit': size_unit
            }
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


def register_user_service():
    # Obtener nombre de usuario y audio.wav que servira de contrasenia
    username = request.form['username']
    audio = request.files['password']

    # Verificar si el usuario ya existe
    if mongo.db.users.find_one({"username": username}):
        return jsonify({"mensaje": "ya existe un usuario registrado con ese nombre en el sistema"}), 400

    # Subir el archivo de audio a GridFS y retener su ObjectId
    file_id = grid_fs.put(audio, filename=audio.filename)

    # Guardar los datos del usuario y la referencia al archivo en MongoDB
    user_data = {
        "username": username,
        "password_audio_file_id": file_id,
        "audios":[]
    }
    mongo.db.users.insert_one(user_data)

    return jsonify({"mensaje": "Usuario registrado con éxito", "file_id": str(file_id)}), 201

oracion = " "
username = " "

def loggin_username_service():
    global oracion
    global username

    # obtiene el nombre de usuario enviado desde el front y busca en la base de datos y exite el usuario
    # si el usuario no exite, devuelve un mensaje de error
    # si el ususario exite, genera una oracion y la envia al front para que el usuario la lea
    username = request.form['username']
    if not mongo.db.users.find_one({"username": username}):
        return jsonify({"mensaje":"no existe un usuario registrado con ese nombre en el sistema"}), 400
    oracion = generar_oracion()

    return jsonify({"oracion": oracion}), 200

def loggin_password_service():
    global oracion
    global username

    # obtener el audio desde el front en bytes
    password_front = request.files['password']
    password_front_bytes = password_front.read()

    # crea un archivo temporal para almacenar el audio del front y obtiene su ruta
    ruta_pass_front = convertir_audio_temporal(password_front_bytes)

    # realiza la transcripcion y la valida, obtiene un valor booleano
    #transcripcion = transcribir(ruta_pass_front)
    transcripcion = oracion
    result_lectura = validar_lectura(transcripcion, oracion)

    # si la validacion da False, devuelve un mensaje de error y una nueva oracion para leer
    if not result_lectura:
        eliminar_archivo_temporal(ruta_pass_front)
        oracion = generar_oracion()
        return jsonify({
            "mensaje":"la lectura no coincide con la oracion generada",
            "oracion": oracion,
            "transcripcion": transcripcion}), 400

    # obtiene el audio registrado en grid en bytes
    password_db_bytes = get_password_audio_db(username)

    # crea un archivo temporal para almacenar el audio registrado en grid y devuelve su ruta
    ruta_pass_db = convertir_audio_temporal(password_db_bytes)

    # valida la voz del hablante con la del usuario registrado, obtiene un valor booleano
    result_voz = validar_voz(ruta_pass_front, ruta_pass_db)

    # si la validacion es False, devuelve un mensaje de error y una nueva oracion generada para leer
    if not result_voz:
        eliminar_archivo_temporal(ruta_pass_front)
        eliminar_archivo_temporal(ruta_pass_db)
        oracion = generar_oracion()
        return jsonify({
            "mensaje":"la voz no coincide con la del usuario ingresado",
            "oracion": oracion}), 400

    token = generar_token(username)
    # la validacion se completa, envia mensaje y codigo de estado ok, elimina archivos temporales
    eliminar_archivo_temporal(ruta_pass_front)
    eliminar_archivo_temporal(ruta_pass_db)
    return jsonify({"mensaje":"felicidades te loggeaste con exito",
            "oracion": oracion,
            "transcripcion": transcripcion,
            "token": token}), 201


def generar_token(username):
    # Crear el JWT
    token = jwt.encode({
        'username': username,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=1)  # Expiración en 1 hora
    }, 'secretkey', algorithm="HS256")
    return token

def get_password_audio_db(username):
    # Buscar el usuario
    user = mongo.db.users.find_one({"username": username})
    
    if not user:
        return jsonify({"message": "Usuario no encontrado"}), 404

    # Obtener el archivo de audio desde GridFS
    file_id = user["password_audio_file_id"]
    audio_file = grid_fs.get(file_id)

    # Devolver el archivo de audio
    return audio_file.read()

def generar_oracion():
    sujeto = random.choice(sujetos)
    verbo = random.choice(verbos)
    complemento = random.choice(complementos)
    texto = sujeto + " " + verbo + " " + complemento
    return texto

def convertir_audio_temporal(audio):
    # Crear archivos temporales con nombres únicos
    converted_file_path = create_unique_temp_file(suffix=".wav")

    sample_rate, file_binary = wavfile.read(io.BytesIO(audio))
    wavfile.write(converted_file_path, sample_rate, file_binary)

    return converted_file_path

def eliminar_archivo_temporal(ruta):
    os.remove(ruta)

# Convertir a minúsculas y eliminar puntuaciones, caracteres especiales y espacios
def clear_text(text):
    clean_text = re.sub(r'[^a-zA]', '', text.lower())
    return clean_text

def validar_lectura(transcripcion, texto):
    transcripcion = clear_text(transcripcion)
    texto = clear_text(texto)
    if transcripcion == texto:
        return True
    else:
        return False

def create_unique_temp_file(suffix=".wav"):
    """
    Crea un archivo temporal con un nombre único y devuelve el nombre del archivo.
    El archivo no se eliminará automáticamente al cerrar para permitir su manipulación posterior.
    """
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    temp_file.close()  # Cerramos el archivo para poder usarlo en otros procesos
    return temp_file.name


def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            print('token faltante')
            return jsonify({'message': 'Token faltante'}), 403
        try:
            token = token.split(" ")[1]
            data = jwt.decode(token, 'secretkey', algorithms=["HS256"])
            username = data['username']
        except jwt.ExpiredSignatureError:
            print('token expirado')
            return jsonify({'message': 'Token expirado'}), 403
        except jwt.InvalidTokenError:
            print('token invalido')
            return jsonify({'message': 'Token inválido'}), 403

        return f(username, *args, **kwargs)
    return decorated


# def transcribir(ruta):
#     # Enviar el archivo a Whisper para la transcripción
#     with open(ruta, 'rb') as audio:
#         transcripcion  = openai.audio.transcriptions.create(
#             model="whisper-1",
#             file=audio
#         )
#     # Obtener el texto transcrito
#     transcripcion_text = transcripcion.text
#     # print("Transcripción:", transcripcion_text)
#     return transcripcion_text

def validar_voz(ruta_audio1, ruta_audio2):

    # verificar si las dos voces coinciden
    score, prediccion = modelo.verify_files(ruta_audio1, ruta_audio2)

    # resultado de la verificación, valor booleano
    return prediccion




# Lista de 100 sujetos
sujetos = [
    "El gato", "La casa", "Un coche", "Una persona", "El perro", "El pájaro", "El niño", "La niña",
    "El profesor", "El estudiante", "El árbol", "La montaña", "El río", "El mar", "El viento",
    "El soldado", "El piloto", "El doctor", "El robot", "El astronauta", "La madre", "El padre",
    "El hermano", "La hermana", "El músico", "El pintor", "El actor", "El escritor", "El ingeniero",
    "El chef", "El guardia", "El policía", "El bombero", "El dragón", "El león", "La mariposa",
    "El tiburón", "El lobo", "El oso", "El ciervo", "El ratón", "El científico", "El investigador",
    "El vecino", "El abogado", "El periodista", "El carpintero", "El mecánico", "El electricista",
    "El granjero", "El pescador", "El cazador", "El ciclista", "El corredor", "El nadador", "El pintor",
    "El escritor", "El explorador", "El aventurero", "El viajero", "El turista", "El guía", "El mago",
    "El rey", "La reina", "El príncipe", "La princesa", "El fantasma", "El vampiro", "El monstruo",
    "El alienígena", "El robot", "El samurái", "El ninja", "El pirata", "El guerrero", "El caballero",
    "El capitán", "El director", "El entrenador", "El jugador", "El bailarín", "El cantante",
    "El músico", "El artista", "El fotógrafo", "El cineasta", "El agricultor", "El tendero",
    "El comerciante", "El banquero", "El administrador", "El político", "El filósofo", "El matemático",
    "El físico", "El químico", "El biólogo", "El arquitecto", "El diseñador", "El programador",
    "El desarrollador", "El técnico", "El operador", "El conductor"
]

# Lista de 100 verbos
verbos = [
    "come", "corre", "salta", "mira", "duerme", "camina", "canta", "baila", "conduce", "nada",
    "vuela", "habla", "escribe", "lee", "juega", "construye", "destruye", "crea", "dibuja", "pinta",
    "explora", "descubre", "investiga", "compra", "vende", "prepara", "lava", "seca", "friega",
    "arregla", "rompe", "abre", "cierra", "enciende", "apaga", "atrapa", "lucha", "cocina", "hornea",
    "traduce", "calcula", "enseña", "aprende", "explica", "colorea", "graba", "escucha", "ve", "observa",
    "detecta", "analiza", "programa", "prueba", "mejora", "crece", "disminuye", "calcula", "esculpe",
    "compone", "interpreta", "crea", "borra", "mueve", "gira", "cae", "se levanta", "gana", "pierde",
    "celebra", "descansa", "invita", "recibe", "viaja", "explora", "descubre", "coloca", "empaqueta",
    "envuelve", "abre", "desempaca", "examina", "analiza", "distribuye", "clasifica", "escoge",
    "selecciona", "envía", "recoge", "saca", "mete", "suelta", "agarra", "espera", "reúne", "separa",
    "conecta", "desconecta", "arma", "desarma", "organiza", "resuelve", "atrapa", "escapa", "protege"
]

# Lista de 100 complementos
complementos = [
    "rápidamente", "en el parque", "bajo la lluvia", "con cuidado", "en silencio", "sin hacer ruido",
    "con alegría", "en la biblioteca", "en la montaña", "en la ciudad", "en el desierto", "en el campo",
    "en el mar", "en el bosque", "en el río", "bajo el sol", "en la sombra", "en el avión", "en el tren",
    "en el coche", "en la bicicleta", "en la playa", "en el estadio", "en el teatro", "en el museo",
    "en la galería", "en la tienda", "en la escuela", "en la universidad", "en el hospital", "en el laboratorio",
    "en la oficina", "en la fábrica", "en el mercado", "en el restaurante", "en el café", "en el bar",
    "en la plaza", "en el jardín", "en la piscina", "en la cancha", "en el gimnasio", "en el zoológico",
    "en la farmacia", "en la estación", "en el aeropuerto", "en la base", "en el puerto", "en el barco",
    "en el submarino", "en la nave espacial", "en la casa", "en el apartamento", "en el edificio",
    "en el rascacielos", "en la cueva", "en la mina", "en la torre", "en el castillo", "en la fortaleza",
    "en la iglesia", "en la catedral", "en el templo", "en la mezquita", "en el mercado", "en el supermercado",
    "en la tienda de ropa", "en la librería", "en la ferretería", "en el banco", "en la peluquería",
    "en la estación de tren", "en la parada de autobús", "en la autopista", "en el túnel", "en el puente",
    "en el parque de atracciones", "en el circo", "en el concierto", "en la conferencia", "en el festival",
    "en la exposición", "en el evento", "en la feria", "en el mercado de pulgas", "en la tienda de comestibles",
    "en la oficina de correos", "en el centro comercial", "en el salón de belleza", "en el sofá", "en el club",
    "en la discoteca", "en la heladería", "en la pastelería", "en la panadería", "en la carnicería",
    "en la pescadería", "en la floristería", "en la joyería", "en la tienda de electrónica", "en la gasolinera"
]


# def create_audio_service():
#     data = request.get_json()
#     title = data.get('title', None)
#     description = data.get('description', None)
#     if title:
#         response = mongo.db.audios.insert_one({
#             'title': title,
#             'description': description,
#             'done': False
#         })
#         result = {
#             'id': str(response.inserted_id),
#             'title': title,
#             'description': description,
#             'done': False
#         }
#         return jsonify(result), 200
#     else:
#         return jsonify({'error': 'invalid payload'}), 400

# def get_audios_service():
#     data = mongo.db.audios.find()
#     result = json_util.dumps(data)
#     return Response(result, mimetype='application/json')

# def get_audio_service(id):
#     data = mongo.db.audios.find({'_id': ObjectId(id)})
#     result = json_util.dumps(data)
#     return Response(result, mimetype='application/json')

# def update_audio_service(id):
#     data = request.get_json()
#     if len(data) == 0:
#         return 'invalid payload', 400
#     response = mongo.db.audios.update_one({'_id': ObjectId(id)}, {'$set': data})
#     if response.modified_count >= 1:
#         return 'audios updates successfully', 200
#     else:
#         return 'audio not found', 404

# def delete_audio_service(id):
#     response = mongo.db.audios.delete_one({'_id': ObjectId(id)})
#     if response.deleted_count >= 1:
#         return 'audio deleted successfully', 200


# # funciones gridfs

# # # Subir un archivo a GridFS
# # def subir_archivo(ruta_archivo):
# #     with open(ruta_archivo, "rb") as file:
# #         file_id = grid_fs.put(file, filename=ruta_archivo.split("/")[-1])  # Usar el nombre del archivo
# #         print("Archivo subido" + file_id)


# # Descargar un archivo de GridFS
# def descargar_archivo(file_id, ruta_salida):
#     file_data = grid_fs.get(file_id)
#     with open(ruta_salida, "wb") as output_file:
#         output_file.write(file_data.read())
#     print("Archivo descargado.")

# # Listar archivos en GridFS
# def listar_archivos():
#     print("Archivos en GridFS:")
#     for file in grid_fs.find():
#         print(file.filename)

# # Eliminar un archivo de GridFS
# def eliminar_archivo(file_id):
#     grid_fs.delete(file_id)
#     print("Archivo eliminado.")
