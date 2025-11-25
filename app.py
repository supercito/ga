
import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO

st.set_page_config(page_title="Control Producción — SAP vs Real", layout="wide")

st.title("Control de Producción y Consumo de Materiales (SAP vs Real)")

st.markdown("""Sube los 4 archivos Excel. La app detecta columnas automáticamente pero puedes ajustar el mapeo si los nombres reales son distintos.
""")

# --- Uploads
uploaded_tr = st.file_uploader("Tiempo real por orden de producción (Excel)", type=["xlsx"], key="tr")
uploaded_ti = st.file_uploader("Tiempos informados / SAP (Excel)", type=["xlsx"], key="ti")
uploaded_prod = st.file_uploader("Producción (Excel)", type=["xlsx"], key="prod")
uploaded_comp = st.file_uploader("Componentes / Materiales (Excel)", type=["xlsx"], key="comp")

def read_all_sheets(uploaded):
    xls = pd.ExcelFile(uploaded)
    frames = []
    for s in xls.sheet_names:
        df = xls.parse(s)
        df["_sheet_"] = s
        frames.append(df)
    if len(frames)==1:
        return frames[0]
    return pd.concat(frames, ignore_index=True)

if st.button("Cargar y preparar datos"):
    if not all([uploaded_tr, uploaded_ti, uploaded_prod, uploaded_comp]):
        st.error("Por favor sube los 4 archivos antes de continuar.")
        st.stop()

    tr_raw = read_all_sheets(uploaded_tr)
    ti_raw = read_all_sheets(uploaded_ti)
    prod_raw = read_all_sheets(uploaded_prod)
    comp_raw = read_all_sheets(uploaded_comp)

    # Normalizar nombres de columnas (no destructivo)
    def normalize_cols(df):
        df = df.copy()
        df.columns = [str(c).strip().lower().replace(" ", "_").replace("\n","_") for c in df.columns]
        return df

    tr = normalize_cols(tr_raw)
    ti = normalize_cols(ti_raw)
    prod = normalize_cols(prod_raw)
    comp = normalize_cols(comp_raw)

    st.subheader("Columnas detectadas (muestra)")
    col1, col2 = st.columns(2)
    with col1:
        st.write("Tiempo real (primeras columnas):")
        st.write(tr.columns.tolist()[:30])
        st.dataframe(tr.head(3))
    with col2:
        st.write("Tiempos informados (primeras columnas):")
        st.write(ti.columns.tolist()[:30])
        st.dataframe(ti.head(3))

    st.write("Producción (columnas):", prod.columns.tolist()[:40])
    st.write("Componentes (columnas):", comp.columns.tolist()[:40])

    # --- Mapeo de columnas (permitir override)
    st.markdown("### Mapeo de columnas (ajusta si es necesario)")
    order_col = st.text_input("Nombre columna orden (order_id)", value="tiempo_real_por_orden_de_producción")
    time_real_col = st.text_input("Nombre columna tiempo real", value="tiempo_real_por_orden_de_producción")
    time_reported_col = st.text_input("Nombre columna tiempo reportado (SAP)", value="time_reported")
    prod_needed_col = st.text_input("Nombre columna producción necesaria (planificada)", value="cantidad_orden")
    prod_reported_col = st.text_input("Nombre columna producción reportada (realizada)", value="prod_reported")
    material_col = st.text_input("Nombre columna material_id en componentes", value="material")
    qty_unit_col = st.text_input("Nombre columna consumo por unidad en componentes", value="qty_per_unit")
    qty_taken_col = st.text_input("Nombre columna cantidad tomada/consumida en componentes", value="cantidad_tomada")

    # Forzar strings en order_id y renombrar si existen las columnas
    def safe_rename(df, orig, new):
        df = df.copy()
        if orig in df.columns:
            df = df.rename(columns={orig:new})
        return df

    tr = safe_rename(tr, order_col, "order_id")
    ti = safe_rename(ti, order_col, "order_id")
    prod = safe_rename(prod, order_col, "order_id")
    comp = safe_rename(comp, order_col, "order_id")

    tr["order_id"] = tr["order_id"].astype(str)
    ti["order_id"] = ti["order_id"].astype(str)
    prod["order_id"] = prod["order_id"].astype(str)
    comp["order_id"] = comp["order_id"].astype(str)

    # rename time/cols if exist
    tr = safe_rename(tr, time_real_col, "time_real")
    ti = safe_rename(ti, time_reported_col, "time_reported")
    prod = safe_rename(prod, prod_needed_col, "prod_needed")
    prod = safe_rename(prod, prod_reported_col, "prod_reported")
    comp = safe_rename(comp, material_col, "material_id")
    comp = safe_rename(comp, qty_unit_col, "qty_per_unit")
    comp = safe_rename(comp, qty_taken_col, "qty_taken")

    # convert numeric columns where applicable
    def to_numeric_if_exists(df, cols):
        for c in cols:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c].astype(str).str.replace(",", "."), errors="coerce")
    to_numeric_if_exists(tr, ["time_real"]) 
    to_numeric_if_exists(ti, ["time_reported", "prod_reported"]) 
    to_numeric_if_exists(prod, ["prod_needed", "prod_reported"]) 
    to_numeric_if_exists(comp, ["qty_per_unit", "qty_taken"]) 

    # --- Merge principal por orden ---
    main = tr[ [c for c in tr.columns if c in ["order_id","time_real"] or True] ].drop_duplicates(subset=["order_id"]).merge(
        ti[[c for c in ti.columns if c in ["order_id","time_reported","prod_reported"] or True]].drop_duplicates(subset=["order_id"]),
        on="order_id", how="outer"
    )
    main = main.merge(prod.drop_duplicates(subset=["order_id"]), on="order_id", how="outer")

    # Calculos tiempos
    main["time_real"] = pd.to_numeric(main.get("time_real"), errors="coerce")
    main["time_reported"] = pd.to_numeric(main.get("time_reported"), errors="coerce")
    main["time_diff"] = main["time_real"] - main["time_reported"]
    main["time_diff_pct"] = main.apply(lambda r: (r["time_diff"]/r["time_reported"]) if pd.notna(r["time_reported"]) and r["time_reported"]!=0 else np.nan, axis=1)

    # Calculos producción
    main["prod_needed"] = pd.to_numeric(main.get("prod_needed"), errors="coerce")
    main["prod_reported"] = pd.to_numeric(main.get("prod_reported"), errors="coerce")
    main["prod_diff"] = main["prod_reported"] - main["prod_needed"]
    main["prod_diff_pct"] = main.apply(lambda r: (r["prod_diff"]/r["prod_needed"]) if pd.notna(r["prod_needed"]) and r["prod_needed"]!=0 else np.nan, axis=1)

    st.subheader("Resumen por orden (tiempos y producción)")
    st.dataframe(main.head(200))

    # --- Componentes y consumo ---
    # intentar inferir qty_per_unit si no existe: usar 'cantidad' columna u otra heurística
    if "qty_per_unit" not in comp.columns or comp["qty_per_unit"].isna().all():
        if "cantidad" in comp.columns:
            comp["cantidad"] = pd.to_numeric(comp["cantidad"].astype(str).str.replace(",", "."), errors="coerce")
        comp = comp.merge(main[["order_id","prod_needed","prod_reported"]], on="order_id", how="left")
        if "cantidad" in comp.columns:
            comp["qty_per_unit_inferred"] = np.where((comp["prod_needed"].notna()) & (comp["prod_needed"]>0), comp["cantidad"]/comp["prod_needed"], np.nan)
        else:
            comp["qty_per_unit_inferred"] = np.nan
        comp["qty_per_unit"] = comp.get("qty_per_unit", pd.Series(np.nan)).fillna(comp["qty_per_unit_inferred"])
    else:
        comp = comp.merge(main[["order_id","prod_needed","prod_reported"]], on="order_id", how="left")

    if "qty_taken" not in comp.columns and "cantidad" in comp.columns:
        comp["qty_taken"] = pd.to_numeric(comp["cantidad"].astype(str).str.replace(",", "."), errors="coerce")
    else:
        if "qty_taken" in comp.columns:
            comp["qty_taken"] = pd.to_numeric(comp["qty_taken"].astype(str).str.replace(",", "."), errors="coerce")

    comp["expected_by_needed"] = np.where(comp["prod_needed"].notna() & comp["qty_per_unit"].notna(), comp["prod_needed"] * comp["qty_per_unit"], np.nan)
    comp["expected_by_reported"] = np.where(comp["prod_reported"].notna() & comp["qty_per_unit"].notna(), comp["prod_reported"] * comp["qty_per_unit"], np.nan)

    comp["mat_diff_vs_needed"] = np.where(comp["qty_taken"].notna(), comp["qty_taken"] - comp["expected_by_needed"], np.nan)
    comp["mat_diff_vs_reported"] = np.where(comp["qty_taken"].notna(), comp["qty_taken"] - comp["expected_by_reported"], np.nan)

    def safe_pct(numer, denom):
        try:
            if pd.isna(numer) or pd.isna(denom) or denom==0:
                return np.nan
            return numer/denom
        except:
            return np.nan

    comp["mat_diff_pct_vs_needed"] = comp.apply(lambda r: safe_pct(r["mat_diff_vs_needed"], r["expected_by_needed"]), axis=1)
    comp["mat_diff_pct_vs_reported"] = comp.apply(lambda r: safe_pct(r["mat_diff_vs_reported"], r["expected_by_reported"]), axis=1)

    ALERT_PCT = st.number_input("Umbral de alerta (porcentaje)", min_value=0.0, max_value=1.0, value=0.05, step=0.01)

    comp["alert_vs_needed"] = comp["mat_diff_pct_vs_needed"].abs() > ALERT_PCT
    comp["alert_vs_reported"] = comp["mat_diff_pct_vs_reported"].abs() > ALERT_PCT

    st.subheader("Análisis de componentes y desviaciones")
    st.dataframe(comp.head(200))

    materials_alerts = comp[comp["alert_vs_needed"]==True].sort_values(by="mat_diff_pct_vs_needed", ascending=False)
    st.subheader("Materiales que exceden umbral vs necesario")
    st.dataframe(materials_alerts)

    # Ordenes con alertas
    order_summary = comp.groupby("order_id").agg(total_expected_by_needed=("expected_by_needed","sum"), total_taken=("qty_taken","sum"), total_diff_vs_needed=("mat_diff_vs_needed","sum"), max_mat_diff_pct_vs_needed=("mat_diff_pct_vs_needed","max")).reset_index()
    order_summary["order_alert"] = order_summary["max_mat_diff_pct_vs_needed"].abs() > ALERT_PCT
    orders_alerts = order_summary[order_summary["order_alert"]==True].copy()

    st.subheader("Órdenes que requieren corrección por materiales")
    st.dataframe(orders_alerts)

    # Generar recomendaciones básicas
    st.subheader("Recomendaciones automáticas (sugeridas)")
    recs = []

    # Si tiempo reportado difiere mucho -> sugerir revisar tiempo en SAP o cronometraje
    for _,r in main.iterrows():
        if pd.notna(r.get("time_diff_pct")) and abs(r.get("time_diff_pct"))>0.2:
            recs.append({"order_id": r.get("order_id"), "tipo":"tiempo","mensaje": f"Revisar tiempo: diferencia {r.get('time_diff_pct'):.2%}"})

    # Si producción reportada difiere -> sugerir revisar lote/registro
    for _,r in main.iterrows():
        if pd.notna(r.get("prod_diff_pct")) and abs(r.get("prod_diff_pct"))>0.05:
            recs.append({"order_id": r.get("order_id"), "tipo":"produccion","mensaje": f"Revisar producción: diferencia {r.get('prod_diff_pct'):.2%}"})

    # Si material con alerta -> sugerir revisar consumo estándar o toma de stock
    for _,m in materials_alerts.iterrows():
        recs.append({"order_id": m.get("order_id"), "tipo":"material","material_id": m.get("material_id"), "mensaje": f"Revisar consumo del material (desvío {m.get('mat_diff_pct_vs_needed'):.2%})"})

    recs_df = pd.DataFrame(recs)
    if not recs_df.empty:
        st.dataframe(recs_df)
    else:
        st.write("No hay recomendaciones automáticas basadas en los umbrales actuales.")

    # --- Descargas ---
    def to_excel_bytes(dfs_dict):
        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            for name,df in dfs_dict.items():
                try:
                    df.to_excel(writer, sheet_name=name[:31], index=False)
                except Exception as e:
                    df.head(100).to_excel(writer, sheet_name=name[:31], index=False)
        return output.getvalue()

    excel_bytes = to_excel_bytes({"main": main, "components": comp, "materials_alerts": materials_alerts, "orders_alerts": orders_alerts, "recs": recs_df})
    st.download_button("Descargar reporte completo (Excel)", excel_bytes, file_name="reporte_produccion_materiales.xlsx")

    st.success("Procesamiento completo.")
