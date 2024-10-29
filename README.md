# pasos:

# 1 ) primero crear el entorno virtual
python -m venv venv

# 2 ) activarlo
venv\Scripts\activate

# 3 ) instalar dependencias
pip install -r requirements.txt

# 4 ) ejecutar 
python src/app.py


# NOTA: si se presentan problemas como "El cliente no dispone de un privilegio requerido":

abrir CMD como administrador y hacer los pasos 2, 3, 4;  con solo ejecutar como administrador una vez es suficiente