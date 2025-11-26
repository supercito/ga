import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="Analizador Automático de Producción", layout="wide")
st.title("🔎 Analizador Automático de Producción")

# ---------------- helpers ----------------
def leer_mejor(path_or_buffer):
    """
    Intenta leer la hoja correcta automáticamente.
    Si detecta encabezados desplazados en Tiempo Real intenta header=3.
    """
    xl = pd.ExcelFile(path_or_buffer)
    # si hay solo una hoja, usarla
    for sheet in xl.sheet_names:
        try:
            df = xl.parse(sheet_name=sheet, header=0)
            if df.shape[1] > 1:
                return df
        except Exception:
            continue
    # fallback: leer primera hoja sin asumir encabezado
    try:
        return xl.parse(xl.sheet_names[0], header=0)
    except Exception:
        return xl.parse(xl.sheet_names[0], header=None)


def normalizar_cols(df):
    df = df.copy()
    cols = (
        df.columns.astype(str)
        .str.strip()
        .str.lower()
        .str.replace("á","a").str.replace("é","e").str.replace("í","i")
        .str.replace("ó","o").str.replace("ú","u")
        .str.replace("%","").str.replace(".","").str.replace("/","_")
    )
    # reemplazar espacios por guion bajo
    cols = cols.str.replace(r"\s+", "_", regex=True)
    df.columns = cols
    return df


def detectar_columna(df, claves):
    """
    Detecta la primera columna que contenga alguna de las claves (lista) en su nombre.
    Devuelve el nombre real de la columna en df.columns (normalizadas).
    """
    cols = df.columns.tolist()
    for clave in claves:
        for c in cols:
            if clave in c:
                return c
    return None


def convertir_tiempo_serie(s):
    """
    Convierte una Series con tiempos a número (horas).
    - "3,25" -> 3.25
    - "3:15" -> 3.25 (3 horas 15 min -> 3.25 h)
    - "195" -> 195 (se asume la misma unidad que el archivo; se deja como número)
    - errores -> 0
    """
    s = s.astype(str).str.strip().fillna("0")
    # detectar hh:mm
    mask_hm = s.str.contains(":", regex=False)
    res = pd.Series(0.0, index=s.index)
    if mask_hm.any():
        parts = s[mask_hm].str.split(":", expand=True)
        # si hay mm
        horas = pd.to_numeric(parts[0], errors="coerce").fillna(0)
        minutos = pd.to_numeric(parts[1], errors="coerce").fillna(0)
        res.loc[mask_hm] = horas + minutos / 60.0
    # resto: reemplazar coma por punto y convertir
    rest_idx = ~mask_hm
    rest = s[rest_idx].str.replace(",", ".")
    restnum = pd.to_numeric(rest, errors="coerce").fillna(0.0)
    res.loc[rest_idx] = restnum
    return res


def df_to_excel_bytes(dfs_dict):
    """
    Recibe dict: {sheet_name: dataframe} y devuelve bytes excel.
    """
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        for name, df in dfs_dict.items():
            df.to_excel(writer, sheet_name=name[:31], index=False)
        writer.save()
    buffer.seek(0)
    return buffer.getvalue()

# ---------------- UI: carga archivos ----------------
st.sidebar.header("Cargar archivos")
tiempo_real_file = st.sidebar.file_uploader("Tiempo real (Excel)", type=["xlsx", "xls"])
componentes_file = st.sidebar.file_uploader("Componentes (Excel)", type=["xlsx", "xls"])
tiempos_inf_file = st.sidebar.file_uploader("Tiempos informados (Excel)", type=["xlsx", "xls"])
produccion_file = st.sidebar.file_uploader("Producción (Excel)", type=["xlsx", "xls"])

st.sidebar.markdown("---")
st.sidebar.markdown("Opciones de tolerancia y export")

# tolerancias por defecto
margen_inferior = st.sidebar.number_input("Margen inferior (%)", value=-10.0, step=1.0)
margen_superior = st.sidebar.number_input("Margen superior (%)", value=10.0, step=1.0)

# ---------------- Validar carga ----------------
if not (tiempo_real_file and componentes_file and tiempos_inf_file and produccion_file):
    st.info("Sube los 4 archivos (Tiempo real, Componentes, Tiempos informados, Producción) para comenzar.")
    st.stop()

# ---------------- Leer y normalizar ----------------
# usar leer_mejor para mayor robustez (elige hoja)
df_tr_raw = leer_mejor(tiempo_real_file)
df_comp_raw = leer_mejor(componentes_file)
df_tinf_raw = leer_mejor(tiempos_inf_file)
df_prod_raw = leer_mejor(produccion_file)

# si tiempo real viene con encabezado desplazado (caso observado),
# intentar cargar con header=3 si la primera fila es título
if all(col.startswith("unnamed") or "tiempo real por" in str(col).lower() for col in df_tr_raw.columns.astype(str)):
    # re-parse con header=3
    try:
        df_tr_raw = pd.ExcelFile(tiempo_real_file).parse(sheet_name=0, header=3)
    except Exception:
        pass

