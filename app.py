import streamlit as st
import pandas as pd
import io
import numpy as np

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Dashboard Integral SAP", layout="wide", page_icon="🏭")
st.title("🏭 Dashboard de Control: Tiempos y Materiales")
st.markdown("Sistema unificado de control de desvíos.")

# --- FUNCIONES DE CARGA ROBUSTA (CORE) ---
def encontrar_fila_encabezado(df, keywords):
    """Escanea las primeras 20 filas buscando palabras clave."""
    for i in range(min(20, len(df))):
        fila = df.iloc[i].astype(str).str.lower().tolist()
        texto = " ".join(fila)
        if any(k in texto for k in keywords):
            df.columns = df.iloc[i] # Asignar esa fila como header
            df = df.iloc[i+1:].reset_index(drop=True) # Datos
            return df, i
    return df, 0

def cargar_excel_inteligente(file, keywords, name):
    if not file: return None, 0
    try:
        df = pd.read_excel(file, header=None)
        df, fila = encontrar_fila_encabezado(df, keywords)
        # Limpieza básica de nombres de columnas
        df.columns = df.columns.astype(str).str.strip().str.replace('\n', ' ')
        return df, fila
    except Exception as e:
        st.error(f"Error cargando {name}: {e}")
        return None, 0

def clean_num(val):
    """Limpia textos con unidades (KG, CJ, HRA) y formato europeo."""
    if isinstance(val, (int, float)): return val
    if isinstance(val, str):
        # Quitar textos comunes
        val = val.upper().strip().replace('KG','').replace('CJ','').replace('HRA','').replace('HR','').strip()
        # Formato 1.000,00 -> 1000.00
        val = val.replace('.', '').replace(',', '.')
        try: return float(val)
        except: return 0.0
    return 0.0

def clean_key(val):
    """Estandariza la Orden a texto puro sin decimales."""
    return str(val).split('.')[0].strip()

def buscar_col(df, keywords):
    """Busca una columna que contenga alguna de las palabras clave."""
    for col in df.columns:
        if any(k in col.lower() for k in keywords): return col
    return None

# --- SIDEBAR ---
st.sidebar.header("⚙️ Configuración")
merma = st.sidebar.number_input("Merma Materiales (%)", 0.0, 20.0, 3.0) / 100
tolerancia = st.sidebar.slider("Filtro Tolerancia (%)", 0.0, 50.0, 1.0)

st.sidebar.divider()
f_mat = st.sidebar.file_uploader("1. Materiales (SAP)", type=["xlsx"])
f_prod = st.sidebar.file_uploader("2. Producción (Excel)", type=["xlsx"])
f_real = st.sidebar.file_uploader("3. Tiempos Reales (Piso)", type=["xlsx"])
f_sap = st.sidebar.file_uploader("4. Tiempos SAP", type=["xlsx"])

