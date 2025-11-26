import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="Analizador Producción (Materiales & Tiempos)", layout="wide")
st.title("🔎 Analizador Automático de Producción — Materiales y Tiempos")

# ---------------- helpers ----------------
def leer_mejor_excel(file_buffer):
    """Intenta elegir la mejor hoja y retornar DataFrame."""
    xl = pd.ExcelFile(file_buffer)
    # Si sólo tiene una hoja, usarla
    if len(xl.sheet_names) == 1:
        try:
            return xl.parse(xl.sheet_names[0], header=0)
        except Exception:
            return xl.parse(xl.sheet_names[0], header=None)
    # Si varias hojas, buscar la que tenga >1 columna y nombres plausibles
    for sheet in xl.sheet_names:
        try:
            df = xl.parse(sheet_name=sheet, header=0)
            if df.shape[1] > 1:
                return df
        except Exception:
            continue
    # fallback: primera hoja
    try:
        return xl.parse(xl.sheet_names[0], header=0)
    except Exception:
        return xl.parse(xl.sheet_names[0], header=None)


def normalizar_cols(df):
    cols = df.columns.astype(str)
    cols = cols.str.strip().str.lower()
    cols = cols.str.replace("á","a").str.replace("é","e").str.replace("í","i").str.replace("ó","o").str.replace("ú","u")
    cols = cols.str.replace("%","").str.replace(".","").str.replace("/","_")
    cols = cols.str.replace(r"\s+", "_", regex=True)
    df = df.copy()
    df.columns = cols
    return df


def detectar_columna_por_claves(df, claves):
    """Devuelve la primera columna de df que contiene alguna de las claves (ya normalizadas)."""
    if df is None:
        return None
    for clave in claves:
        for c in df.columns:
            if clave in c:
                return c
    return None


def convertir_tiempo_serie(s):
    """
    Convierte una Series textual a horas (float).
    Acepta formatos:
      - '3,25' -> 3.25
      - '3.25' -> 3.25
      - '3:15' -> 3.25 (3h15m -> 3.25)
      - '195' -> 195 (se mantiene)
    Errores -> 0
    """
    s = s.fillna("").astype(str).str.strip()
    if s.empty:
        return pd.Series(dtype=float)

    # detectar hh:mm
    mask_hm = s.str.contains(":")
    result = pd.Series(0.0, index=s.index)

    if mask_hm.any():
        parts = s[mask_hm].str.split(":", expand=True)
        horas = pd.to_numeric(parts[0], errors="coerce").fillna(0)
        minutos = pd.to_numeric(parts[1], errors="coerce").fillna(0)
        result.loc[mask_hm] = horas + minutos / 60.0

    # resto: coma -> punto y convertir
    rest_idx = ~mask_hm
    rest = s[rest_idx].str.replace(",", ".")
    restnum = pd.to_numeric(rest, errors="coerce").fillna(0.0)
    result.loc[rest_idx] = restnum
    return result


def df_to_excel_bytes(dfs):
    """
    dfs: dict of {sheetname: df}
    returns bytes for download
    """
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
        for name, df in dfs.items():
            df.to_excel(writer, sheet_name=name[:31], index=False)
        writer.save()
    buf.seek(0)
    return buf.getvalue()


# ---------------- Sidebar: upload & options ----------------
st.sidebar.header("1) Carga de archivos")
tiempo_real_file = st.sidebar.file_uploader("Tiempo real (Excel)", type=["xlsx","xls"])
componentes_file = st.sidebar.file_uploader("Componentes (Excel)", type=["xlsx","xls"])
tiempos_inf_file = st.sidebar.file_uploader("Tiempos informados (Excel)", type=["xlsx","xls"])
produccion_file = st.sidebar.file_uploader("Producción (Excel)", type=["xlsx","xls"])

st.sidebar.markdown("---")
st.sidebar.header("2) Parámetros")
margen_inferior = st.sidebar.number_input("Margen inferior (%)", value=-10.0, step=1.0)
margen_superior = st.sidebar.number_input("Margen superior (%)", value=10.0, step=1.0)
st.sidebar.markdown("Los márgenes se aplican como tolerancia relativa para desvíos porcentuales.")

st.sidebar.markdown("---")
st.sidebar.header("3) Export")
# export handled later

# Require all files
if not (tiempo_real_file and componentes_file and tiempos_inf_file and produccion_file):
    st.info("Sube los 4 archivos (Tiempo real, Componentes, Tiempos informados, Producción) en la barra lateral para comenzar.")
    st.stop()

# ---------------- Read & normalize ----------------
with st.spinner("Leyendo archivos..."):
    raw_tr = leer_mejor_excel(tiempo_real_file)
    raw_comp = leer_mejor_excel(componentes_file)
    raw_tinf = leer_mejor_excel(tiempos_inf_file)
    raw_prod = leer_mejor_excel(produccion_file)

    st.write("Columnas TIEMPO REAL:", df_tr.columns.tolist())