# normalizar columnas
df_tr = normalizar_cols(df_tr_raw)
df_comp = normalizar_cols(df_comp_raw)
df_tinf = normalizar_cols(df_tinf_raw)
df_prod = normalizar_cols(df_prod_raw)

st.success("✅ Archivos leídos y columnas normalizadas")

# mostrar previews en pestañas
tab1, tab2, tab3, tab4 = st.tabs(["Tiempo Real (preview)","Componentes (preview)","Tiempos Informados (preview)","Producción (preview)"])
with tab1:
    st.dataframe(df_tr.head(20))
with tab2:
    st.dataframe(df_comp.head(10))
with tab3:
    st.dataframe(df_tinf.head(10))
with tab4:
    st.dataframe(df_prod.head(10))

# ---------------- Detectar columnas clave automáticamente ----------------
# listas de keywords
claves_orden = ["orden", "n_orden", "nro_orden", "op", "ordenproduccion","orden_produccion","orden_produccion"]
claves_tiempo = ["tiempo","duracion","hora","horas","hrs","hraa","tiempo_maquina","tiempo_real","tiempo_informado","activ"]

col_orden_prod = detectar_columna(df_prod, "orden")
col_orden_comp = detectar_columna(df_comp, "orden")
col_orden_tr = detectar_columna(df_tr, "orden")
col_orden_tinf = detectar_columna(df_tinf, "orden")

# detectar columnas de tiempo haciendo búsqueda por claves_tiempo
col_tiempo_real = detectar_columna(df_tr, "tiempo") or detectar_columna(df_tr, "duracion") or detectar_columna(df_tr, "hora")
col_tiempo_inf = detectar_columna(df_tinf, "tiempo") or detectar_columna(df_tinf, "duracion") or detectar_columna(df_tinf, "hora")

# columnas para componentes
col_cantidad_necesaria = detectar_columna(df_comp, "necesari") or detectar_columna(df_comp, "cantidad")
col_cantidad_tomada = detectar_columna(df_comp, "tomad") or detectar_columna(df_comp, "cantidad")
col_texto_material = detectar_columna(df_comp, "texto") or detectar_columna(df_comp, "material") or detectar_columna(df_comp, "descripcion")

# columnas para producción
col_texto_prod = detectar_columna(df_prod, "texto") or detectar_columna(df_prod, "material") or detectar_columna(df_prod, "descripcion")
col_cant_orden = detectar_columna(df_prod, "cantidad_orden") or detectar_columna(df_prod, "cantidad")
col_cant_buena = detectar_columna(df_prod, "cantidad_buena") or detectar_columna(df_prod, "buena") or detectar_columna(df_prod, "cantidad_buena_confirmada") or detectar_columna(df_prod, "cantidad_buena_confirmada")

# validar detecciones mínimas
missing = []
if col_orden_prod is None: missing.append("orden en produccion")
if col_orden_comp is None: missing.append("orden en componentes")
if col_orden_tr is None: missing.append("orden en tiempo real")
if col_orden_tinf is None: missing.append("orden en tiempos informados")
if col_tiempo_real is None: missing.append("columna tiempo en tiempo real")
if col_tiempo_inf is None: missing.append("columna tiempo en tiempos informados")
if col_cantidad_necesaria is None: missing.append("cantidad necesaria en componentes")
if col_cantidad_tomada is None: missing.append("cantidad tomada en componentes")
if col_texto_material is None: missing.append("texto material en componentes")
if col_cant_orden is None: missing.append("cantidad orden en produccion")
if col_cant_buena is None: missing.append("cantidad buena en produccion")

if missing:
    st.error("No se pudieron detectar automáticamente algunas columnas necesarias:")
    st.write(missing)
    st.write("Columnas detectadas por archivo:")
    st.write("Producción:", list(df_prod.columns))
    st.write("Componentes:", list(df_comp.columns))
    st.write("Tiempo Real:", list(df_tr.columns))
    st.write("Tiempos Informados:", list(df_tinf.columns))
    st.stop()

# ---------------- Preparar estructuras de resultados ----------------
margen_inf = margen_inferior / 100.0
margen_sup = margen_superior / 100.0

resultados_materiales = []
resultados_tiempos = []

# ---------------- Procesar cada orden ----------------
ordenes = sorted(df_prod[col_orden_prod].dropna().unique())