# --- PROCESAMIENTO PRINCIPAL ---
if f_mat and f_prod and f_real and f_sap:
    
    # 1. CARGA DE ARCHIVOS
    df_mat, _ = cargar_excel_inteligente(f_mat, ['necesaria', 'texto breve'], "Materiales")
    df_prod, _ = cargar_excel_inteligente(f_prod, ['cantidad buena', 'cantidad orden'], "Producción")
    df_real, r3 = cargar_excel_inteligente(f_real, ['tiempo de máquina', 'sector', 'planta'], "Tiempos Real")
    df_sap, r4 = cargar_excel_inteligente(f_sap, ['activ.1', 'recursos'], "Tiempos SAP")

    if all(v is not None for v in [df_mat, df_prod, df_real, df_sap]):
        
        # 2. UNIFICACIÓN DE LLAVES (ORDEN)
        # Buscamos la columna orden en cada archivo
        c_ord_mat = buscar_col(df_mat, ['orden'])
        c_ord_prod = buscar_col(df_prod, ['orden'])
        c_ord_real = buscar_col(df_real, ['orden']) # Busca "orden producción" o "orden"
        c_ord_sap = buscar_col(df_sap, ['orden'])

        if not (c_ord_mat and c_ord_prod and c_ord_real and c_ord_sap):
            st.error("❌ Error Crítico: No se encontró la columna 'Orden' en alguno de los archivos.")
            st.write(f"Columnas detectadas - Real: {list(df_real.columns)} | SAP: {list(df_sap.columns)}")
            st.stop()

        # Creamos la llave maestra 'KEY'
        df_mat['KEY'] = df_mat[c_ord_mat].apply(clean_key)
        df_prod['KEY'] = df_prod[c_ord_prod].apply(clean_key)
        df_real['KEY'] = df_real[c_ord_real].apply(clean_key)
        df_sap['KEY'] = df_sap[c_ord_sap].apply(clean_key)

        # ==========================================
        # 🕒 MÓDULO DE TIEMPOS (HORAS)
        # ==========================================
        
        # Buscar columnas de valores
        c_time_real = buscar_col(df_real, ['tiempo de máquina', 'tiempo maquina', 'machine'])
        c_time_sap = buscar_col(df_sap, ['activ.1', 'notificada'])

        if c_time_real and c_time_sap:
            # Limpieza de valores
            df_real['Val_Real'] = df_real[c_time_real].apply(clean_num)
            df_sap['Val_SAP'] = df_sap[c_time_sap].apply(clean_num)

            # Agrupar por orden (sumar si hay múltiples líneas)
            g_real = df_real.groupby('KEY')['Val_Real'].sum().reset_index()
            g_sap = df_sap.groupby('KEY')['Val_SAP'].sum().reset_index()

            # Merge (Outer para ver si falta cargar o sobra)
            df_times = pd.merge(g_sap, g_real, on='KEY', how='outer').fillna(0)
            
            # Cálculos
            df_times['Diferencia'] = df_times['Val_Real'] - df_times['Val_SAP']
            
            # Lógica de Acción
            # Si Real > SAP -> Falta cargar -> SUMAR
            # Si Real < SAP -> Se cargó de más -> RESTAR
            df_times['Acción'] = np.select(
                [df_times['Diferencia'] > 0.05, df_times['Diferencia'] < -0.05],
                ['SUMAR A SAP (Falta Declarar)', 'RESTAR A SAP (Exceso Declarado)'],
                default='OK'
            )
            
            # Filtrar solo errores
            df_times_final = df_times[df_times['Acción'] != 'OK'].copy()
            df_times_final = df_times_final.sort_values('Diferencia', ascending=False) # Los que más faltan arriba

        else:
            st.error("No se encontraron las columnas de 'Tiempo de Máquina' o 'Activ.1 Notificada'.")
            df_times_final = pd.DataFrame()

        # ==========================================
        # 📦 MÓDULO DE MATERIALES (DINÁMICO)
        # ==========================================
        
        c_nec = buscar_col(df_mat, ['necesaria'])
        c_tom = buscar_col(df_mat, ['tomada', 'real'])
        c_plan = buscar_col(df_prod, ['cantidad orden', 'plan'])
        c_hecha = buscar_col(df_prod, ['buena', 'real', 'producida'])

        if c_nec and c_tom and c_plan and c_hecha:
            # Limpieza
            df_mat['Nec'] = df_mat[c_nec].apply(clean_num)
            df_mat['Tom'] = df_mat[c_tom].apply(clean_num)
            df_prod['Plan'] = df_prod[c_plan].apply(clean_num)
            df_prod['Hecha'] = df_prod[c_hecha].apply(clean_num)

            # Agrupar producción
            prod_master = df_prod.groupby('KEY')[['Plan', 'Hecha']].sum().reset_index()
            
            # Merge Mat + Prod
            df_m = pd.merge(df_mat, prod_master, on='KEY', how='left')
            
            # Fallback por si no cruza producción (asumimos 1 a 1 para no romper)
            df_m['Plan'] = df_m['Plan'].fillna(1) 
            df_m['Hecha'] = df_m['Hecha'].fillna(df_m['Plan']) 

            # Cálculo Receta Dinámica
            # Coeficiente = Cuanto necesito por cada caja planeada
            df_m['Coef'] = np.where(df_m['Plan'] > 0, df_m['Nec'] / df_m['Plan'], 0)
            
            # Teorico Ajustado = Coef * Cajas Reales Hechas
            df_m['Teorico_Real'] = df_m['Coef'] * df_m['Hecha']
            
            # Max Permitido = Teorico Ajustado + Merma
            df_m['Max_Permitido'] = df_m['Teorico_Real'] * (1 + merma)

            # Diferencia y Estados
            df_m['Diff_Abs'] = df_m['Tom'] - df_m['Max_Permitido']
            
            conds = [
                (df_m['Tom'] > df_m['Max_Permitido']),
                (df_m['Tom'] < df_m['Teorico_Real'] * 0.95) # Tolerancia hacia abajo
            ]
            df_m['Estado'] = np.select(conds, ['EXCEDENTE', 'FALTA CARGAR'], default='OK')

            # Filtro visual de porcentaje
            df_m['% Desvio'] = np.where(df_m['Teorico_Real'] > 0, (df_m['Diff_Abs'] / df_m['Teorico_Real'])*100, 0)
            
            df_mat_final = df_m[
                (df_m['Estado'] != 'OK') & 
                (abs(df_m['% Desvio']) >= tolerancia)
            ].copy()

            # Columnas bonitas
            c_txt = buscar_col(df_mat, ['texto', 'descrip'])
            cols_show = ['KEY', c_txt, 'Hecha', 'Teorico_Real', 'Tom', 'Estado', 'Diff_Abs', '% Desvio']
            cols_show = [c for c in cols_show if c in df_mat_final.columns] # Evitar error si falta texto
            
        else:
            st.error("Faltan columnas numéricas en Materiales/Producción.")
            df_mat_final = pd.DataFrame()

        # ==========================================
        # 🖥️ VISUALIZACIÓN (TABS)
        # ==========================================
        
        tab1, tab2, tab3 = st.tabs(["⏱️ ANÁLISIS TIEMPOS", "📦 ANÁLISIS MATERIALES", "🕵️ DIAGNÓSTICO"])

        # --- TAB TIEMPOS ---
        with tab1:
            if not df_times_final.empty:
                col1, col2 = st.columns(2)
                col1.metric("Órdenes con Error Horas", len(df_times_final))
                
                sum_ajuste = df_times_final['Diferencia'].sum()
                col2.metric("Horas Netas a Ajustar", f"{sum_ajuste:+.2f} h", 
                           help="Positivo: Falta cargar en SAP. Negativo: Sobra en SAP.")

                # Función color simple
                def color_time(val):
                    if val > 0: return 'background-color: #ffeeb0; color: black' # Amarillo (Falta)
                    if val < 0: return 'background-color: #ffcdd2; color: black' # Rojo (Sobra)
                    return ''

                st.dataframe(
                    df_times_final.style.format({'Val_SAP': '{:.2f}', 'Val_Real': '{:.2f}', 'Diferencia': '{:+.2f}'})
                    .applymap(color_time, subset=['Diferencia']),
                    use_container_width=True
                )
                
                # Descarga
                buffer_h = io.BytesIO()
                with pd.ExcelWriter(buffer_h) as writer:
                    df_times_final.to_excel(writer, index=False)
                st.download_button("📥 Descargar Ajuste Horas", buffer_h.getvalue(), "Ajuste_Horas.xlsx")
            else:
                st.info("No hay diferencias de horas o no se cruzaron datos. Revisa la pestaña Diagnóstico.")

        # --- TAB MATERIALES ---
        with tab2:
            if not df_mat_final.empty:
                col1, col2 = st.columns(2)
                col1.metric("Materiales Desviados", len(df_mat_final))
                criticos = len(df_mat_final[df_mat_final['Estado']=='EXCEDENTE'])
                col2.metric("Excedentes Críticos", criticos)

                def color_mat(val):
                    if val == 'EXCEDENTE': return 'background-color: #ffcdd2; color: black; font-weight: bold'
                    if val == 'FALTA CARGAR': return 'background-color: #ffeeb0; color: black'
                    return ''

                st.dataframe(
                    df_mat_final[cols_show].style.format({
                        'Hecha': '{:,.0f}', 'Teorico_Real': '{:.2f}', 
                        'Tom': '{:.2f}', 'Diff_Abs': '{:.2f}', '% Desvio': '{:.1f}%'
                    }).applymap(color_mat, subset=['Estado']),
                    use_container_width=True
                )
                
                buffer_m = io.BytesIO()
                with pd.ExcelWriter(buffer_m) as writer:
                    df_mat_final.to_excel(writer, index=False)
                st.download_button("📥 Descargar Ajuste Materiales", buffer_m.getvalue(), "Ajuste_Materiales.xlsx")
            else:
                st.success("No hay desvíos de materiales según los filtros actuales.")

        # --- TAB DIAGNÓSTICO (SI ALGO FALLA) ---
        with tab3:
            st.write("### Verificación de Cruce de Datos")
            st.write("Si las tablas anteriores están vacías, verifica aquí los nombres de columnas y las llaves.")
            
            c1, c2 = st.columns(2)
            with c1:
                st.write("**Muestra Tiempos Real:**")
                st.dataframe(df_real.head(3), use_container_width=True)
                st.write(f"Columna detectada Orden: `{c_ord_real}`")
                st.write(f"Columna detectada Valor: `{c_time_real}`")
            with c2:
                st.write("**Muestra Tiempos SAP:**")
                st.dataframe(df_sap.head(3), use_container_width=True)
                st.write(f"Columna detectada Orden: `{c_ord_sap}`")
                st.write(f"Columna detectada Valor: `{c_time_sap}`")
                
            st.divider()
            
            # Checkeo de coincidencia de Keys
            keys_real = set(df_real['KEY'].unique())
            keys_sap = set(df_sap['KEY'].unique())
            coincidencias = len(keys_real.intersection(keys_sap))
            
            st.metric("Órdenes que coinciden (Real vs SAP)", coincidencias)
            if coincidencias == 0:
                st.error("¡CUIDADO! No hay ninguna orden en común entre los archivos de Tiempos. Revisa los formatos.")
                st.write("Ejemplo Real Key:", list(keys_real)[:5])
                st.write("Ejemplo SAP Key:", list(keys_sap)[:5])

else:
    st.info("Por favor, sube los 4 archivos para comenzar.")
