import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="Control de Órdenes", layout="wide")

st.title("📊 Control Automático de Órdenes de Producción")


# ============================================================
# 1) CARGA DE ARCHIVOS
# ============================================================
st.sidebar.header("📁 Cargar Archivos Excel")

file_tr = st.sidebar.file_uploader("Tiempo real", type=["xlsx"])
file_ti = st.sidebar.file_uploader("Tiempo informado", type=["xlsx"])
file_pr = st.sidebar.file_uploader("Producción", type=["xlsx"])
file_cp = st.sidebar.file_uploader("Componentes", type=["xlsx"])

if not all([file_tr, file_ti, file_pr, file_cp]):
    st.warning("Cargá los 4 archivos para continuar…")
    st.stop()


# ============================================================
# 2) LEER ARCHIVOS
# ============================================================
def leer_excel(file):
    df = pd.read_excel(file)
    df.columns = df.columns.str.lower().str.strip()
    return df

tr = leer_excel(file_tr)
ti = leer_excel(file_ti)
pr = leer_excel(file_pr)
cp = leer_excel(file_cp)


# ============================================================
# 3) SELECCIONAR ORDEN
# ============================================================
ordenes = sorted(set(pr["orden de producción"].astype(str)))

orden_sel = st.selectbox("Seleccionar una orden:", ordenes)

st.subheader(f"Orden seleccionada: **{orden_sel}**")

# Filtros
tr_o = tr[tr["orden de producción"].astype(str) == orden_sel]
ti_o = ti[ti["orden"].astype(str) == orden_sel]
pr_o = pr[pr["orden de producción"].astype(str) == orden_sel]
cp_o = cp[cp["orden de producción"].astype(str) == orden_sel]


# ============================================================
# 4) TIEMPOS
# ============================================================
st.header("⏱️ Análisis de Tiempos")

tiempo_real = tr_o["tiempo real por orden de producción"].sum() if not tr_o.empty else None
tiempo_inf = ti_o["duración del tratamiento"].sum() if not ti_o.empty else None

if tiempo_real is None or tiempo_inf is None:
    estado_t = "FALTA INFORMACIÓN"
    diferencia = None
else:
    diferencia = tiempo_inf - tiempo_real
    if abs(diferencia) <= 0.01:
        estado_t = "OK"
    elif diferencia > 0:
        estado_t = "REVISAR (restar horas)"
    else:
        estado_t = "REVISAR (informar horas)"

st.write(f"**Tiempo Real:** {tiempo_real}")
st.write(f"**Tiempo Informado:** {tiempo_inf}")
st.write(f"**Diferencia:** {diferencia}")
st.write(f"**Estado:** {estado_t}")


# ============================================================
# 5) PRODUCCIÓN → RELACIÓN
# ============================================================
st.header("🏭 Producción")

if pr_o.empty:
    st.error("No hay datos de producción para esta orden")
    st.stop()

cantidad_buena = pr_o["cantidad buena confirmada"].iloc[0]
cantidad_orden = pr_o["cantidad orden"].iloc[0]

relacion = cantidad_buena / cantidad_orden

st.write(f"**Cantidad orden:** {cantidad_orden}")
st.write(f"**Cantidad buena:** {cantidad_buena}")
st.write(f"➡️ Relación = {relacion:.4f}")


# ============================================================
# 6) COMPONENTES
# ============================================================
st.header("🧩 Análisis de Componentes")

if cp_o.empty:
    st.info("La orden no tiene componentes.")
else:
    df = cp_o.copy()
    df["relacion"] = relacion
    df["esperado"] = df["cantidad necesaria"] * relacion
    df["diferencia"] = df["cantidad tomada"] - df["esperado"]

    def desvio(row):
        if row["cantidad tomada"] == 0:
            return 1.0
        return abs(row["diferencia"]) / row["esperado"]

    df["desvio_pct"] = df.apply(desvio, axis=1)
    df["estado"] = df["desvio_pct"].apply(lambda x: "OK" if x <= 0.10 else "REVISAR")

    def accion(row):
        if row["estado"] == "OK":
            return ""
        if row["diferencia"] < 0:
            return f"Informar {abs(row['diferencia']):.3f}"
        else:
            return f"Restar {row['diferencia']:.3f}"

    df["acción"] = df.apply(accion, axis=1)

    st.dataframe(
        df[[
            "material",
            "cantidad necesaria",
            "cantidad tomada",
            "esperado",
            "diferencia",
            "desvio_pct",
            "estado",
            "acción"
        ]]
    )


# ============================================================
# 7) DESCARGA DE EXCEL FINAL
# ============================================================
st.header("📥 Descargar reporte")

output = io.BytesIO()

with pd.ExcelWriter(output, engine="openpyxl") as writer:
    # Hoja tiempos
    pd.DataFrame({
        "orden": [orden_sel],
        "tiempo_real": [tiempo_real],
        "tiempo_informado": [tiempo_inf],
        "diferencia": [diferencia],
        "estado": [estado_t]
    }).to_excel(writer, sheet_name="Tiempos", index=False)

    # Hoja producción
    pr_o.assign(relacion=relacion).to_excel(writer, sheet_name="Producción", index=False)

    # Hoja componentes
    if not cp_o.empty:
        df.to_excel(writer, sheet_name="Componentes", index=False)

st.download_button(
    label="⬇ Descargar Excel",
    data=output.getvalue(),
    file_name=f"reporte_{orden_sel}.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
