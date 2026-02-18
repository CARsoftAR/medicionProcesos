import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
import numpy as np
import io
import base64
from scipy.stats import norm

def fig_to_base64(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight', dpi=110)
    buf.seek(0)
    img_str = base64.b64encode(buf.read()).decode('utf-8')
    plt.close(fig)
    return f"data:image/png;base64,{img_str}"

def generate_xbar_chart(data_points, xr_data, labels):
    if not xr_data: return None
    
    fig, ax = plt.subplots(figsize=(8, 2.2))
    x_bars = xr_data['x_bars']
    grand_mean = xr_data['grand_mean']
    ucl = xr_data['ucl_x']
    lcl = xr_data['lcl_x']
    n = xr_data['subgroup_size']
    
    # Plot individual points in light gray
    ax.plot(range(len(data_points)), data_points, color='#94a3b8', alpha=0.4, linewidth=1, marker='o', markersize=3, label='Piezas Indiv.')
    
    # Plot X-bars (subgroup means)
    # Positions: [n-1, 2n-1, ...]
    positions = [(i + 1) * n - 1 for i in range(len(x_bars))]
    ax.plot(positions, x_bars, color='#0ea5e9', linewidth=2.5, marker='D', markersize=6, label='Promedio X-Bar')
    
    # Control Limits
    ax.axhline(y=grand_mean, color='#10b981', linestyle='--', linewidth=1.5, label='Media Global')
    ax.axhline(y=ucl, color='#ef4444', linestyle=':', linewidth=1.5, label='UCL')
    ax.axhline(y=lcl, color='#ef4444', linestyle=':', linewidth=1.5, label='LCL')
    
    ax.set_title('Gráfico de Medidas (X-Bar)', fontsize=10, fontweight='bold', pad=10)
    ax.legend(loc='upper right', fontsize=7, frameon=True, framealpha=0.8)
    ax.grid(True, alpha=0.15)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=45, fontsize=6)
    
    return fig_to_base64(fig)

def generate_r_chart(data_points, xr_data, labels):
    if not xr_data: return None
    
    fig, ax = plt.subplots(figsize=(8, 2.2))
    ranges = xr_data['ranges']
    avg_range = xr_data['avg_range']
    ucl = xr_data['ucl_r']
    lcl = xr_data['lcl_r']
    n = xr_data['subgroup_size']
    
    # Individual Moving Ranges (mR) in gray
    mr_data = [None] + [abs(data_points[i] - data_points[i-1]) for i in range(1, len(data_points))]
    ax.plot(range(len(data_points)), mr_data, color='#94a3b8', alpha=0.4, linewidth=1, marker='.', label='mR Indiv.')
    
    # Plot subgroup ranges
    positions = [(i + 1) * n - 1 for i in range(len(ranges))]
    ax.plot(positions, ranges, color='#a855f7', linewidth=2.5, marker='s', markersize=6, label='Rango Subgr.')
    
    # Limits
    ax.axhline(y=avg_range, color='#00ff88', linestyle='--', linewidth=1.5)
    ax.axhline(y=ucl, color='#ff4d6a', linestyle=':', linewidth=1.5)
    if lcl > 0: ax.axhline(y=lcl, color='#ff4d6a', linestyle=':', linewidth=1.5)
    
    ax.set_title('Gráfico de Amplitud (Rango)', fontsize=10, fontweight='bold', pad=10)
    ax.legend(loc='upper right', fontsize=7)
    ax.grid(True, alpha=0.1)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=45, fontsize=6)
    
    return fig_to_base64(fig)

def generate_capability_chart(data_points, nominal, lsl, usl):
    if not data_points: return None
    
    fig, ax = plt.subplots(figsize=(5, 2.2))
    
    # Histogram
    counts, bins, _ = ax.hist(data_points, bins='auto', density=True, alpha=0.5, color='#3b82f6', edgecolor='#1d4ed8', label='Frecuencias')
    
    # Gauss Curve
    mu = np.mean(data_points)
    sigma = np.std(data_points, ddof=1) or 0.0001
    x = np.linspace(min(data_points + ([lsl] if lsl else []) + ([usl] if usl else [])) - sigma, 
                    max(data_points + ([lsl] if lsl else []) + ([usl] if usl else [])) + sigma, 100)
    p = norm.pdf(x, mu, sigma)
    ax.plot(x, p, 'k', linewidth=2, color='#0284c7', label='Diste. Obtenida')
    
    # Tolerance lines
    if lsl is not None: ax.axvline(x=lsl, color='#ef4444', linestyle='-', linewidth=2, label='L.I.E.')
    if usl is not None: ax.axvline(x=usl, color='#ef4444', linestyle='-', linewidth=2, label='L.S.E.')
    if nominal is not None: ax.axvline(x=nominal, color='#64748b', linestyle='--', linewidth=1, label='Nominal')
    
    ax.set_title('Capacidad y Distribución', fontsize=10, fontweight='bold')
    ax.legend(loc='upper right', fontsize=6)
    ax.set_yticks([]) # Hide Y axis density
    
    return fig_to_base64(fig)
