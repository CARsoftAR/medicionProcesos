import React, { useState } from 'react';

const EscanerManual = () => {
    const [imagenBase64, setImagenBase64] = useState(null);
    const [casilleros, setCasilleros] = useState([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    const procesarPlanilla = async () => {
        setLoading(true);
        setError(null);
        try {
            const response = await fetch('/api/procesar-planilla/');
            if (!response.ok) {
                throw new Error('Error de conexión con el servidor Django');
            }
            const data = await response.json();
            if (data.status === 'success') {
                setImagenBase64(data.imagen);
                setCasilleros(data.casilleros);
            } else {
                throw new Error(data.message || 'Error al procesar la matriz');
            }
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="escaner-manual-container" style={{ padding: '20px' }}>
            <h2>Escáner Manual de Planillas</h2>
            <button 
                onClick={procesarPlanilla} 
                disabled={loading}
                style={{
                    padding: '10px 20px', 
                    fontSize: '16px', 
                    cursor: 'pointer',
                    backgroundColor: '#007bff',
                    color: 'white',
                    border: 'none',
                    borderRadius: '4px',
                    marginBottom: '20px'
                }}
            >
                {loading ? 'Procesando con OpenCV...' : 'Cargar y Procesar Planilla'}
            </button>

            {error && (
                <div style={{ color: 'red', marginBottom: '20px', padding: '10px', border: '1px solid red' }}>
                    <strong>Error: </strong> {error}
                </div>
            )}

            {imagenBase64 && (
                <div 
                    className="imagen-relativa-container" 
                    style={{ 
                        position: 'relative', 
                        display: 'inline-block',
                        border: '2px solid #ccc',
                        backgroundColor: '#f8f9fa'
                    }}
                >
                    <img 
                        src={imagenBase64} 
                        alt="Planilla Calibrada" 
                        style={{ display: 'block' }} 
                    />
                    
                    {casilleros.map((casilla) => (
                        <input
                            key={casilla.id}
                            type="text"
                            placeholder={casilla.id}
                            title={`Bloque: ${casilla.bloque} - Fila: ${casilla.fila} - Columna: ${casilla.columna}`}
                            style={{
                                position: 'absolute',
                                left: `${casilla.x}px`,
                                top: `${casilla.y}px`,
                                width: `${casilla.w}px`,
                                height: `${casilla.h}px`,
                                background: 'rgba(255, 255, 255, 0.7)',
                                border: '1px solid rgba(0, 0, 255, 0.5)',
                                color: '#000',
                                fontSize: '14px',
                                textAlign: 'center',
                                outline: 'none',
                                boxSizing: 'border-box'
                            }}
                            onFocus={(e) => {
                                e.target.style.background = 'rgba(255, 255, 0, 0.8)';
                                e.target.style.border = '2px solid red';
                            }}
                            onBlur={(e) => {
                                e.target.style.background = 'rgba(255, 255, 255, 0.7)';
                                e.target.style.border = '1px solid rgba(0, 0, 255, 0.5)';
                            }}
                        />
                    ))}
                </div>
            )}
        </div>
    );
};

export default EscanerManual;
