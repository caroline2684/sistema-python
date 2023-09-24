from flask import Flask, render_template, request, redirect, url_for, session, flash
from datetime import datetime
from bson import ObjectId
from pymongo import MongoClient
from werkzeug.security import generate_password_hash
from werkzeug.security import check_password_hash
from datetime import datetime, timedelta

app = Flask(__name__)

# Configuramos la conexion al replicaset de mongo
client = MongoClient(
    "mongodb+srv://caroline:Jade2684@development.3ttkyle.mongodb.net/sistema_bancario?retryWrites=true&w=majority"
)

# Se utilizara la base de datos bank1
db = client.bank1


@app.route("/")
def index():
    return sign()


@app.route("/movimientos", methods=["GET", "POST"])
def movimientos():
    # Obtener el ID de usuario actual desde la sesión
    usernid = session.get("username")
    usuario_id = ObjectId(usernid)

    # Obtener los parámetros de búsqueda del formulario
    fecha_inicio = request.args.get("fecha_inicio")
    fecha_fin = request.args.get("fecha_fin")

    # Construir una consulta para filtrar las transacciones
    filter_query = {"client": usuario_id}

    if fecha_inicio and fecha_fin:
        filter_query["date"] = {"$gte": fecha_inicio, "$lte": fecha_fin}

    # Obtener y ordenar las transacciones por fecha en orden ascendente
    collection = db["Transaction"]
    result = collection.find(filter_query).sort("date", 1)

    # Crear una lista para almacenar los registros formateados
    registros_formateados = []

    # Inicializar el saldo total en 0
    saldo_total = 0

    # Calcular el saldo total para cada transacción y almacenarlas en orden descendente
    transacciones_ordenadas = []
    for item in result:
        # Formatear la fecha
        fecha_formateada = datetime.strptime(
            item["date"], "%Y-%m-%d %H:%M:%S"
        ).strftime("%Y-%m-%d %I:%M %p")

        # Formatear el tipo de transacción
        tipo_transaccion = "Ingreso" if item["Type"] == 1 else "Egreso"

        # Calcular el saldo total para esta transacción
        if item["Type"] == 1:  # Ingreso
            saldo_total += int(item["mount"])
        elif item["Type"] == 2:  # Egreso
            saldo_total -= int(item["mount"])

        # Agregar el registro formateado a la lista de transacciones ordenadas
        transacciones_ordenadas.insert(
            0,  # Insertar al principio para orden descendente
            {
                "Registro": fecha_formateada,
                "Tipo de Transacción": tipo_transaccion,
                "Valor": f"${item['mount']}",
                "Saldo Total": f"${saldo_total}",
            },
        )

    return render_template(
        "movimientos.html", data=transacciones_ordenadas, monto=saldo_total
    )


@app.route("/login", methods=["POST"])
def login():
    # verificar usuario y contraseña
    username = request.form["username"]
    contrasena = request.form["contrasena"]

    collection = db["clientes"]

    result = collection.find_one({"username": username})

    if result and check_password_hash(result["contraseña"], contrasena):
        # Las contraseñas coinciden, guardar la sesión
        session["username"] = str(result["_id"])
        return redirect(url_for("ingreso"))
    else:
        return redirect(url_for("logout"))


app.secret_key = "clave"


@app.route("/ingreso", methods=["GET"])
def ingreso():
    usernid = session.get("username")
    usuario_id = ObjectId(usernid)
    collection = db["clientes"]
    print(usuario_id)
    result = collection.find({"_id": usuario_id})
    result = list(result)
    for doc in result:
        mount = doc.get("monto")
    print(mount)
    monto = mount
    if "resultado_ingreso" in session:
        message = session.get("resultado_ingreso")
        session.pop("resultado_ingreso")
    else:
        message = "null"
    return render_template("ingreso.html", monto=monto, message=message)


@app.route("/ingreso", methods=["POST"])
def guardar():
    monto = request.form["monto"]
    print(monto)
    # Actualizar saldo
    usernid = session.get("username")
    print(usernid)
    usuario_id = ObjectId(usernid)
    collection = db["Transaction"]
    collections = db["clientes"]
    # Obtener los registros
    fecha_actual = datetime.now()
    # Formato de fecha
    fecha_formateada = fecha_actual.strftime("%Y-%m-%d %H:%M:%S")
    sessions = client.start_session()
    with sessions.start_transaction():
        try:
            # Realizar ingreso
            collection.insert_one(
                {
                    "client": usuario_id,
                    "Type": 1,
                    "mount": monto,
                    "date": fecha_formateada,
                }
            )
            # Actualizar el saldo
            collections.update_one({"_id": usuario_id}, {"$inc": {"monto": int(monto)}})

            sessions.commit_transaction()

            resultado = "¡Saldo actualizado!"
        except:
            session.abort_transaction()
            resultado = "Error al actualizar el saldo"

    sessions.end_session()
    session["resultado_ingreso"] = resultado
    return redirect(url_for("ingreso"))

