# app.py
import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="Analizador Producción (Materiales & Tiempos)", layout="wide")
st.title("🔎 Analizador Automático de Producción — Materiales y Tiempos")

# ---------------- Helpers ----------------
def leer_mejor(file_buffer):
    """Lee la mejor hoja posible del Excel. Intenta header=0, si parece título intenta header=3."""
    xl = pd.ExcelFile(file_buffer)
    # Primero intento leer la primera hoja con header=0
    try:
        df = xl.parse(xl.sheet_names[0], header=0)
        # Si tiene muchas 'Unnamed' al inicio, intentar header=3 (caso reportes exportados)
        cols = [str(c).strip().lower() for c in df.columns.astype(str)]
        unnamed_count = sum(1 for c in cols[:3] if "unnamed" in c or c == "")
        if unnamed_count >= 2:
            # reparsear con header=3 si existe
            try:
                df2 = xl.parse(xl.sheet_names[0], header=3)
                if df2.shape[1] > 1:
                    return df2
            except Exception:
                pass
        return df
    except Exception:
        # fallback: leer sin header
        try:
            return xl.parse(xl.sheet_names[0], header=None)
        except Exception:
            raise

def normalizar_cols(df):
    df = df.copy()
    cols = df.columns.astype(str)
    cols = cols.str.strip().str.lower()
    cols = cols.str.replace("á","a").str.replace("é","e").str.replace("í","i").str.replace("ó","o").str.replace("ú","u")
    cols = cols.str.replace("%","").str.replace(".","").str.replace("/","_")
    cols = cols.str.replace(r"\s+", "_", regex=True)
    df.columns = cols
    return df

def detectar_columna_por_claves(df, claves):
    if df is None:
        return None
    for clave in claves:
        for c in df.columns:
            if clave in c:
                return c
    return None

def convertir_tiempo_serie(s):
    """Convierte strings a horas float: '3,25'->3.25, '3:15'->3.25, numeric kept."""
    s = s.fillna("").astype(str).str.strip()
    if s.empty:
        return pd.Series(dtype=float)
    mask_hm = s.str.contains(":")
    res = pd.Series(0.0, index=s.index)
    if mask_hm.any():
        parts = s[mask_hm].str.split(":", expand=True)
        horas = pd.to_numeric(parts[0], errors="coerce").fillna(0)
        minutos = pd.to_numeric(parts[1], errors="coerce").fillna(0)
        res.loc[mask_hm] = horas + minutos / 60.0
    rest_idx = ~mask_hm
    rest = s[rest_idx].str.replace(",", ".")
    restnum = pd.to_numeric(rest, errors="coerce").fillna(0.0)
    res.loc[rest_idx] = restnum
    return res

def df_to_excel_bytes(dfs):
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
        for name, df in dfs.items():
            df.to_excel(writer, sheet_name=str(name)[:31], index=False)
        writer.save()
    buf.seek(0)
    return buf.getvalue()

# ---------------- Sidebar: uploads & params ----------------
st.sidebar.header("1) Subir archivos (Excel)")
tiempo_real_file = st.sidebar.file_uploader("Tiempo real", type=["xlsx","xls"])
componentes_file = st.sidebar.file_uploader("Componentes", type=["xlsx","xls"])
tiempos_inf_file = st.sidebar.file_uploader("Tiempos informados", type=["xlsx","xls"])
produccion_file = st.sidebar.file_uploader("Producción", type=["xlsx","xls"])

st.sidebar.markdown("---")
st.sidebar.header("2) Parámetros")
margen_inferior = st.sidebar.number_input("Margen inferior (%)", value=-10.0, step=1.0)
margen_superior = st.sidebar.number_input("Margen superior (%)", value=10.0, step=1.0)
st.sidebar.markdown("Los márgenes se usan para decidir OK / REVISAR sobre desvío porcentual.")

# ---------------- Require files ----------------
if not (tiempo_real_file and componentes_file and tiempos_inf_file and produccion_file):
    st.info("Sube los 4 archivos en la barra lateral para ejecutar el análisis.")
    st.stop()