st.write("Columnas COMPONENTES:", df_comp.columns.tolist())
st.write("Columnas TIEMPOS INFORMADOS:", df_tinf.columns.tolist())
st.write("Columnas PRODUCCIÓN:", df_prod.columns.tolist())

    # handle special case: if tiempo real has top-title and headers start at row 3 (observado)
    cols_lower = [str(c).strip().lower() for c in raw_tr.columns.astype(str)]
    if all(("unnamed" in c or "tiempo real por" in c) for c in cols_lower[:3]):
        # try parse with header=3
        try:
            raw_tr = pd.ExcelFile(tiempo_real_file).parse(sheet_name=0, header=3)
        except Exception:
            pass

    df_tr = normalizar_cols(raw_tr)
    df_comp = normalizar_cols(raw_comp)
    df_tinf = normalizar_cols(raw_tinf)
    df_prod = normalizar_cols(raw_prod)

st.success("Archivos leídos y normalizados.")

# ---------------- previews for inspection ----------------
st.markdown("### Previews")
tab_a, tab_b, tab_c, tab_d = st.tabs(["Tiempo Real (preview)","Componentes (preview)","Tiempos Informados (preview)","Producción (preview)"])
with tab_a:
    st.dataframe(df_tr.head(20))
with tab_b:
    st.dataframe(df_comp.head(10))
with tab_c:
    st.dataframe(df_tinf.head(10))
with tab_d:
    st.dataframe(df_prod.head(10))

# ---------------- Detect columns automatically ----------------
# Key word lists
kw_orden = ["orden", "n_orden", "nro_orden", "op", "orden_produccion", "ordendeproduccion","ordenproduccion"]
kw_tiempo = ["tiempo","duracion","hora","horas","hrs","hraa","tiempo_maquina","tiempo_real","tiempo_informado","activ"]
kw_cant = ["cantidad","cant","cantidad_necesaria","cantidad_necesaria","cantidad_orden","cantidad_buena","cantidad_buena_confirmada","cantidadorden"]

# detect order columns
col_orden_prod = detectar_columna_por_claves(df_prod, kw_orden)
col_orden_comp = detectar_columna_por_claves(df_comp, kw_orden)
col_orden_tr = detectar_columna_por_claves(df_tr, kw_orden)
col_orden_tinf = detectar_columna_por_claves(df_tinf, kw_orden)

# detect time columns
col_tiempo_real = detectar_columna_por_claves(df_tr, kw_tiempo)
col_tiempo_inf = detectar_columna_por_claves(df_tinf, kw_tiempo)

# detect comp quantity columns
col_cant_necesaria = detectar_columna_por_claves(df_comp, ["necesari","cantidad_necesaria","cantidad"])
col_cant_tomada = detectar_columna_por_claves(df_comp, ["tomad","cantidad_tomada","cantidad"])
col_texto_mat = detectar_columna_por_claves(df_comp, ["texto","material","descripcion","texto_breve"])

# detect prod qty columns
col_cant_orden = detectar_columna_por_claves(df_prod, ["cantidad_orden","cantidadorden","cantidad"])
col_cant_buena = detectar_columna_por_claves(df_prod, ["cantidad_buena","cantidadbuena","buena","cantidad_buena_confirmada","cantidad_buena_confirmada"])

# detect prod text
col_texto_prod = detectar_columna_por_claves(df_prod, ["texto","material","descripcion"])

# Validate minimal columns exist
missing = []
if col_orden_prod is None: missing.append("orden en produccion")
if col_orden_comp is None: missing.append("orden en componentes")
if col_orden_tr is None: missing.append("orden en tiempo real")
if col_orden_tinf is None: missing.append("orden en tiempos informados")
if col_tiempo_real is None: missing.append("tiempo en tiempo real")
if col_tiempo_inf is None: missing.append("tiempo en tiempos informados")
if col_cant_necesaria is None: missing.append("cantidad necesaria en componentes")
if col_cant_tomada is None: missing.append("cantidad tomada en componentes")
if col_texto_mat is None: missing.append("texto material en componentes")
if col_cant_orden is None: missing.append("cantidad orden en produccion")
if col_cant_buena is None: missing.append("cantidad buena en produccion")

if missing:
    st.error("No se detectaron automáticamente algunas columnas necesarias:")
    st.write(missing)
    st.write("Columnas detectadas por archivo (normalizadas):")
    st.write("Producción:", list(df_prod.columns))
    st.write("Componentes:", list(df_comp.columns))
    st.write("Tiempo Real:", list(df_tr.columns))
    st.write("Tiempos Informados:", list(df_tinf.columns))
    st.stop()

# ---------------- Prepare results ----------------
margen_inf = margen_inferior / 100.0
margen_sup = margen_superior / 100.0

resultados_materiales = []
resultados_tiempos = []

ordenes = sorted(df_prod[col_orden_prod].dropna().unique())

