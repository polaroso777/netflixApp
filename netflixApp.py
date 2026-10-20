import json
import pandas as pd
import streamlit as st
from google.cloud import firestore
from google.oauth2 import service_account
from sqlalchemy import text

#   Conexion a firebase
@st.cache_resource
def conectar_firestore():
    datos = st.secrets["textkey"]
    if isinstance(datos, str):
        datos = json.loads(datos)
    else:
        datos = dict(datos)
    credenciales = service_account.Credentials.from_service_account_info(datos)
    return firestore.Client(credentials=credenciales, project=datos["project_id"])

#   Conexion a postgresql
@st.cache_resource
def conectar_postgresql():
    return st.connection("postgresql", type="sql")

#   Hacer el dataframe para la coleccion de firebase
def obtener_peliculas(base_datos):
    documentos = base_datos.collection("movies").stream()
    lista_peliculas = []
    for documento in documentos:
        lista_peliculas.append(documento.to_dict())
    columnas = ["name", "genre", "director", "company"]
    return pd.DataFrame(lista_peliculas).reindex(columns=columnas).fillna("")

#   Busqueda de nombre por coincidencias de firebase
def buscar_peliculas(dataframe, nombre):
    return dataframe[dataframe["name"].str.contains(nombre, case=False, regex=False, na=False)]

#   Filtro por directores de firebase
def buscar_director(dataframe, director):
    return dataframe[dataframe["director"] == director]

#   Insertar pelicular a firebase
def guardar_pelicula(base_datos, nombre, genero, director, compania):
    nueva_pelicula = {"name": nombre, "genre": genero, "director": director, "company": compania}
    base_datos.collection("movies").add(nueva_pelicula)

#   Guardar comentario en postgresql
def guardar_comentario(conexion, correo, comentario):
    with conexion.session as sesion:
        sesion.execute(
            text("INSERT INTO people (email, comment) VALUES (:email, :comment)"),
            {"email": correo, "comment": comentario},
        )
        sesion.commit()

#   Traer comentarios de postgresql
def consultar_comentarios(conexion):
    return conexion.query("SELECT email, comment FROM people", ttl=0)

#   Streamlit
st.set_page_config(page_title="Netflix app", layout="wide")
st.title("Netflix app")

try:
    db = conectar_firestore()
    df_peliculas = obtener_peliculas(db)
except Exception as error:
    st.error("No se pudo consultar Firestore.")
    st.exception(error)
    st.stop()

#   Mostrar todo con checkbox
st.sidebar.header("Explorar peliculas")
mostrar_todos = st.sidebar.checkbox("Mostrar todo", value=True)

#   Cuadro de texto para buscar por titulo
st.sidebar.subheader("Buscar por titulo")
titulo = st.sidebar.text_input("Titulo de la pelicula")
boton_buscar = st.sidebar.button("Buscar pelicula")

#   Lista desplegable con los directores para filtrar
st.sidebar.subheader("Seleccionar director")
directores = sorted(df_peliculas["director"].astype(str).unique().tolist())
director_elegido = st.sidebar.selectbox("Director", ["Selecciona un director"] + directores)
boton_director = st.sidebar.button("Filtrar director")

st.sidebar.divider()

#   Formulario para insertar nueva pelicula
st.sidebar.subheader("Nuevo pelicula")
with st.sidebar.form("formulario_pelicula", clear_on_submit=True):
    nombre = st.text_input("Nombre")
    genero = st.text_input("Género")
    director_nuevo = st.text_input("Director del nuevo pelicula")
    compania = st.text_input("Compañia")
    boton_guardar = st.form_submit_button("Crear nuevo pelicula")

st.sidebar.divider()

#   Formulario para insertar nuevo comentario
st.sidebar.subheader("Libro de visitas")
with st.sidebar.form("formulario_comentario", clear_on_submit=True):
    correo = st.text_input("Correo electrónico")
    comentario = st.text_area("Comentario")
    boton_comentario = st.form_submit_button("Registrar visita")
boton_visitas = st.sidebar.button("Ver visitas")

# Guardar nueva pelicula en firebase y actualizar el dataframe
if boton_guardar:
    if nombre.strip() and genero.strip() and director_nuevo.strip() and compania.strip():
        try:
            guardar_pelicula(db, nombre.strip(), genero.strip(), director_nuevo.strip(), compania.strip())
            df_peliculas = obtener_peliculas(db)
            st.success("Pelicula guardada correctamente.")
        except Exception as error:
            st.error("No se pudo guardar la pelicula.")
            st.exception(error)
    else:
        st.warning("Completa todos los campos de la pelicula.")

#   Guardar comentario nuevo en postgresql
if boton_comentario:
    if correo.strip() and comentario.strip():
        try:
            guardar_comentario(conectar_postgresql(), correo.strip(), comentario.strip())
            st.success("Comentario guardado en PostgreSQL.")
        except Exception as error:
            st.error("No se pudo guardar el comentario.")
            st.exception(error)
    else:
        st.warning("Completa el correo y el comentario.")

#   Acciones por botones de busqueda y filtrado
if boton_buscar:
    st.header("Búsqueda por titulo")
    if titulo.strip():
        resultado = buscar_peliculas(df_peliculas, titulo.strip())
        st.write("Total de peliculas:", len(resultado))
        st.dataframe(resultado, use_container_width=True, hide_index=True)
    else:
        st.info("Escribe un titulo para buscar.")
elif boton_director:
    st.header("Peliculas por director")
    if director_elegido != "Selecciona un director":
        resultado = buscar_director(df_peliculas, director_elegido)
        st.write("Total de peliculas:", len(resultado))
        st.dataframe(resultado, use_container_width=True, hide_index=True)
    else:
        st.info("Selecciona un director.")
elif mostrar_todos:
    st.header("Todos los peliculas")
    st.write("Total de peliculas:", len(df_peliculas))
    st.dataframe(df_peliculas, use_container_width=True, hide_index=True)

#   Cargar comentarios de postgresql
if boton_visitas:
    st.header("Comentarios de los visitantes")
    try:
        df_comentarios = consultar_comentarios(conectar_postgresql())
        st.dataframe(df_comentarios, use_container_width=True, hide_index=True)
    except Exception as error:
        st.error("No se pudieron consultar los comentarios.")
        st.exception(error)