# ---------------- Read files robustly ----------------
with st.spinner("Leyendo y detectando hojas..."):
    raw_tr = leer_mejor(tiempo_real_file)
    raw_comp = leer_mejor(componentes_file)
    raw_tinf = leer_mejor(tiempos_inf_file)
    raw_prod = leer_mejor(produccion_file)

# Show previews and original columns (helpful to debug)
st.markdown("## Previews y columnas detectadas (originales)")
tab_a, tab_b, tab_c, tab_d = st.tabs(["Tiempo Real","Componentes","Tiempos Informados","Producción"])
with tab_a:
    st.subheader("Preview Tiempo Real")
    st.dataframe(raw_tr.head(10))
    st.write("Columnas (originales):", list(raw_tr.columns.astype(str)))
with tab_b:
    st.subheader("Preview Componentes")
    st.dataframe(raw_comp.head(8))
    st.write("Columnas (originales):", list(raw_comp.columns.astype(str)))
with tab_c:
    st.subheader("Preview Tiempos Informados")
    st.dataframe(raw_tinf.head(8))
    st.write("Columnas (originales):", list(raw_tinf.columns.astype(str)))
with tab_d:
    st.subheader("Preview Producción")
    st.dataframe(raw_prod.head(8))
    st.write("Columnas (originales):", list(raw_prod.columns.astype(str)))

# ---------------- Normalize column names ----------------
df_tr = normalizar_cols(raw_tr)
df_comp = normalizar_cols(raw_comp)
df_tinf = normalizar_cols(raw_tinf)
df_prod = normalizar_cols(raw_prod)

st.success("Columnas normalizadas (minúsculas, sin acentos, espacios->_)")

# ---------------- Detect columns automatically ----------------
kw_orden = ["orden", "n_orden", "nro_orden", "op", "orden_produccion", "ordenproduccion"]
kw_tiempo = ["tiempo","duracion","hora","horas","hrs","tiempo_maquina","activ","activ1","activ_1","actividad"]
kw_cant = ["cantidad","cant","cantidad_necesaria","cantidad_necesaria","cantidad_orden","cantidad_buena","cantidad_buena_confirmada"]

col_orden_prod = detectar_columna_por_claves(df_prod, kw_orden)
col_orden_comp = detectar_columna_por_claves(df_comp, kw_orden)
col_orden_tr = detectar_columna_por_claves(df_tr, kw_orden)
col_orden_tinf = detectar_columna_por_claves(df_tinf, kw_orden)

col_tiempo_real = detectar_columna_por_claves(df_tr, kw_tiempo)
col_tiempo_inf = detectar_columna_por_claves(df_tinf, kw_tiempo)

col_cant_necesaria = detectar_columna_por_claves(df_comp, ["necesari","cantidad_necesaria","cantidad"])
col_cant_tomada = detectar_columna_por_claves(df_comp, ["tomad","cantidad_tomada","cantidad"])
col_texto_mat = detectar_columna_por_claves(df_comp, ["texto","material","descripcion","texto_breve"])

col_cant_orden = detectar_columna_por_claves(df_prod, ["cantidad_orden","cantidadorden","cantidad"])
col_cant_buena = detectar_columna_por_claves(df_prod, ["cantidad_buena","cantidadbuena","buena","cantidad_buena_confirmada","cantidad_buena_confirmada"])
col_texto_prod = detectar_columna_por_claves(df_prod, ["texto","material","descripcion"])

# ---------------- Validate detection ----------------
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
    st.write("Si faltan cosas, revisá los previews. Puedo adaptar las claves si me pegás las columnas exactas.")
    st.stop()

# ---------------- Prepare results lists ----------------
margen_inf = margen_inferior / 100.0
margen_sup = margen_superior / 100.0

resultados_materiales = []
resultados_tiempos = []

# ---------------- Process all orders ----------------
ordenes = sorted(df_prod[col_orden_prod].dropna().unique())

