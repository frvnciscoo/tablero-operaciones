import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import base64
import os
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from io import BytesIO

def get_img_as_base64(file_path):
    with open(file_path, "rb") as f:
        data = f.read()
    return base64.b64encode(data).decode()

def generar_pdf_resumen(df, fecha, turno):
    # 1. Preparar Datos
    cols = ['Area', 'Faena', 'Metrica', 'Ubicacion', 'Observaciones']
    cols_existentes = [c for c in cols if c in df.columns]
    
    if not cols_existentes:
        return None

    df_pdf = df[cols_existentes].copy()
    if 'Metrica' in df_pdf.columns:
        df_pdf['Metrica'] = df_pdf['Metrica'].apply(
            lambda x: "" if pd.isna(x) else f"{int(x)}"
        )
        
    df_pdf = df_pdf.fillna("").astype(str)
    # Ordenar es vital para el agrupamiento visual
    df_pdf = df_pdf.sort_values(by=['Area', 'Faena', 'Ubicacion'])
    
    # 2. Configurar Estilos de Texto (Paragraph)
    styles = getSampleStyleSheet()
    # Creamos un estilo personalizado para las celdas
    style_cell = ParagraphStyle(
        'CellText', 
        parent=styles['Normal'], 
        fontSize=8, 
        leading=10, # Espacio entre líneas
        alignment=0 # 0=Left, 1=Center, 2=Right
    )
    
    # Estilo para el encabezado (texto en negrita y centrado)
    style_header = ParagraphStyle(
        'HeaderText',
        parent=styles['Normal'],
        fontSize=10,
        leading=12,
        textColor=colors.white,
        fontName='Helvetica-Bold',
        alignment=1 # Center
    )

    # 3. Procesar Filas (Lógica de fusión + Conversión a Paragraph)
    lista_filas = df_pdf.values.tolist()
    data_procesada = []
    
    prev_area = None
    prev_faena = None
    
    for row in lista_filas:
        # Convertimos la fila a lista modificable
        fila_texto = list(row) # Aquí tenemos strings puros
        
        area_actual = fila_texto[0]
        faena_actual = fila_texto[1] if len(fila_texto) > 1 else ""
        
        # --- LÓGICA DE FUSIÓN VISUAL (Borrar texto repetido) ---
        
        # Si el área es igual a la anterior, la dejamos vacía
        if area_actual == prev_area:
            fila_texto[0] = "" 
        else:
            prev_area = area_actual
            prev_faena = None # Reset de faena si cambia el área

        # Si el área está vacía (es repetida) y la faena es igual, la dejamos vacía
        if fila_texto[0] == "" and faena_actual == prev_faena:
            fila_texto[1] = ""
        else:
            prev_faena = faena_actual

        # --- CONVERSIÓN A PARAGRAPH (EL TRUCO PARA EL SALTO DE LÍNEA) ---
        # Recorremos cada celda de esta fila y la envolvemos en un Paragraph.
        # Esto obliga a ReportLab a respetar el ancho de columna y bajar el texto.
        fila_visual = []
        for celda in fila_texto:
            # Paragraph(texto, estilo)
            fila_visual.append(Paragraph(celda, style_cell))
            
        data_procesada.append(fila_visual)

    # 4. Preparar Encabezados (También como Paragraph para centrado perfecto)
    headers_visual = [Paragraph(col, style_header) for col in cols_existentes]
    data_final = [headers_visual] + data_procesada

    # 5. Configurar PDF
    buffer = BytesIO()
    # Landscape Letter: ~792 points de ancho
    # Margenes: 30 izq, 30 der -> Espacio útil: ~732 points
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=landscape(letter),
        rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=18
    )
    
    elements = []
    elements.append(Paragraph(f"<b>Resumen Operacional - {fecha} - Turno {turno}</b>", styles['Heading2']))
    elements.append(Spacer(1, 12))

    # Anchos de columna (Suma total debe ser aprox 730)
    # Area: 110, Faena: 140, Ubicacion: 130, Obs: 350 (Le damos más espacio a Obs)
    col_widths = [110, 140 ,  60, 130, 320] 

    t = Table(data_final, colWidths=col_widths, repeatRows=1)

    # 6. Estilos de la Tabla (Grid y Colores)
    estilo_tabla = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#0d1b2a")), # Fondo Header
        ('VALIGN', (0, 0), (-1, -1), 'TOP'), # Alinear todo arriba para leer bien párrafos
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey), # Líneas grises
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
    ]
    
    # Líneas divisorias gruesas de color azul cuando cambia el Área
    # Como ahora fila_visual[0] es un Objeto Paragraph, no podemos comparar con string ""
    # Usamos la lógica de indices basada en data_procesada original (strings) si fuera necesario,
    # pero aquí podemos detectar si el texto del Paragraph está vacío. 
    # Sin embargo, la forma más fácil es replicar la lógica visual basada en el índice.
    
    # Recorremos las filas de datos (saltando el header que es índice 0)
    for i, fila in enumerate(data_procesada, start=1):
        # Accedemos al objeto Paragraph de la primera columna (Area)
        # El texto está en el atributo 'text' (aunque a veces contiene etiquetas HTML)
        p_area = fila[0] 
        
        # Si el párrafo tiene texto (no es cadena vacía), es un grupo nuevo
        if p_area.getPlainText().strip() != "":
             estilo_tabla.append(('LINEABOVE', (0, i), (-1, i), 1.5, colors.HexColor("#00b4d8")))

    t.setStyle(TableStyle(estilo_tabla))
    elements.append(t)
    
    doc.build(elements)
    buffer.seek(0)
    return buffer


# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="Tablero Planificación Operacional",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- LÓGICA DE REINICIO DESDE EL TÍTULO ---
# Si detectamos 'reset=true' en la URL, limpiamos caché y recargamos
if "reset" in st.query_params:
    st.cache_data.clear()
    st.query_params.clear() # Limpiar la URL para que no se quede en bucle
    st.rerun()
# --- ESTILOS CSS PERSONALIZADOS (MODERNO Y OSCURO) ---
st.markdown("""
<style>
            
    /* Fondo General */
    .stApp {
        background-color: #0d1b2a;
        color: white;
    }
    
    /* Contenedores de métricas y gráficos (Cards) */
    .css-1r6slb0, .css-12oz5g7, .stMarkdown, .stDataFrame {
        color: white;
    }
    
    /* Estilo para los contenedores personalizados */
    .custom-container {
        background-color: #1b263b;
        padding: 15px;
        border-radius: 10px;
        margin-bottom: 15px;
        border: 1px solid #415a77;
    }

    /* Título Centrado */
    .title-container {
        text-align: center;
        cursor: pointer;
        padding: 10px;
    }
    .title-text {
        color: white !important;
        font-size: 2.5rem;
        font-weight: bold;
        text-decoration: none !important; /* Quita el subrayado típico de los links */
        display: block; /* Ocupa el ancho para facilitar el click */
    }
    .title-text:hover {
        color: #00b4d8 !important; /* Efecto hover azul cian */
        transition: 0.3s;
        cursor: pointer;
    }

    /* Filtros (Selectbox y DateInput) */
    .stSelectbox label, .stDateInput label {
        color: #e0e1dd !important;
    }
    div[data-baseweb="select"] > div {
        background-color: #1b263b !important;
        color: white !important;
        border: 1px solid #00b4d8;
    }
    div[data-baseweb="calendar"] {
        background-color: #1b263b !important;
    }
    
    /* Tablas */
    [data-testid="stDataFrame"] {
        background-color: #1b263b;
    }
    
    /* Botones */
    .stButton > button {
        background-color: #00b4d8;
        color: white;
        border-radius: 5px;
        border: none;
    }
    .stButton > button:hover {
        background-color: #0096c7;
    }

    /* Eliminar padding excesivo de Streamlit para efecto "pantalla completa" */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 1rem;
        padding-left: 2rem;
        padding-right: 2rem;
    }
    /* Estilo específico para Radio Buttons (Selector Faenas/Equipos) */
    .stRadio > div {
        flex-direction: row; /* Asegura horizontalidad extra */
        align-items: center;
    }
    
    /* Texto de las opciones del radio button */
    .stRadio label p {
        color: white !important;
        font-size: 1rem;
        font-weight: 500;
    }
    
    /* Círculos del radio button */
    div[data-testid="stMarkdownContainer"] p {
        color: white; 
    } 
    /* Reducir el espacio inferior del radio button específicamente */
    div[data-testid="stRadio"] {
        margin-bottom: 0px !important;
        padding-bottom: 0px !important;
    }           
    /* Ajuste fino del título */
    .title-text {
        margin: 0 !important;      /* Elimina márgenes rebeldes */
        padding: 0 !important;
        line-height: 1.0 !important; /* Alineación vertical más precisa */
        text-align: center;
    }
    
    /* Contenedor flexible para asegurar centrado total */
    .title-container {
        display: flex;
        justify-content: center;
        align-items: center;
        width: 100%;
    } 
    /* --- ESTILOS ESPECÍFICOS PARA EL DATE INPUT --- */

    /* 1. El campo de entrada (la caja donde se ve la fecha) */
    div[data-testid="stDateInput"] div[data-baseweb="base-input"] {
        background-color: #1b263b !important;
        border: 1px solid #415a77 !important;
        border-radius: 5px !important;
    }
    
    /* 2. El texto de la fecha dentro de la caja */
    div[data-testid="stDateInput"] input {
        color: white !important;
    }

    /* 3. El icono del calendario (svg) dentro de la caja */
    div[data-testid="stDateInput"] svg {
        fill: white !important;
    }

    /* --- ESTILOS PARA EL CALENDARIO DESPLEGABLE (POPOVER) --- */
    
    /* Fondo del calendario desplegable */
    div[data-baseweb="calendar"] {
        background-color: #1b263b !important;
        color: white !important;
    }
    
    /* Contenedor del popover (borde y fondo) */
    div[data-baseweb="popover"] > div {
        background-color: #1b263b !important;
        border: 1px solid #415a77 !important;
    }

    /* Cabecera del calendario (Mes/Año) */
    div[data-baseweb="calendar"] div {
        color: white !important;
    }
    
    /* Flechas de navegación del calendario */
    div[data-baseweb="calendar"] button svg {
        fill: white !important;
    }

    /* Los días (números) */
    div[data-baseweb="day"] {
        color: #e0e1dd !important;
    }

    /* Día seleccionado */
    div[data-baseweb="day"][aria-selected="true"] {
        background-color: #00b4d8 !important;
        color: white !important;
    }
    
    /* Hover sobre los días (efecto al pasar el mouse) */
    div[data-baseweb="day"]:hover:not([aria-selected="true"]) {
        background-color: #415a77 !important;
    }
    
    /* Desactivar días (si hubiera) */
    div[data-baseweb="day"][aria-disabled="true"] {
        color: #415a77 !important;
    } 
    /* --- CORRECCIÓN FINAL: DÍAS DE LA SEMANA (Mon, Tue, Wed...) --- */
    
    /* Apunta al contenedor específico de los nombres de los días */
    div[data-baseweb="calendar"] > div:nth-child(2) {
        background-color: #1b263b !important;
    }

    /* Asegura que el texto (Mon, Tue...) sea blanco */
    div[data-baseweb="calendar"] > div:nth-child(2) div {
        color: white !important;
        font-weight: bold; /* Opcional: para que se lean mejor */
            
    } 
    /* --- ESTILOS DE TABLA (SOLUCIÓN DEFINITIVA ENCABEZADOS) --- */
    
    /* 1. Fondo del contenedor general */
    div[data-testid="stDataFrame"] {
        background-color: #1b263b !important;
        border: 1px solid #415a77;
        border-radius: 5px;
    }

    /* 2. ENCABEZADOS (HEADERS) - La parte difícil */
    /* Apuntamos al rol 'columnheader' que usa Streamlit internamente */
    div[data-testid="stDataFrame"] div[role="columnheader"] {
        background-color: #1b263b !important; /* Tu color oscuro */
        color: white !important;
        border-bottom: 2px solid #415a77 !important; /* Borde inferior para separar */
    }

    /* 3. Asegurar que el TEXTO dentro del encabezado sea blanco */
    div[data-testid="stDataFrame"] div[role="columnheader"] div,
    div[data-testid="stDataFrame"] div[role="columnheader"] span,
    div[data-testid="stDataFrame"] div[role="columnheader"] p {
        color: white !important;
        font-weight: bold !important;
    }

    /* 4. CELDAS DE DATOS (Por si el estilo de Python falla) */
    div[data-testid="stDataFrame"] div[role="gridcell"] {
        background-color: #1b263b !important;
        color: white !important;
        border-bottom: 1px solid #415a77 !important;
    }
    
    /* 5. CELDAS DE ÍNDICE (La primera columna si estuviera visible) */
    div[data-testid="stDataFrame"] div[role="rowheader"] {
        background-color: #1b263b !important;
        color: white !important;
    }     
                                                  
</style>
""", unsafe_allow_html=True)