for orden in ordenes:
    # info produccion
    prod_rows = df_prod[df_prod[col_orden_prod] == orden]
    if prod_rows.empty:
        continue
    prod = prod_rows.iloc[0]
    cantidad_orden = float(prod.get(col_cant_orden, 0) or 0)
    cantidad_buena = float(prod.get(col_cant_buena, 0) or 0)
    if cantidad_orden == 0:
        continue
    relacion = cantidad_buena / cantidad_orden

    # materiales
    comps = df_comp[df_comp[col_orden_comp] == orden].copy()
    if not comps.empty:
        # convertir cantidades a numericas (robusto)
        comps[col_cantidad_necesaria] = pd.to_numeric(comps[col_cantidad_necesaria].astype(str).str.replace(",", "."), errors="coerce").fillna(0)
        comps[col_cantidad_tomada] = pd.to_numeric(comps[col_cantidad_tomada].astype(str).str.replace(",", "."), errors="coerce").fillna(0)

        comps["esperado"] = comps[col_cantidad_necesaria] * relacion
        comps["desvio"] = comps[col_cantidad_tomada] - comps["esperado"]
        comps["pct_desvio"] = comps.apply(lambda r: (r["desvio"] / r["esperado"] * 100) if r["esperado"] != 0 else 0, axis=1)
        comps["estado"] = comps["pct_desvio"].apply(lambda p: "🟢 OK" if (margen_inf*100) <= p <= (margen_sup*100) else "🔴 REVISAR")
        # seleccionar columnas de salida con nombres legibles
        out_mat = comps[[col_orden_comp, col_texto_material, col_cantidad_necesaria, col_cantidad_tomada, "esperado", "desvio", "pct_desvio", "estado"]].copy()
        out_mat.columns = ["orden","texto_material","cantidad_necesaria","cantidad_tomada","esperado","desvio","%_desvio","estado"]
        resultados_materiales.append(out_mat)

    # tiempos: sumar todos los registros por orden (robusto)
    t_real_rows = df_tr[df_tr[col_orden_tr] == orden]
    t_inf_rows = df_tinf[df_tinf[col_orden_tinf] == orden]

    tiempo_real = 0.0
    tiempo_inf = 0.0
    if not t_real_rows.empty:
        tiempo_real = convertir_tiempo_serie(t_real_rows[col_tiempo_real]).sum()
    if not t_inf_rows.empty:
        tiempo_inf = convertir_tiempo_serie(t_inf_rows[col_tiempo_inf]).sum()

    desvio_t = tiempo_inf - tiempo_real
    pct_desvio_t = (desvio_t / tiempo_real * 100) if tiempo_real != 0 else (100.0 if tiempo_inf != 0 else 0.0)
    estado_t = "🟢 OK" if (margen_inf*100) <= pct_desvio_t <= (margen_sup*100) else "🔴 REVISAR"

    resultados_tiempos.append({
        "orden": orden,
        "tiempo_real": tiempo_real,
        "tiempo_informado": tiempo_inf,
        "desvio": desvio_t,
        "%_desvio": pct_desvio_t,
        "estado": estado_t
    })

# ---------------- Consolidar resultados ----------------
if resultados_materiales:
    df_res_mat = pd.concat(resultados_materiales, ignore_index=True)
else:
    df_res_mat = pd.DataFrame(columns=["orden","texto_material","cantidad_necesaria","cantidad_tomada","esperado","desvio","%_desvio","estado"])

df_res_tiempos = pd.DataFrame(resultados_tiempos)

# ---------------- Mostrar resumen y métricas ----------------
st.markdown("## ✅ Resumen")
c1, c2, c3 = st.columns(3)
c1.metric("Órdenes analizadas", len(ordenes))
n_desv_mat = int((df_res_mat["estado"] == "🔴 REVISAR").sum()) if not df_res_mat.empty else 0
n_desv_t = int((df_res_tiempos["estado"] == "🔴 REVISAR").sum()) if not df_res_tiempos.empty else 0
c2.metric("Materiales a revisar", n_desv_mat)
c3.metric("Órdenes con desvío en tiempos", n_desv_t)

st.divider()

# tablas en pestañas
tab_mat, tab_time, tab_all = st.tabs(["Materiales", "Tiempos", "Exportar"])
with tab_mat:
    st.subheader("Desvíos en materiales")
    st.dataframe(df_res_mat.sort_values(["orden","%_desvio"], ascending=[True, False]).reset_index(drop=True), use_container_width=True)

with tab_time:
    st.subheader("Desvíos en tiempos")
    st.dataframe(df_res_tiempos.sort_values("%_desvio", ascending=False).reset_index(drop=True), use_container_width=True)

with tab_all:
    st.subheader("Exportar resultados")
    st.write("Descargá un Excel con hojas: materiales, tiempos")
    excel_bytes = df_to_excel_bytes({"materiales": df_res_mat, "tiempos": df_res_tiempos})
    st.download_button("⬇️ Descargar resultados (Excel)", data=excel_bytes, file_name="analisis_produccion_resultados.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

st.markdown("---")
st.info("Notas: el app detecta columnas automáticamente. Si algo no se detecta correctamente, revisá las primeras filas en los previews y ajustá el nombre de la columna en el Excel (o avisame y lo adapto).")
