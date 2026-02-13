import numpy as np

class SPCAnalyzer:
    def __init__(self, values, nominal=None, min_limit=None, max_limit=None):
        """
        :param values: List of floats (measurements in chronological order)
        :param nominal: Nominal value (target)
        :param min_limit: Lower tolerance limit
        :param max_limit: Upper tolerance limit
        """
        self.values = [v for v in values if v is not None]
        self.nominal = float(nominal) if nominal is not None else None
        self.min_limit = float(min_limit) if min_limit is not None else None
        self.max_limit = float(max_limit) if max_limit is not None else None
        
        # Calculate mean of current batch if nominal is not provided
        if self.nominal is None and len(self.values) > 0:
            self.mean = np.mean(self.values)
        else:
            self.mean = self.nominal
            
    def check_rules(self):
        """
        Checks common SPC rules and returns a list of alerts.
        """
        alerts = []
        if not self.values:
            return alerts

        last_val = self.values[-1]

        # Rule 1: Outside Limits (Critical)
        if self.min_limit is not None and last_val < self.min_limit:
            diff = round(abs(self.min_limit - last_val), 4)
            alerts.append({
                'rule': 'LIMIT_OUT',
                'severity': 'danger',
                'message': f'🔴 ERROR CRÍTICO\nMEDIDA: {last_val:.4f} < LÍM. INF ({self.min_limit})\nDESVIACIÓN: -{diff}\n----------------\nACCIÓN: La pieza es CHATARRA o requiere REPROCESO.'
            })
        elif self.max_limit is not None and last_val > self.max_limit:
            diff = round(abs(last_val - self.max_limit), 4)
            alerts.append({
                'rule': 'LIMIT_OUT',
                'severity': 'danger',
                'message': f'🔴 ERROR CRÍTICO\nMEDIDA: {last_val:.4f} > LÍM. SUP ({self.max_limit})\nDESVIACIÓN: +{diff}\n----------------\nACCIÓN: Verificar CORRECTOR DE HERRAMIENTA.'
            })

        # Trend Analysis (Requires history)
        if len(self.values) >= 6:
            # Rule: 6 consecutive points increasing or decreasing
            last_6 = self.values[-6:]
            diffs = np.diff(last_6)
            if np.all(diffs > 0):
                alerts.append({
                    'rule': 'TREND_UP',
                    'severity': 'warning',
                    'message': '⚠️ TENDENCIA CRECIENTE\n----------------\nDETALLE: 6 piezas consecutivas aumentando de tamaño.\nCAUSA: Posible desgaste de herramienta o deriva térmica.\nACCIÓN: Ajustar corrector.'
                })
            elif np.all(diffs < 0):
                alerts.append({
                    'rule': 'TREND_DOWN',
                    'severity': 'warning',
                    'message': '⚠️ TENDENCIA DECRECIENTE\n----------------\nDETALLE: 6 piezas consecutivas disminuyendo de tamaño.\nACCIÓN: Verificar estabilidad del proceso.'
                })

        # Bias Analysis (Requires history)
        if len(self.values) >= 7 and self.mean is not None:
            # Rule: 7 consecutive points on one side of the mean/nominal
            last_7 = self.values[-7:]
            if np.all(np.array(last_7) > self.mean):
                alerts.append({
                    'rule': 'BIAS_UP',
                    'severity': 'warning',
                    'message': f'⚠️ PROCESO DESCENTRADO (ALTO)\n----------------\nDETALLE: 7 piezas consecutivas por ENCIMA del nominal ({self.mean}).\nACCIÓN: Corregir el centro del proceso.'
                })
            elif np.all(np.array(last_7) < self.mean):
                alerts.append({
                    'rule': 'BIAS_DOWN',
                    'severity': 'warning',
                    'message': f'⚠️ PROCESO DESCENTRADO (BAJO)\n----------------\nDETALLE: 7 piezas consecutivas por DEBAJO del nominal ({self.mean}).\nACCIÓN: Corregir el centro del proceso.'
                })

        return alerts