# --- CARGA DE DATOS ---
@st.cache_data(ttl=60) # Actualiza cada 60 segundos si se recarga
def load_data():
    url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQVBpFJ2ofFXndlMC4xtuqc4AaO7BguF1Z3Jp-XrB0xD_wVsZrHFp51yoqCrfbBd6WGxxFKhTqtnOc-/pub?output=xlsx"
    
    try:
            sheet1 = pd.read_excel(url, sheet_name='Sheet1')
            equipos = pd.read_excel(url, sheet_name='Equipos')
            
            # 1. Limpieza básica de nombres de columnas
            sheet1.columns = sheet1.columns.str.strip()
            equipos.columns = equipos.columns.str.strip()
            try:
                jefe_op = pd.read_excel(url, sheet_name='JefeOp')
                jefe_op.columns = jefe_op.columns.str.strip()
                # Asegurar formato fecha para filtrar
                if 'Fecha' in jefe_op.columns:
                    jefe_op['Fecha'] = pd.to_datetime(jefe_op['Fecha'], dayfirst=True,errors='coerce').dt.date
            except Exception as e:
                # Si falla leer esa hoja, creamos un df vacío para que no rompa el resto
                jefe_op = pd.DataFrame(columns=['Fecha', 'Dia', 'Noche'])
            # ---------------------------------------------------------
            # LÓGICA DE EXCLUSIÓN GRUPAL (SI HAY UN "NO", SE VA TODO EL TÍTULO)
            # ---------------------------------------------------------

            # Función auxiliar para filtrar grupos "contaminados"
            def filtrar_por_grupo(df, col_id, col_activo):
                # Normalizamos la columna Activo para evitar errores de espacios
                # Creamos una serie temporal limpia
                if col_activo in df.columns and col_id in df.columns:
                    activo_norm = df[col_activo].astype(str).str.strip()
                    
                    # A. Identificamos los Títulos que tienen al menos un registro que NO sea "Si"
                    # (O específicamente que sea "No", dependiendo de tu regla estricta. 
                    # Aquí asumimos que si dice "No", contamina el grupo).
                    titulos_sucios = df[activo_norm == 'No'][col_id].unique()
                    
                    # B. Filtramos el DataFrame original:
                    # Mantenemos solo las filas cuyo Título NO esté en la lista de sucios
                    df_limpio = df[~df[col_id].isin(titulos_sucios)]
                    
                    # C. (Opcional) Limpieza final: 
                    # Si después de eliminar los grupos con "No", quedan filas vacías o raras
                    # y quieres conservar SOLO las que dicen "Si" explícitamente:
                    df_limpio = df_limpio[df_limpio[col_activo].astype(str).str.strip() == 'Si']
                    
                    return df_limpio
                return df

            # Aplicamos la lógica a Sheet1 (Usando columna 'Título')
            if 'Título' in sheet1.columns and 'Activo' in sheet1.columns:
                sheet1 = filtrar_por_grupo(sheet1, 'Título', 'Activo')

            # Aplicamos la lógica a Equipos (Usando columna 'Titulo' sin tilde, según tu esquema)
            if 'Titulo' in equipos.columns and 'Activo' in equipos.columns:
                equipos = filtrar_por_grupo(equipos, 'Titulo', 'Activo')
                
            # ---------------------------------------------------------

            # Asegurar formato fecha
            sheet1['FechaHora'] = pd.to_datetime(sheet1['FechaHora'], errors='coerce').dt.date
            equipos['FechaHora'] = pd.to_datetime(equipos['FechaHora'], errors='coerce').dt.date
            
            return sheet1, equipos, jefe_op

    except Exception as e:
            st.error(f"Error al cargar datos: {e}")
            return pd.DataFrame(), pd.DataFrame()