with st.spinner("Analizando todas las órdenes..."):
    for orden in ordenes:
        # production info (take first matching row)
        prod_rows = df_prod[df_prod[col_orden_prod] == orden]
        if prod_rows.empty:
            continue
        prod = prod_rows.iloc[0]
        cantidad_orden = float(pd.to_numeric(prod.get(col_cant_orden, 0), errors="coerce") or 0)
        cantidad_buena = float(pd.to_numeric(prod.get(col_cant_buena, 0), errors="coerce") or 0)
        if cantidad_orden == 0:
            # skip to avoid divide by zero, but record as insufficient if needed
            continue
        relacion = cantidad_buena / cantidad_orden

        # --- Materials ---
        comp_ord = df_comp[df_comp[col_orden_comp] == orden].copy()
        if not comp_ord.empty:
            # numeric conversion robusta
            comp_ord[col_cant_necesaria] = pd.to_numeric(comp_ord[col_cant_necesaria].astype(str).str.replace(",", "."), errors="coerce").fillna(0.0)
            comp_ord[col_cant_tomada] = pd.to_numeric(comp_ord[col_cant_tomada].astype(str).str.replace(",", "."), errors="coerce").fillna(0.0)

            comp_ord["esperado"] = comp_ord[col_cant_necesaria] * relacion
            comp_ord["desvio"] = comp_ord[col_cant_tomada] - comp_ord["esperado"]
            comp_ord["pct_desvio"] = comp_ord.apply(lambda r: (r["desvio"] / r["esperado"] * 100) if r["esperado"] != 0 else float("nan"), axis=1)

            def estado_mat(pct):
                if pd.isna(pct):
                    return "🟡 INSUFICIENTE"
                return "🟢 OK" if (margen_inf*100) <= pct <= (margen_sup*100) else "🔴 REVISAR"

            comp_ord["estado"] = comp_ord["pct_desvio"].apply(estado_mat)

            out_mat = comp_ord[[col_orden_comp, col_texto_mat, col_cant_necesaria, col_cant_tomada, "esperado", "desvio", "pct_desvio", "estado"]].copy()
            out_mat.columns = ["orden", "texto_material", "cantidad_necesaria", "cantidad_tomada", "esperado", "desvio", "%_desvio", "estado"]
            resultados_materiales.append(out_mat)

        # --- Times ---
        t_real_rows = df_tr[df_tr[col_orden_tr] == orden]
        t_inf_rows = df_tinf[df_tiempo_inf if False else col_orden_tinf] if False else None  # placeholder - won't be used
        # correct filter:
        t_inf_rows = df_tinf[df_tinf[col_orden_tinf] == orden]

        tiempo_real = 0.0
        tiempo_inf = 0.0
        if not t_real_rows.empty:
            # convert column values robustly
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

# Tabs
tab_mat, tab_time, tab_export = st.tabs(["Materiales", "Tiempos", "Exportar"])
with tab_mat:
    st.subheader("📦 Desvíos en Materiales")
    if df_res_mat.empty:
        st.info("No se encontraron componentes para las órdenes procesadas.")
    else:
        # resaltado simple: mostrar estado al lado
        st.dataframe(df_res_mat.sort_values("%_desvio", ascending=False).reset_index(drop=True), use_container_width=True)

with tab_time:
    st.subheader("⏱️ Desvíos en Tiempos")
    if df_res_tiempos.empty:
        st.info("No se encontraron registros de tiempos.")
    else:
        st.dataframe(df_res_tiempos.sort_values("%_desvio", ascending=False).reset_index(drop=True), use_container_width=True)

with tab_export:
    st.subheader("📥 Exportar resultados")
    st.write("Descargá un Excel con hojas: materiales, tiempos")
    excel_bytes = df_to_excel_bytes({"materiales": df_res_mat, "tiempos": df_res_tiempos})
    st.download_button("⬇️ Descargar resultados (Excel)", data=excel_bytes, file_name="analisis_produccion_resultados.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

st.markdown("---")
st.info("🛈 Nota: si algo no se detecta correctamente, mirá los previews arriba y pegame las columnas exactas. Puedo adaptar las claves de detección si hace falta.")