@app.route("/egreso", methods=["GET"])
def egreso():
    # Verificar cedula
    usernid = session.get("username")
    usuario_id = ObjectId(usernid)
    collection = db["clientes"]
    print(usuario_id)
    result = collection.find({"_id": usuario_id})
    result = list(result)
    for doc in result:
        mount = doc.get("monto")
    print(mount)
    monto = mount
    if "resultado_egreso" in session:
        message = session.get("resultado_egreso")
        session.pop("resultado_egreso")
    else:
        message = "null"
    return render_template("egreso.html", monto=monto, message=message)


@app.route("/egreso", methods=["POST"])
def retiro():
    monto = int(request.form["monto"])
    usernid = session.get("username")
    usuario_id = ObjectId(usernid)
    collection = db["Transaction"]
    collections = db["clientes"]
    fecha_actual = datetime.now()
    fecha_formateada = fecha_actual.strftime("%Y-%m-%d %H:%M:%S")
    sessions = client.start_session()
    with sessions.start_transaction():
        try:
            cliente = collections.find_one({"_id": usuario_id})
            monto_actual = cliente["monto"]

            # Verificar Saldo
            if monto_actual >= monto:
                # Realizar el Egreso
                collection.insert_one(
                    {
                        "client": usuario_id,
                        "Type": 2,
                        "mount": monto,
                        "date": fecha_formateada,
                    }
                )
                # Actualizar saldo
                collections.update_one({"_id": usuario_id}, {"$inc": {"monto": -monto}})

                sessions.commit_transaction()
                resultado = "¡Egreso realizado correctamente!"
            else:
                sessions.abort_transaction()
                resultado = "Error: El saldo actual es insuficiente"

        except:
            sessions.abort_transaction()
            resultado = "Error al realizar el egreso"

    sessions.end_session()
    session["resultado_egreso"] = resultado
    return redirect(url_for("egreso"))


@app.route("/perfil", methods=["GET", "POST"])
def perfilusuario():
    # Obtener el ID de usuario actual de la sesión
    usuario_id = session.get("username")

    # Verificar si el usuario está autenticado
    if usuario_id:
        # Obtener los datos del usuario actual desde la base de datos
        usuario = db["clientes"].find_one({"_id": ObjectId(usuario_id)})

        # Verificar si se encontró el usuario en la base de datos
        if usuario:
            name = usuario.get("name")
            dni = usuario.get("dni")
            username = usuario.get("username")

            if request.method == "POST":
                # Obtener la nueva contraseña del formulario
                nueva_contrasena = request.form["nueva_contrasena"]

                # Generar el hash de la nueva contraseña
                nueva_contrasena_hashed = generate_password_hash(
                    nueva_contrasena, method="sha256"
                )

                # Actualizar el campo de contraseña en la base de datos con el nuevo hash
                db["clientes"].update_one(
                    {"_id": usuario["_id"]},
                    {"$set": {"contraseña": nueva_contrasena_hashed}},
                )

                # Redirigir a la página de perfil después de cambiar la contraseña
                flash("Contraseña actualizada con éxito.", "success")
                return redirect(url_for("perfilusuario"))

            return render_template("perfil.html", name=name, dni=dni, username=username)

    # Si el usuario no está autenticado o no se encuentra en la base de datos, redirigir a otra página o mostrar un mensaje de error.
    flash("No se encontró el usuario o no está autenticado.", "error")
    return redirect(url_for("logout"))


@app.route("/logout")
def logout():
    if "username" in session:
        session.pop("username")
    return redirect(url_for("index"))


@app.route("/perfil")
def perfil():
    return render_template("perfil.html")


@app.route("/sign-in")
def sign():
    return render_template("sign-in.html")


@app.route("/sign-up", methods=["GET"])
def sign_up():
    return render_template("registro.html")


@app.route("/sign-up", methods=["POST"])
def sign_up_post():
    # Obtener los datos del formulario
    nombre = request.form["nombre"]
    apellido = request.form["apellido"]
    dni = request.form["dni"]
    username = request.form["username"]
    contrasena = request.form["contrasena"]
    # Generar el hash de la contraseña
    hashed_password = generate_password_hash(contrasena, method="sha256")
    # Crear el campo "name" con el apellido y nombre combinados
    name = f"{apellido} {nombre}"
    # Crear el documento a insertar en la colección
    cliente = {
        "name": name,
        "dni": dni,
        "monto": 0,
        "username": username,
        "contraseña": hashed_password,
    }
    client = db["clientes"]
    # Insertar el documento en la colección
    client.insert_one(cliente)
    return sign()


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")