df_sheet1, df_equipos, df_jefe_op  = load_data()

# --- HEADER ---
# Usamos 3 columnas: [Espacio Izq] [Título Centro] [Logo Der]
# vertical_alignment="center" alinea todo al medio verticalmente (Streamlit 1.31+)
col_spacer, col_title, col_logo = st.columns([1.5, 7, 1.5], vertical_alignment="center")

# 1. Columna Izquierda (Vacía, solo para equilibrar el logo y centrar el título)
with col_spacer:
    st.write("") 

# 2. Columna Central (Título)
with col_title:
    # Lógica de reinicio
    if "reset" in st.query_params:
        st.cache_data.clear()
        st.query_params.clear()
        st.rerun()

    st.markdown("""
        <div class="title-container">
            <a href="?reset=true" target="_self" class="title-text">
                Tablero de Planificación Operacional
            </a>
        </div>
    """, unsafe_allow_html=True)

# 3. Columna Derecha (Logo)
with col_logo:
    try:
        img_b64 = get_img_as_base64("logo-svti.png")
        # El logo se alinea a la derecha dentro de su columna
        st.markdown(f"""
            <div style="display: flex; justify-content: flex-end; align-items: center;">
                <img src="data:image/png;base64,{img_b64}" 
                     style="width: 130px; border-radius: 0px !important;">
            </div>
        """, unsafe_allow_html=True)
    except:
        st.write("")
# --- FILTROS ---
# Contenedor con fondo distinto para los filtros
with st.container():
    c1, c2, c3, c4 = st.columns(4)
    
    # Filtros base
    fechas_disponibles = sorted(df_sheet1['FechaHora'].dropna().unique())
    turnos_disponibles = sorted(df_sheet1['Turno'].dropna().unique())
    
    with c1:
        fecha_sel = st.date_input("Fecha", value=fechas_disponibles[-1] if len(fechas_disponibles) > 0 else datetime.now())
    with c2:
        turno_sel = st.selectbox("Turno", options=turnos_disponibles)

    # Filtrado inicial para llenar selects de Area y Faena (excluyendo Equipos y Grúas)
    mask_base = (df_sheet1['FechaHora'] == fecha_sel) & (df_sheet1['Turno'] == turno_sel)
    df_filtered_s1 = df_sheet1[mask_base]
    
    # Excluir "Equipos y Grúas" de los filtros
    areas_disp = df_filtered_s1[df_filtered_s1['Area'] != "Equipos y Grúas"]['Area'].unique()
    faenas_disp = df_filtered_s1[df_filtered_s1['Faena'] != "Equipos y Grúas"]['Faena'].unique()
    
    with c3:
        area_sel = st.selectbox("Área", options=['Todas'] + list(areas_disp))
    with c4:
        faena_sel = st.selectbox("Faena", options=['Todas'] + list(faenas_disp))

