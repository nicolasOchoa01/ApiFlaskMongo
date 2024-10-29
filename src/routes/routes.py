from flask import Blueprint
#from services.services import create_audio_service, get_audios_service, get_audio_service, update_audio_service, delete_audio_service
from services.services import register_user_service, upload_audio_file_in_storage_service
from services.services import loggin_password_service, loggin_username_service
from services.services import token_required

audio = Blueprint('audio', __name__)


@audio.route('/register', methods=['POST'])
def register_user():
    return register_user_service()

@audio.route('loggin-username', methods=['POST'])
def loggin_username():
    return loggin_username_service()

@audio.route('loggin-password', methods=['POST'])
def loggin_password():
    return loggin_password_service()

@audio.route('/upload-audio', methods=['POST'])
@token_required
def upload_audio_file_in_storage(username):
    return upload_audio_file_in_storage_service(username)





# @audio.route('/', methods=['GET'])
# def get_audios():
#     return get_audios_service()

# @audio.route('/<id>', methods=['GET'])
# def get_audio(id):
#     return get_audio_service(id)

# @audio.route('/', methods=['POST'])
# def create_audio():
#     return create_audio_service()

# @audio.route('/<id>', methods=['PUT'])
# def update_audio(id):
#     return update_audio_service(id)

# @audio.route('/<id>', methods=['DELETE'])
# def delete_audio(id):
#     return delete_audio_service(id)


