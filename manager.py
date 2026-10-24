"""LEDMatrix Glooko plugin for a 128x32 panel."""
import logging
import time
from PIL import Image, ImageDraw
from src.plugin_system.base_plugin import BasePlugin
from glooko_provider import GlookoProvider
logging.getLogger("glooko.client").setLevel(logging.WARNING)

class GlookoPlugin(BasePlugin):
    def __init__(self,plugin_id,config,display_manager,cache_manager,plugin_manager):
        super().__init__(plugin_id,config,display_manager,cache_manager,plugin_manager)
        self.snapshot=None; self.error=None; self.provider=None; self.last_fetch=0
        self._load_config(config)
    def _load_config(self,c):
        self.email=c.get("email",""); self.password=c.get("password",""); self.units=c.get("units","mmol/L")
        self.refresh_seconds=int(c.get("refresh_seconds",300)); self.stale_minutes=int(c.get("stale_minutes",30))
        self.history_hours=int(c.get("history_hours",6)); self.colorize_graph=bool(c.get("colorize_graph",False)); self.provider=None
    def on_config_change(self,new_config):
        super().on_config_change(new_config); self._load_config(self.config)
    def get_update_interval(self): return self.refresh_seconds
    def update(self):
        if not self.email or not self.password: self.error="SET LOGIN"; return
        try:
            if self.provider is None: self.provider=GlookoProvider(self.email,self.password,self.history_hours)
            fresh=self.provider.fetch(); self.snapshot=fresh; self.last_fetch=time.time(); self.error=None if fresh.glucose_mmol is not None else "NO CGM"
        except Exception as exc:
            self.logger.error("Glooko refresh failed (%s)",type(exc).__name__); self.error="GLOOKO ERR"
    def _display_glucose(self,mmol):
        if mmol is None:return "--"
        return f"{mmol*18.0182:.0f}" if self.units=="mg/dL" else f"{mmol:.1f}"
    def _draw_trend_arrow(self,dm,trend,x,y,color):
        if not hasattr(dm,"draw"):return
        if trend in ("^^","^"): dx,dy=0,-5
        elif trend=="/": dx,dy=5,-5
        elif trend in ("vv","v"): dx,dy=0,5
        elif trend=="\\": dx,dy=5,5
        else: dx,dy=6,0
        x1,y1=x,y+5; x2,y2=x1+dx,y1+dy; dm.draw.line((x1,y1,x2,y2),fill=color,width=1)
        if dx==0 and dy<0:
            dm.draw.line((x2,y2,x2-2,y2+2),fill=color,width=1); dm.draw.line((x2,y2,x2+2,y2+2),fill=color,width=1)
        elif dx==0 and dy>0:
            dm.draw.line((x2,y2,x2-2,y2-2),fill=color,width=1); dm.draw.line((x2,y2,x2+2,y2-2),fill=color,width=1)
        elif dy<0:
            dm.draw.line((x2,y2,x2-3,y2),fill=color,width=1); dm.draw.line((x2,y2,x2,y2+3),fill=color,width=1)
        elif dy>0:
            dm.draw.line((x2,y2,x2-3,y2),fill=color,width=1); dm.draw.line((x2,y2,x2,y2-3),fill=color,width=1)
        else:
            dm.draw.line((x2,y2,x2-2,y2-2),fill=color,width=1); dm.draw.line((x2,y2,x2-2,y2+2),fill=color,width=1)
    def display(self,force_clear=False):
        if self.snapshot is None:return False
        dm=self.display_manager; snap=self.snapshot; width=getattr(dm,"width",128); height=getattr(dm,"height",32)
        # Build the complete next frame in memory. Do not call dm.clear(): on a
        # physical RGB matrix that can expose a black frame before repainting,
        # which appears as a very brief blink on repeated display() calls.
        dm.image=Image.new("RGB",(width,height),(0,0,0)); dm.draw=ImageDraw.Draw(dm.image); dm.draw.fontmode="1"
        font=getattr(dm,"bdf_5x7_font",None) or getattr(dm,"small_font",None)
        white=(255,255,255); muted=(150,150,150); stale_red=(255,0,0)
        glucose=self._display_glucose(snap.glucose_mmol); glucose_age=snap.age_minutes(); glucose_stale=glucose_age is None or glucose_age>=self.stale_minutes
        glucose_color=stale_red if glucose_stale else white
        dm.draw_text(glucose,x=1,y=0,color=glucose_color,font=font)
        self._draw_trend_arrow(dm,snap.trend,42,0,glucose_color)
        units_text="mg/dL" if self.units=="mg/dL" else "mmol/L"; dm.draw_text(units_text,x=1,y=8,color=muted,font=font)
        freshness="NO TIME" if glucose_age is None else (f"STALE {glucose_age}m" if glucose_stale else f"{glucose_age}m")
        units_w=dm.get_text_width(units_text,font); dm.draw_text(freshness,x=units_w+5,y=8,color=stale_red if glucose_stale else muted,font=font)
        # IOB is contextual information from Glooko and may legitimately be older than
        # the latest CGM reading. Keep it neutral so red is reserved for stale CGM.
        iob_text="IOB --" if snap.iob is None else f"IOB {snap.iob:.2f}u"
        iob_w=dm.get_text_width(iob_text,font); dm.draw_text(iob_text,x=max(50,width-iob_w-1),y=0,color=white,font=font)
        pump=(snap.pump_mode or "--").upper()[:7]; pump_w=dm.get_text_width(pump,font); dm.draw_text(pump,x=max(70,width-pump_w-1),y=8,color=muted,font=font)
        points=list(snap.points or [])
        if len(points)>=2 and hasattr(dm,"draw"):
            gl,gr,gt,gb=1,width-2,16,height-1; values=[float(v) for _,v in points]; lo,hi=min(values),max(values)
            if hi-lo<1.0: mid=(hi+lo)/2.0; lo,hi=mid-0.5,mid+0.5
            t0,t1=points[0][0],points[-1][0]; span=max(1.0,(t1-t0).total_seconds()); xy=[]
            for timestamp,value in points:
                fx=(timestamp-t0).total_seconds()/span; fy=(float(value)-lo)/max(0.01,hi-lo)
                x=max(gl,min(gr,gl+int(fx*(gr-gl)))); y=max(gt,min(gb,gb-int(fy*(gb-gt)))); xy.append((x,y))
            if self.colorize_graph:
                def graph_color(mmol):
                    if mmol<=3.9:return (255,255,0)
                    if mmol>=10.0:return (255,0,0)
                    return (0,255,0)
                for idx in range(1,len(xy)): dm.draw.line((xy[idx-1],xy[idx]),fill=graph_color(float(points[idx][1])),width=1)
            else: dm.draw.line(xy,fill=white,width=1)
        dm.update_display(); return True