# ---------------- Process every order ----------------
with st.spinner("Analizando órdenes..."):
    for orden in ordenes:
        # production row (take first)
        prod_rows = df_prod[df_prod[col_orden_prod] == orden]
        if prod_rows.empty:
            continue
        prod = prod_rows.iloc[0]
        # numeric robust
        cantidad_orden = float(pd.to_numeric(prod.get(col_cant_orden, 0), errors="coerce") or 0)
        cantidad_buena = float(pd.to_numeric(prod.get(col_cant_buena, 0), errors="coerce") or 0)
        if cantidad_orden == 0:
            # skip or mark? We'll skip to avoid division by zero
            continue
        relacion = cantidad_buena / cantidad_orden

        # --- Materials ---
        comps = df_comp[df_comp[col_orden_comp] == orden].copy()
        if not comps.empty:
            # numeric conversion
            comps[col_cant_necesaria] = pd.to_numeric(comps[col_cant_necesaria].astype(str).str.replace(",", "."), errors="coerce").fillna(0.0)
            comps[col_cant_tomada] = pd.to_numeric(comps[col_cant_tomada].astype(str).str.replace(",", "."), errors="coerce").fillna(0.0)

            comps["esperado"] = comps[col_cant_necesaria] * relacion
            comps["desvio"] = comps[col_cant_tomada] - comps["esperado"]
            comps["pct_desvio"] = comps.apply(lambda r: (r["desvio"] / r["esperado"] * 100) if r["esperado"] != 0 else 0.0, axis=1)

            def estado_mat(pct):
                if pd.isna(pct):
                    return "🟡 INSUFICIENTE"
                return "🟢 OK" if (margen_inf*100) <= pct <= (margen_sup*100) else "🔴 REVISAR"

            comps["estado"] = comps["pct_desvio"].apply(estado_mat)

            out_mat = comps[[col_orden_comp, col_texto_mat, col_cant_necesaria, col_cant_tomada, "esperado", "desvio", "pct_desvio", "estado"]].copy()
            out_mat.columns = ["orden", "texto_material", "cantidad_necesaria", "cantidad_tomada", "esperado", "desvio", "%_desvio", "estado"]
            resultados_materiales.append(out_mat)

        # --- Tiempos ---
        t_real_rows = df_tr[df_tr[col_orden_tr] == orden]
        t_inf_rows = df_tinf[df_tiempo_inf if (col_orden_tinf is None) else col_orden_tinf] if False else None  # placeholder to keep clarity
        # fix correct filter for t_inf_rows
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
            "tiempo_real": round(float(tiempo_real), 4),
            "tiempo_informado": round(float(tiempo_inf), 4),
            "desvio": round(float(desvio_t), 4),
            "%_desvio": round(float(pct_desvio_t), 4),
            "estado": estado_t
        })

# ---------------- Consolidate ----------------
if resultados_materiales:
    df_res_mat = pd.concat(resultados_materiales, ignore_index=True)
else:
    df_res_mat = pd.DataFrame(columns=["orden","texto_material","cantidad_necesaria","cantidad_tomada","esperado","desvio","%_desvio","estado"])

df_res_tiempos = pd.DataFrame(resultados_tiempos)

# ---------------- Metrics & UI ----------------
st.markdown("## Resultados")
c1, c2, c3 = st.columns(3)
c1.metric("Órdenes analizadas", len(ordenes))
n_desv_mat = int((df_res_mat["estado"] == "🔴 REVISAR").sum()) if not df_res_mat.empty else 0
n_desv_t = int((df_res_tiempos["estado"] == "🔴 REVISAR").sum()) if not df_res_tiempos.empty else 0
c2.metric("Materiales a revisar", n_desv_mat)
c3.metric("Órdenes con desvío tiempo", n_desv_t)

st.divider()

# ---------------- Tabs: Materials & Times ----------------
tab1, tab2, tab3 = st.tabs(["Materiales", "Tiempos", "Exportar"])
with tab1:
    st.subheader("Desvíos en materiales")
    st.write("Columnas: orden | texto_material | cantidad_necesaria | cantidad_tomada | esperado | desvio | %_desvio | estado")
    if df_res_mat.empty:
        st.info("No se encontraron componentes para las órdenes procesadas.")
    else:
        # ordenar mostrando los mayores %_desvio primero
        st.dataframe(df_res_mat.sort_values("%_desvio", ascending=False).reset_index(drop=True), use_container_width=True)

with tab2:
    st.subheader("Desvíos en tiempos")
    if df_res_tiempos.empty:
        st.info("No se encontraron registros de tiempos.")
    else:
        st.dataframe(df_res_tiempos.sort_values("%_desvio", ascending=False).reset_index(drop=True), use_container_width=True)

with tab3:
    st.subheader("Exportar resultados")
    st.write("Descargá un Excel con hojas `materiales` y `tiempos`.")
    excel_bytes = df_to_excel_bytes({"materiales": df_res_mat, "tiempos": df_res_tiempos})
    st.download_button("⬇️ Descargar resultados (Excel)", data=excel_bytes, file_name="analisis_produccion_resultados.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

st.markdown("---")
st.info("🛈 Notas: 1) El detector automático busca columnas por palabras clave. 2) Si algo no se detecta o hay inconsistencias, revisá los previews arriba y ajustá el Excel o avisame para adaptar las claves.")