# Lógica de filtrado final
if area_sel != 'Todas':
    df_filtered_s1 = df_filtered_s1[df_filtered_s1['Area'] == area_sel]
if faena_sel != 'Todas':
    df_filtered_s1 = df_filtered_s1[df_filtered_s1['Faena'] == faena_sel]

# Filtrado de Equipos (Para Gráfico 1 y Tabla modo Equipos)
# Nota: "Equipos" se vincula por fecha y turno primariamente.
mask_equipos = (df_equipos['FechaHora'] == fecha_sel) & (df_equipos['Turno'] == turno_sel)
df_filtered_equipos = df_equipos[mask_equipos]

# --- ESTRUCTURA DEL DASHBOARD ---

# Definimos funciones de ploteo para mantener el código limpio

def plot_recursos_solicitados(df):
    if df.empty:
        return go.Figure()
    
    # Agrupar por recurso y sumar cantidad
    df_group = df.groupby('Recurso')['Cantidad'].sum().reset_index()
    df_group = df_group.sort_values('Cantidad', ascending=True)
    
    fig = go.Figure(go.Bar(
        x=df_group['Cantidad'],
        y=df_group['Recurso'],
        orientation='h',
        text=df_group['Cantidad'],
        textposition='outside',
        marker_color='#00b4d8',
        textfont=dict(color="white")
    ))
    
    fig.update_layout(
        height=330,
        title=dict(text="Recursos Solicitados", font=dict(color="white", size=20)),
        plot_bgcolor='#1b263b',
        paper_bgcolor='#1b263b',
        font=dict(color='white'),
        margin=dict(l=10, r=20, t=40, b=10),
        xaxis=dict(showgrid=False, visible=False), # Ocultar eje X para limpieza
        yaxis=dict(showgrid=False, tickfont=dict(color="white"))
    )
    return fig

def plot_disponibilidad_equipos(df, fecha, turno):
    # --- 1. CONFIGURACIÓN DE COLORES (Edita esto a tu gusto) ---
    # Asigna un color específico a cada Área que tengas en tus datos.
    colores_areas = {
            # Operaciones "Pesadas" o Principales (Tonos oscuros e intensos)
            "S. NAVES": "#023e8a",         # Azul Marino Profundo (Destaca base sólida)
            "YARD": "#0077b6",            # Azul Medio (Fuerte pero distinto a Naves)
            
            # Operaciones de Carga y Base (Tu color principal)
            "S. A LA CARGA": "#00b4d8",   # TU COLOR BASE (Cyan Vibrante)
            
            # Almacenamiento y Depósito (Tonos medios)
            "DEPOSITO": "#48cae4",        # Celeste Brillante
            
            # Procesos Administrativos/Apoyo (Tonos claros/pasteles)
            "S. PROCED. ADUANEROS Y G. DOCU.": "#90e0ef", # Celeste pálido
            "Capacitación": "#caf0f8",    # Casi blanco/Hielo (Muy distintivo)
            
            # Color de seguridad por si aparece otra área
            "default": "#adb5bd"     
        }

    
    # Color de la barra de SALDO (El fondo gris/fantasma)
    color_saldo_barra = 'rgba(65, 90, 119, 1)' 
    # -----------------------------------------------------------

    # 2. Filtro base y Exclusiones
    mask = (df['FechaHora'] == fecha) & (df['Turno'] == turno)
    df_static = df[mask].copy()
    
    excluir = ["PREGATE", "GARITAS", "SUPERVISORES", "AUXILIARES", "FRIGORISTAS", "INSTRUCTOR", "PRACTICANTE"]
    if not df_static.empty:
        df_static['Recurso'] = df_static['Recurso'].astype(str).str.strip()
        df_static = df_static[~df_static['Recurso'].isin(excluir)]
    
    if df_static.empty:
        return go.Figure()

    # 3. Separar Capacidad vs Demanda
    df_capacidad = df_static[df_static['Faena'] == 'Equipos y Grúas'].groupby('Recurso')['Cantidad'].sum()
    df_demanda = df_static[df_static['Faena'] != 'Equipos y Grúas']
    
    todos_recursos = sorted(list(set(df_capacidad.index) | set(df_demanda['Recurso'].unique())))
    
    fig = go.Figure()

    # 4. Graficar las Faenas (Barras de colores DEFINIDOS)
    areas = df_demanda['Area'].unique()
    acumulado_por_recurso = {r: 0 for r in todos_recursos}

    for area in areas:
        d_area = df_demanda[df_demanda['Area'] == area].groupby('Recurso')['Cantidad'].sum()
        y_vals = []
        x_vals = []
        
        for r in todos_recursos:
            val = d_area.get(r, 0)
            if val > 0:
                y_vals.append(r)
                x_vals.append(val)
                acumulado_por_recurso[r] += val
        
        if x_vals:
            text_ints = [int(x) for x in x_vals]
            
            # --- SELECCIÓN DEL COLOR ---
            # Buscamos el nombre del área en el diccionario, si no existe, usamos 'default'
            color_actual = colores_areas.get(area, colores_areas["default"])
            
            fig.add_trace(go.Bar(
                name=area,
                y=y_vals,
                x=x_vals,
                orientation='h',
                text=text_ints,
                textposition='auto',
                textfont=dict(color='white'),
                # APLICAMOS EL COLOR AQUÍ
                marker=dict(color=color_actual, line=dict(width=0))
            ))

    # 5. Graficar Saldo / Remanente
    y_rem = []
    x_rem = []
    text_vals = []
    text_colors = []
    
    for r in todos_recursos:
        cap_total = df_capacidad.get(r, 0)
        usado = acumulado_por_recurso[r]
        
        saldo = cap_total - usado
        remanente = max(0, saldo)
        
        y_rem.append(r)
        x_rem.append(remanente)
        
        text_vals.append(f"{int(saldo)}") 
        
        # Color del TEXTO del saldo (Rojo si falta, Blanco si sobra)
        if saldo < 0:
            text_colors.append('#ff4d4d')
        else:
            text_colors.append('white')

    fig.add_trace(go.Bar(
        name="Saldo",
        y=y_rem,
        x=x_rem,
        orientation='h',
        text=text_vals,
        textposition='outside',
        textfont=dict(
            color=text_colors,
            size=14,
            weight='bold'
        ),
        # Usamos la variable definida al inicio para el color de la barra fantasma
        marker_color=color_saldo_barra, 
        hoverinfo='skip'
    ))
    
    fig.update_layout(
        barmode='stack',
        title=dict(
            text="Disponibilidad Equipos", 
            font=dict(color="white", size=20),
            x=0, y=0.98, yanchor='top'
        ),
        plot_bgcolor='#1b263b',
        paper_bgcolor='#1b263b',
        font=dict(color='white'),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.05, xanchor="right", x=1,
            font=dict(color="white")
        ),
        margin=dict(l=10, r=20, t=100, b=10),
        xaxis=dict(showgrid=False, visible=False),
        yaxis=dict(tickfont=dict(color='white'))
    )
    return fig
