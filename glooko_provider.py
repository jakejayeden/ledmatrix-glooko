"""Glooko data provider for LEDMatrix."""
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple
import logging

logging.getLogger("glooko.client").setLevel(logging.WARNING)

@dataclass
class Snapshot:
    glucose_mmol: Optional[float] = None
    glucose_time: Optional[datetime] = None
    trend: str = "?"
    iob: Optional[float] = None
    iob_time: Optional[datetime] = None
    pump_mode: Optional[str] = None
    points: List[Tuple[datetime, float]] = field(default_factory=list)
    @staticmethod
    def _age_minutes(ts):
        if ts is None: return None
        now = datetime.now(timezone.utc)
        if ts.tzinfo is None: ts = ts.replace(tzinfo=timezone.utc)
        return max(0, int((now-ts).total_seconds()/60))
    def age_minutes(self): return self._age_minutes(self.glucose_time)
    def iob_age_minutes(self): return self._age_minutes(self.iob_time)

def _dt(value):
    if not value: return None
    if isinstance(value, datetime): return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, (int,float)):
        v=float(value); v=v/1000.0 if v>10_000_000_000 else v
        try: return datetime.fromtimestamp(v,tz=timezone.utc)
        except (ValueError,OSError,OverflowError): return None
    if isinstance(value,str):
        try: return datetime.fromisoformat(value.replace("Z","+00:00"))
        except ValueError: return None
    return None

def _series(data):
    if not isinstance(data,dict): return {}
    s=data.get("series",data)
    return s if isinstance(s,dict) else {}

def extract_cgm(data):
    out=[]
    for key in ("cgmLow","cgmNormal","cgmHigh"):
        for item in _series(data).get(key,[]) or []:
            if not isinstance(item,dict): continue
            ts=_dt(item.get("timestamp")); val=item.get("y")
            try:
                if ts is not None and val is not None: out.append((ts,float(val)))
            except (TypeError,ValueError): pass
    return sorted({ts:val for ts,val in out}.items(),key=lambda p:p[0])

def trend(points):
    if len(points)<2: return "?"
    t2,v2=points[-1]; t1,v1=points[-2]
    for ct,cv in reversed(points[:-1]):
        if (t2-ct).total_seconds()>=600: t1,v1=ct,cv; break
    mins=max(1.0,(t2-t1).total_seconds()/60.0); rate=(v2-v1)/mins
    if rate>=3/18.0182:return "^^"
    if rate>=2/18.0182:return "^"
    if rate>=1/18.0182:return "/"
    if rate<=-3/18.0182:return "vv"
    if rate<=-2/18.0182:return "v"
    if rate<=-1/18.0182:return "\\"
    return "->"

def extract_iob(data):
    newest=None
    for item in _series(data).get("deliveredBolus",[]) or []:
        if not isinstance(item,dict) or item.get("insulinOnBoard") is None: continue
        ts=_dt(item.get("timestamp"))
        if ts is None: continue
        try: candidate=(ts,float(item["insulinOnBoard"]))
        except (TypeError,ValueError): continue
        if newest is None or ts>newest[0]: newest=candidate
    return newest

def _find_mode_fields(obj):
    if not isinstance(obj,dict): return None
    wanted=("op5PumpModeAutomaticPercentage","op5PumpModeManualPercentage","op5PumpModeLimitedPercentage","op5PumpModeHypoProtectPercentage")
    if any(k in obj for k in wanted): return obj
    for value in obj.values():
        if isinstance(value,dict):
            found=_find_mode_fields(value)
            if found is not None:return found
        elif isinstance(value,list):
            for item in value:
                found=_find_mode_fields(item)
                if found is not None:return found
    return None

def extract_mode(stats):
    source=_find_mode_fields(stats)
    if not source:return None
    candidates={"AUTO":source.get("op5PumpModeAutomaticPercentage",0) or 0,"MANUAL":source.get("op5PumpModeManualPercentage",0) or 0,"LIMIT":source.get("op5PumpModeLimitedPercentage",0) or 0,"HYPO":source.get("op5PumpModeHypoProtectPercentage",0) or 0}
    mode,pct=max(candidates.items(),key=lambda x:x[1])
    return mode if pct else None

class GlookoProvider:
    def __init__(self,email,password,history_hours=3):
        from glooko import GlookoClient
        self.client=GlookoClient(email,password); self.history_hours=history_hours
    def fetch(self):
        end=datetime.now(timezone.utc); start=end-timedelta(hours=self.history_hours)
        start_s=start.strftime("%Y-%m-%dT%H:%M:%S.000Z"); end_s=end.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        graph=self.client.get_graph_data(start_s,end_s) or {}; stats=self.client.get_statistics(start_s,end_s) or {}
        points=extract_cgm(graph); iob_record=extract_iob(graph)
        return Snapshot(glucose_mmol=points[-1][1] if points else None,glucose_time=points[-1][0] if points else None,trend=trend(points),iob=iob_record[1] if iob_record else None,iob_time=iob_record[0] if iob_record else None,pump_mode=extract_mode(stats),points=points)
