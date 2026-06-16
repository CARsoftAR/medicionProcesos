import React from 'react';
import EscanerManual from "./components/EscanerManual.jsx";
import './App.css';

function App() {
  return (
    <div className="App">
      <header className="App-header" style={{ padding: '20px', backgroundColor: '#282c34', color: 'white', textAlign: 'center' }}>
        <h1>Sistema de Medición ABBAMAT</h1>
      </header>
      <main>
        {/* Componente Escaner Manual restaurado e inyectado */}
        <EscanerManual />
      </main>
    </div>
  )
}

export default App
