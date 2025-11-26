import pandas as pd

# ============================================
# EJEMPLO DE DATOS (simulan tus archivos)
# ============================================

# Datos de materiales por orden
materiales = pd.DataFrame([
    {"orden": 202357, "material": "Madera", "cant_orden": 500, "cant_buena": 445,
     "material_usado": 300, "material_tomado": 270},
    {"orden": 202357, "material": "Tornillos", "cant_orden": 500, "cant_buena": 445,
     "material_usado": 1500, "material_tomado": 1335},
    {"orden": 202357, "material": "Bisagras", "cant_orden": 500, "cant_buena": 445,
     "material_usado": 500, "material_tomado": 500},
])

# Tiempos informados / reales
tiempos = pd.DataFrame([
    {"orden": 202357, "tiempo_informado": 3.25, "tiempo_real": 3.25}
])

# ============================================
# LÓGICA
# ============================================

def analizar_orden(df_mat, df_tiempo, orden):

    # Filtrar datos de la orden
    datos = df_mat[df_mat["orden"] == orden].copy()
    tiempo = df_tiempo[df_tiempo["orden"] == orden].iloc[0]

    # Relación entre cantidad buena y cantidad ordenada
    cant_orden = datos["cant_orden"].iloc[0]
    cant_buena = datos["cant_buena"].iloc[0]
    relacion = cant_buena / cant_orden  # Ej: 445/500 = 0.89

    # Calcular desvíos por material
    datos["material_esperado"] = datos["material_usado"] * relacion
    datos["desvio"] = datos["material_tomado"] - datos["material_esperado"]

    # Tiempo
    tiempo_informado = tiempo["tiempo_informado"]
    tiempo_real = tiempo["tiempo_real"]
    desvio_tiempo = tiempo_informado - tiempo_real

    # Armamos la salida
    reporte = {
        "orden": orden,
        "relacion_produccion": relacion,
        "materiales": datos.to_dict(orient="records"),
        "tiempos": {
            "tiempo_informado": float(tiempo_informado),
            "tiempo_real": float(tiempo_real),
            "desvio": float(desvio_tiempo)
        }
    }

    return reporte


# ============================================
# PRUEBA CON ORDEN 202357
# ============================================

resultado = analizar_orden(materiales, tiempos, 202357)
resultado
