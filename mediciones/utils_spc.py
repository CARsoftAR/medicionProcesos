import numpy as np
import math

class SPCAnalyzer:
    # SPC Factors for X-bar and R control charts (Subgroup size 2 to 10)
    FACTORS = {
        2:  {'A2': 1.880, 'D3': 0,     'D4': 3.267},
        3:  {'A2': 1.023, 'D3': 0,     'D4': 2.574},
        4:  {'A2': 0.729, 'D3': 0,     'D4': 2.282},
        5:  {'A2': 0.577, 'D3': 0,     'D4': 2.114},
        6:  {'A2': 0.483, 'D3': 0,     'D4': 2.004},
        7:  {'A2': 0.419, 'D3': 0.076, 'D4': 1.924},
        8:  {'A2': 0.373, 'D3': 0.136, 'D4': 1.864},
        9:  {'A2': 0.337, 'D3': 0.184, 'D4': 1.816},
        10: {'A2': 0.308, 'D3': 0.223, 'D4': 1.777},
    }

    def __init__(self, values, nominal=None, min_limit=None, max_limit=None, subgroup_size=5):
        """
        :param values: List of floats (measurements in chronological order)
        :param nominal: Nominal value (target)
        :param min_limit: Lower tolerance limit (Engineering)
        :param max_limit: Upper tolerance limit (Engineering)
        :param subgroup_size: Size of subgroups for X-bar/R charts
        """
        self.values = [float(v) for v in values if v is not None]
        self.nominal = float(nominal) if nominal is not None else None
        self.lsl = float(min_limit) if min_limit is not None else None
        self.usl = float(max_limit) if max_limit is not None else None
        self.n = subgroup_size
        
        # Derived stats for individual values
        self.mean = np.mean(self.values) if self.values else None
        self.std = np.std(self.values, ddof=1) if len(self.values) > 1 else 0

    def get_xr_data(self):
        """
        Groups data into subgroups and calculates X-bar and R values.
        """
        if not self.values or len(self.values) < self.n:
            return None

        subgroups = [self.values[i:i + self.n] for i in range(0, len(self.values), self.n)]
        # Ignore the last subgroup if it's incomplete
        if len(subgroups[-1]) < self.n:
            subgroups.pop()

        if not subgroups:
            return None

        x_bars = [np.mean(sg) for sg in subgroups]
        ranges = [max(sg) - min(sg) for sg in subgroups]
        
        grand_mean = np.mean(x_bars)
        avg_range = np.mean(ranges)
        
        factors = self.FACTORS.get(self.n, self.FACTORS[2])
        
        # X-bar Chart Limits
        ucl_x = grand_mean + factors['A2'] * avg_range
        lcl_x = grand_mean - factors['A2'] * avg_range
        
        # R Chart Limits
        ucl_r = factors['D4'] * avg_range
        lcl_r = factors['D3'] * avg_range

        return {
            'x_bars': x_bars,
            'ranges': ranges,
            'grand_mean': grand_mean,
            'avg_range': avg_range,
            'ucl_x': ucl_x,
            'lcl_x': lcl_x,
            'ucl_r': ucl_r,
            'lcl_r': lcl_r,
            'subgroup_size': self.n,
            'num_subgroups': len(subgroups)
        }

    def check_nelson_rules(self):
        """
        Applies Nelson rules (standard SPC anomaly detection).
        Returns a list of detected violations.
        """
        if not self.values or len(self.values) < 2:
            return []

        alerts = []
        data = np.array(self.values)
        mu = self.mean
        sigma = self.std
        
        if sigma == 0: sigma = 0.0001

        # Rule 1: One point is more than 3 sigma from the mean (Out of Control)
        outside_3s = np.where(np.abs(data - mu) > 3 * sigma)[0]
        for idx in outside_3s:
            alerts.append({
                'rule': 1,
                'point': int(idx),
                'value': float(data[idx]),
                'severity': 'danger',
                'title': 'Fuera de Control (±3σ)',
                'desc': f'El punto {idx+1} ({data[idx]:.4f}) está fuera de los límites estadísticos naturales.'
            })

        # Rule 2: 9 or more points in a row on the same side of the mean
        if len(data) >= 9:
            for i in range(len(data) - 8):
                window = data[i:i+9] - mu
                if np.all(window > 0) or np.all(window < 0):
                    alerts.append({
                        'rule': 2,
                        'point': i + 8,
                        'severity': 'warning',
                        'title': 'Racha detectada (9+ puntos)',
                        'desc': '9 o más puntos consecutivos en el mismo lado del promedio.'
                    })
                    break

        # Rule 3: 6 or more points in a row are all increasing or all decreasing
        if len(data) >= 6:
            for i in range(len(data) - 5):
                window = data[i:i+6]
                diffs = np.diff(window)
                if np.all(diffs > 0) or np.all(diffs < 0):
                    alerts.append({
                        'rule': 3,
                        'point': i + 5,
                        'severity': 'warning',
                        'title': 'Tendencia detectada (6+ puntos)',
                        'desc': '6 o más puntos seguidos en una dirección constante (creciente/decreciente).'
                    })
                    break

        # Rule 4: 14 or more points in a row alternate in direction, increasing then decreasing
        if len(data) >= 14:
            for i in range(len(data) - 13):
                window = data[i:i+14]
                diffs = np.diff(window)
                # Check if signs alternate: [+, -, +, -, ...]
                signs = np.sign(diffs)
                if np.all(signs[1:] != signs[:-1]) and np.all(signs != 0):
                    alerts.append({
                        'rule': 4,
                        'point': i + 13,
                        'severity': 'info',
                        'title': 'Variabilidad Inestable',
                        'desc': '14 puntos consecutivos alternando arriba y abajo. Indica inestabilidad sistemática.'
                    })
                    break

        return alerts

    def get_capability_indices(self):
        """
        Calculates Cp, Cpk, and process status.
        """
        if self.std == 0 or self.lsl is None or self.usl is None:
            # Try to calculate Cpk if only one limit exists
            cp = None
            cpk = None
            if self.std > 0:
                cpk_l = (self.mean - self.lsl) / (3 * self.std) if self.lsl is not None else float('inf')
                cpk_u = (self.usl - self.mean) / (3 * self.std) if self.usl is not None else float('inf')
                cpk = min(cpk_l, cpk_u)
                if cpk == float('inf'): cpk = None
            return cp, cpk

        cp = (self.usl - self.lsl) / (6 * self.std)
        cpk_l = (self.mean - self.lsl) / (3 * self.std)
        cpk_u = (self.usl - self.mean) / (3 * self.std)
        cpk = min(cpk_l, cpk_u)
        
        return cp, cpk
