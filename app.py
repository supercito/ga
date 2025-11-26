import { useState } from "react";
import * as XLSX from "xlsx";

export default function FrontEndProduccion() {
  const [archivos, setArchivos] = useState({
    tiempoReal: null,
    componentes: null,
    tiemposInformados: null,
    produccion: null,
  });

  const [ordenes, setOrdenes] = useState([]);
  const [resultado, setResultado] = useState(null);

  const handleArchivo = (e, tipo) => {
    setArchivos({ ...archivos, [tipo]: e.target.files[0] });
  };

  const leerExcel = async (file) => {
    const data = await file.arrayBuffer();
    const workbook = XLSX.read(data);
    const hoja = workbook.Sheets[workbook.SheetNames[0]];
    return XLSX.utils.sheet_to_json(hoja);
  };

  const procesar = async () => {
    const tiempoReal = await leerExcel(archivos.tiempoReal);
    const componentes = await leerExcel(archivos.componentes);
    const tiemposInf = await leerExcel(archivos.tiemposInformados);
    const produccion = await leerExcel(archivos.produccion);

    // Obtener órdenes disponibles
    const listaOrdenes = [...new Set(produccion.map((r) => r.Orden))];
    setOrdenes(listaOrdenes);

    window._data = { tiempoReal, componentes, tiemposInf, produccion }; // para debug
  };

  const analizarOrden = (orden) => {
    const { tiempoReal, componentes, tiemposInf, produccion } = window._data;

    const prod = produccion.find((x) => x.Orden === orden);
    const comp = componentes.filter((x) => x.Orden === orden);
    const tReal = tiempoReal.find((x) => x.Orden === orden);
    const tInf = tiemposInf.find((x) => x.Orden === orden);

    // Relación de producción
    const relacion = prod["Cantidad buena confirmada"] / prod["Cantidad orden"];

    // Materiales
    const materiales = comp.map((m) => {
      const esperado = m["Cantidad tomada"] * relacion;
      return {
        material: m["Texto Breve Material"],
        necesario: m["Cantidad necesaria"],
        tomado: m["Cantidad tomada"],
        esperado,
        desvio: m["Cantidad tomada"] - esperado,
      };
    });

    // Tiempo
    const tiempo = {
      real: tReal?.Tiempo || 0,
      informado: tInf?.Tiempo || 0,
      desvio: (tInf?.Tiempo || 0) - (tReal?.Tiempo || 0),
    };

    setResultado({
      orden,
      relacion,
      materiales,
      tiempo,
      produccion: prod,
    });
  };

  return (
    <div className="p-6 max-w-3xl mx-auto">
      <h1 className="text-3xl font-bold mb-4">Analizador de Producción</h1>

      {/* ARCHIVOS */}
      <div className="grid grid-cols-2 gap-4">
        <input type="file" onChange={(e) => handleArchivo(e, "tiempoReal")} />
        <input type="file" onChange={(e) => handleArchivo(e, "componentes")} />
        <input type="file" onChange={(e) => handleArchivo(e, "tiemposInformados")} />
        <input type="file" onChange={(e) => handleArchivo(e, "produccion")} />
      </div>

      <button
        onClick={procesar}
        className="mt-4 bg-blue-600 text-white px-4 py-2 rounded"
      >
        Procesar archivos
      </button>

      {/* ORDENES */}
      {ordenes.length > 0 && (
        <div className="mt-6">
          <h2 className="font-bold">Seleccionar Orden:</h2>
          <select
            className="border p-2 rounded"
            onChange={(e) => analizarOrden(Number(e.target.value))}
          >
            <option value="">-- Elegir --</option>
            {ordenes.map((o) => (
              <option key={o} value={o}>
                {o}
              </option>
            ))}
          </select>
        </div>
      )}

      {/* RESULTADO */}
      {resultado && (
        <div className="mt-6 p-4 bg-gray-100 rounded">
          <h2 className="text-xl font-bold mb-2">Orden {resultado.orden}</h2>

          <p><b>Relación de producción:</b> {(resultado.relacion * 100).toFixed(2)}%</p>

          <h3 className="font-bold mt-4 mb-2">Materiales</h3>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b">
                <th>Material</th>
                <th>Tomado</th>
                <th>Esperado</th>
                <th>Desvío</th>
              </tr>
            </thead>
            <tbody>
              {resultado.materiales.map((m) => (
                <tr key={m.material} className="border-b">
                  <td>{m.material}</td>
                  <td>{m.tomado}</td>
                  <td>{m.esperado.toFixed(2)}</td>
                  <td className={m.desvio > 0 ? "text-red-600" : "text-green-600"}>
                    {m.desvio.toFixed(2)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          <h3 className="font-bold mt-4 mb-2">Tiempo</h3>
          <p>Real: {resultado.tiempo.real}</p>
          <p>Informado: {resultado.tiempo.informado}</p>
          <p>
            Desvío:{" "}
            <span
              className={
                resultado.tiempo.desvio > 0 ? "text-red-600" : "text-green-600"
              }
            >
              {resultado.tiempo.desvio}
            </span>
          </p>
        </div>
      )}
    </div>
  );
}