def plot_mapa(df_loc):
    # 1. CONFIGURACIÓN DE ZONAS (Ajusta x, y, w, h a tu imagen real)
    zonas_cfg = {
        'Garitas':      {'x': 1050,  'y': 230, 'w': 30, 'h': 30},
        'Aforo':      {'x': 970,  'y': 250, 'w': 30, 'h': 30},
        ' E1, E2, E3, E4, E5, S3, R3, R4, R5, R6, R7, R8':       {'x': 300, 'y': 230, 'w': 220, 'h': 100},
        ' (O2 AL D6)':        {'x': 210, 'y': 30,  'w': 100, 'h': 100},
        'RACKS/NAVE':     {'x': 700, 'y': 230, 'w': 220, 'h': 20},
        'Sitio 1':     {'x': 710, 'y': 400, 'w': 140, 'h': 20},
        'Sitio 2':     {'x': 570, 'y': 400, 'w': 140, 'h': 20},
        'Sitio 3':     {'x': 430, 'y': 400, 'w': 140, 'h': 20},
        'Sitio 4':     {'x': 290, 'y': 400, 'w': 140, 'h': 20},
        'Sitio 5':     {'x': 150, 'y': 400, 'w': 140, 'h': 20},
        'X3':     {'x': 635, 'y': 160, 'w': 30, 'h': 40},
        'Bodega 6':     {'x': 450, 'y': 150, 'w': 180, 'h': 65},
        'Bodega 7':     {'x': 330, 'y': 130, 'w': 120, 'h': 80},
        'Bodega 8':     {'x': 665, 'y': 170, 'w': 110, 'h': 50},
        'Bodega 1':     {'x': 540, 'y': 230, 'w': 100, 'h': 50},
        'Bodega 2':     {'x': 540, 'y': 280, 'w': 100, 'h': 50},
        'Línea 10':     {'x': 330, 'y': 210, 'w': 300, 'h': 20},
        'Línea 11':     {'x': 330, 'y': 210, 'w': 300, 'h': 20},
        'Línea 12':     {'x': 330, 'y': 210, 'w': 300, 'h': 20},
        'Línea 9':     {'x': 330, 'y': 210, 'w': 300, 'h': 20}

    }
    
    fig = go.Figure()
    
    # 2. Cargar Imagen de Fondo
    try:
        from PIL import Image
        img = Image.open("mapa-svti.png")
        ancho_img = img.width
        alto_img = img.height
        
        fig.add_layout_image(
            dict(
                source=img,
                xref="x", yref="y",
                x=0, y=alto_img,
                sizex=ancho_img, sizey=alto_img,
                sizing="stretch", opacity=1, layer="below"
            )
        )
    except:
        ancho_img, alto_img = 1000, 800
        fig.add_annotation(text="Falta imagen mapa-svti.png", x=500, y=400, showarrow=False, font=dict(color="white"))

    # 3. Calcular Conteos
    if not df_loc.empty and 'Ubicacion' in df_loc.columns:
        counts = df_loc['Ubicacion'].value_counts()
    else:
        counts = pd.Series()

    # Listas para crear la capa invisible de Hover (Tooltip)
    hover_x = []
    hover_y = []
    hover_text = []

    # 4. Dibujar Rectángulos
    for zona, cfg in zonas_cfg.items():
        cantidad = counts.get(zona, 0)
        
        # Solo dibujamos si hay cantidad > 0 para no ensuciar
        if cantidad > 0:
            color_relleno = "rgba(0, 180, 216, 0.6)" # Azul semi-transparente
            color_borde = "white"
            grosor_borde = 2
            
            # Coordenadas Plotly
            x0 = cfg['x']
            y1 = alto_img - cfg['y']
            x1 = cfg['x'] + cfg['w']
            y0 = alto_img - (cfg['y'] + cfg['h'])

            # A) Dibujar el Rectángulo (Solo visual, sin texto)
            fig.add_shape(
                type="rect",
                x0=x0, y0=y0, x1=x1, y1=y1,
                line=dict(color=color_borde, width=grosor_borde),
                fillcolor=color_relleno,
                layer="above"
            )
            
            # B) Guardar coordenadas centrales para el Hover
            hover_x.append(x0 + (cfg['w'] / 2))
            hover_y.append(y0 + (cfg['h'] / 2))
            hover_text.append(f"{zona}: {cantidad}")

    # 5. Capa Invisible de Interacción (Para que salga el texto al pasar el mouse)
    if hover_x:
        fig.add_trace(go.Scatter(
            x=hover_x,
            y=hover_y,
            mode='markers',
            marker=dict(size=0, opacity=0), # Totalmente invisible
            text=hover_text,
            hoverinfo='text', # Solo muestra el texto limpio
            showlegend=False
        ))

    # Configuración final
    fig.update_xaxes(visible=False, range=[0, ancho_img])
    fig.update_yaxes(visible=False, range=[0, alto_img])
    
    fig.update_layout(
        title=dict(text="Mapa de Operaciones", font=dict(color="white", size=20)),
        plot_bgcolor='#1b263b',
        paper_bgcolor='#1b263b',
        font=dict(color='white'),
        margin=dict(l=10, r=10, t=50, b=10),
        height=400,
        dragmode=False,
        hoverlabel=dict(bgcolor="#1b263b", font_size=14, font_family="sans-serif") # Estilo del tooltip
    )
    return fig
# --- LAYOUT PRINCIPAL ---

# FILA 1: Gráfico Recursos (Izq) | Tabla (Der)
row1_col1, row1_col2 = st.columns(2)

with row1_col1:
    st.markdown('<div class="custom-container">', unsafe_allow_html=True)
    
    # 1. Copiamos la base filtrada por Fecha y Turno
    df_chart1 = df_filtered_equipos.copy()

    # 2. --- AQUÍ ESTÁ EL CAMBIO ---
    # Filtramos para que NO ( != ) incluya 'Equipos y Grúas'
    df_chart1 = df_chart1[df_chart1['Faena'] != 'Equipos y Grúas']
    # ------------------------------

    # 3. Aplicamos los filtros interactivos del usuario (si seleccionó algo específico)
    if faena_sel != 'Todas':
        df_chart1 = df_chart1[df_chart1['Faena'] == faena_sel]
    
    if area_sel != 'Todas':
        df_chart1 = df_chart1[df_chart1['Area'] == area_sel]

    # 4. Generamos el gráfico
    fig1 = plot_recursos_solicitados(df_chart1)
    st.plotly_chart(fig1, use_container_width=True, config={'displayModeBar': False})
    st.markdown('</div>', unsafe_allow_html=True)

with row1_col2:
    st.markdown('<div class="custom-container">', unsafe_allow_html=True)
    
    # --- SUB-LAYOUT: [Toggle] [Info Jefes] [Botón PDF] ---
    # Ajustamos proporciones: 2.5 (Toggle), 3 (Texto Jefes), 1.5 (Botón)
    col_toggle, col_info, col_btn = st.columns([2, 3, 2], vertical_alignment="center")

    # 1. TOGGLE (Izquierda)
    with col_toggle:
        modo_tabla = st.radio(
            "Modo:", ["Faenas", "Equipos"], 
            horizontal=True, label_visibility="collapsed", key="selector_modo"
        )

    # 2. INFO JEFES (Centro)
    with col_info:
        # Lógica para obtener Dia y Noche según la fecha seleccionada
        jefe_dia = "--"
        jefe_noche = "--"
        
        if not df_jefe_op.empty and 'Fecha' in df_jefe_op.columns:
            # Filtramos por la fecha seleccionada en el filtro principal (fecha_sel)
            df_jefe_filtrado = df_jefe_op[df_jefe_op['Fecha'] == fecha_sel]
            
            if not df_jefe_filtrado.empty:
                # Tomamos el primer registro encontrado
                fila_jefe = df_jefe_filtrado.iloc[0]
                jefe_dia = str(fila_jefe.get('Dia', '--'))
                jefe_noche = str(fila_jefe.get('Noche', '--'))

        # Mostramos el texto estilizado en el centro
        st.markdown(f"""
            <div style="text-align: center; font-weight: bold; color: white; font-size: 0.9rem; border: 1px solid #415a77; border-radius: 5px; padding: 5px; background-color: #0d1b2a; margin-top:-15px;">
                <span style="color: #00b4d8;">D:</span> {jefe_dia} &nbsp;|&nbsp; <span style="color: #00b4d8;">N:</span> {jefe_noche}
            </div>
        """, unsafe_allow_html=True)

    # 3. BOTÓN PDF (Derecha)
    with col_btn:
        mask_pdf = (df_sheet1['FechaHora'] == fecha_sel) & (df_sheet1['Turno'] == turno_sel)
        df_to_pdf = df_sheet1[mask_pdf].copy()
        df_to_pdf = df_to_pdf[df_to_pdf['Faena'] != "Equipos y Grúas"]
        
        if not df_to_pdf.empty:
            pdf_data = generar_pdf_resumen(df_to_pdf, fecha_sel, turno_sel)
            if pdf_data:
                st.download_button(
                    label="📥 PDF Resumen",
                    data=pdf_data,
                    file_name=f"Resumen_{fecha_sel}_{turno_sel}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )

    # Espaciador
    st.markdown('<div style="margin-top: -10px;"></div>', unsafe_allow_html=True)

    # --- TABLAS (Estilo y Visualización) ---
    def aplicar_estilo(df):
        return df.style.set_properties(**{
            'background-color': '#1b263b',
            'color': 'white',
            'border-color': '#415a77'
        })

    if modo_tabla == "Faenas":
        df_faenas_clean = df_filtered_s1[df_filtered_s1['Faena'] != "Equipos y Grúas"]
        df_faenas_clean['Metrica'] = df_faenas_clean['Metrica'].fillna(0).astype(int)

        cols_mostrar = ['Faena', 'Ubicacion','Metrica', 'Observaciones']
        cols_validas = [c for c in cols_mostrar if c in df_faenas_clean.columns]
        
        st.dataframe(
            aplicar_estilo(df_faenas_clean[cols_validas]), 
            height=250, 
            use_container_width=True, 
            hide_index=True
        )
        
    else:
        df_equipos_interno = df_filtered_equipos[df_filtered_equipos['Faena'] == 'Equipos y Grúas']
        df_show = df_equipos_interno.rename(columns={'Recurso': 'Equipo', 'Observaciones': 'Comentarios'})
        
        if 'Cantidad' in df_show.columns:
            df_show['Cantidad'] = df_show['Cantidad'].fillna(0).astype(int)

        cols_validas = [c for c in ['Equipo', 'Cantidad', 'Comentarios'] if c in df_show.columns]
        
        st.dataframe(
            aplicar_estilo(df_show[cols_validas]), 
            height=250, 
            use_container_width=True, 
            hide_index=True,
            column_config={
                "Cantidad": st.column_config.NumberColumn("Cantidad", format="%d", step=1)
            }
        )

    st.markdown('</div>', unsafe_allow_html=True)

# FILA 2: Gráfico Disponibilidad (Izq) | Mapa (Der)
# Prompt: "La fila del gráfico de recursos... tenga la mitad del ancho que la fila del gráfico de disponibilidad..."
# Interpretación: Probablemente se refiere a ALTURA visual (height) para que quepa en una pantalla.
# Ajustaremos alturas en los gráficos Plotly.

row2_col1, row2_col2 = st.columns(2)

with row2_col1:
    st.markdown('<div class="custom-container">', unsafe_allow_html=True)
    # Este gráfico es estático respecto a filtros Area/Faena, usa df_equipos original filtrado solo por fecha/turno
    fig2 = plot_disponibilidad_equipos(df_equipos, fecha_sel, turno_sel)
    # Aumentamos altura para dar peso visual
    fig2.update_layout(height=450)
    st.plotly_chart(fig2, use_container_width=True, config={'displayModeBar': False})
    st.markdown('</div>', unsafe_allow_html=True)

with row2_col2:
    st.markdown('<div class="custom-container">', unsafe_allow_html=True)
    # Mapa usa df_filtered_s1 (Faenas filtradas)
    fig_map = plot_mapa(df_filtered_s1)
    fig_map.update_layout(height=450)
    st.plotly_chart(fig_map, use_container_width=True, config={'displayModeBar': False})
    st.markdown('</div>', unsafe_allow_html=True)