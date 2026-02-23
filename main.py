import os
import math
import threading
from kivy.app import App
from kivy.lang import Builder
from kivy.uix.popup import Popup
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.filechooser import FileChooserListView
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.checkbox import CheckBox
from kivy.uix.progressbar import ProgressBar
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.utils import platform
from kivy.clock import Clock
from kivy.graphics import Color, Rectangle, RoundedRectangle

GPS_TIMEOUT = 90

# =====================================================
# Permissions Request (Android)
# =====================================================
def request_android_permissions():
    if platform == 'android':
        try:
            from android.permissions import request_permissions, Permission
            request_permissions([
                Permission.ACCESS_FINE_LOCATION,
                Permission.ACCESS_COARSE_LOCATION,
                Permission.READ_EXTERNAL_STORAGE,
                Permission.WRITE_EXTERNAL_STORAGE
            ])
        except Exception:
            pass

# =====================================================
# KML Layer Colors (Google Earth: AABBGGRR format)
# =====================================================
LAYER_COLORS_HEX = [
    ("Red",    "ff0000ff"),
    ("Blue",   "ffff0000"),
    ("Green",  "ff00aa00"),
    ("Yellow", "ff00ffff"),
    ("Cyan",   "ffffff00"),
    ("Purple", "ffaa00aa"),
    ("Orange", "ff0066ff"),
    ("White",  "ffffffff"),
    ("Pink",   "ffaa44ff"),
    ("Lime",   "ff00ff88"),
]

def get_layer_color(index):
    return LAYER_COLORS_HEX[index % len(LAYER_COLORS_HEX)]

def kml_color_to_rgb(kml_hex):
    """AABBGGRR → (R,G,B) 0-1"""
    try:
        b = int(kml_hex[2:4], 16) / 255
        g = int(kml_hex[4:6], 16) / 255
        r = int(kml_hex[6:8], 16) / 255
        return (r, g, b)
    except Exception:
        return (1, 1, 1)

# =====================================================
# SLD99 → WGS84
# =====================================================
def sld99_to_wgs84(easting, northing):
    a=6377276.345; f=1/300.8017; b=a*(1-f)
    e2=(a**2-b**2)/a**2; e_prime2=(a**2-b**2)/b**2
    k0=0.9999238418; fe=500000.0; fn=500000.0
    lon0=math.radians(80.7717130833333); lat0=math.radians(7.00047152777778)
    x=easting-fe; y=northing-fn
    M0=a*((1-e2/4-3*e2**2/64-5*e2**3/256)*lat0-(3*e2/8+3*e2**2/32)*math.sin(2*lat0)+(15*e2**3/256)*math.sin(4*lat0))
    M=M0+y/k0; mu=M/(a*(1-e2/4-3*e2**2/64-5*e2**3/256))
    e1=(1-math.sqrt(1-e2))/(1+math.sqrt(1-e2))
    lat1=mu+(3*e1/2-27*e1**3/32)*math.sin(2*mu)+(21*e1**2/16)*math.sin(4*mu)+(151*e1**3/96)*math.sin(6*mu)
    N1=a/math.sqrt(1-e2*math.sin(lat1)**2); T1=math.tan(lat1)**2
    C1=e_prime2*math.cos(lat1)**2; R1=a*(1-e2)/(1-e2*math.sin(lat1)**2)**1.5
    D=x/(N1*k0)
    lat_l=lat1-(N1*math.tan(lat1)/R1)*(D**2/2-(5+3*T1+10*C1-4*C1**2-9*e_prime2)*D**4/24+(61+90*T1+298*C1+45*T1**2-252*e_prime2-3*C1**2)*D**6/720)
    lon_l=lon0+(D-(1+2*T1+C1)*D**3/6+(5-2*C1+28*T1-3*C1**2+8*e_prime2+24*T1**2)*D**5/120)/math.cos(lat1)
    h=0.0; Nl=a/math.sqrt(1-e2*math.sin(lat_l)**2)
    Xl=(Nl+h)*math.cos(lat_l)*math.cos(lon_l); Yl=(Nl+h)*math.cos(lat_l)*math.sin(lon_l); Zl=(Nl*(1-e2)+h)*math.sin(lat_l)
    dx=-0.293; dy=766.95; dz=87.713
    rx=math.radians(-0.195704/3600); ry=math.radians(-1.695068/3600); rz=math.radians(-3.473016/3600); ds=-0.039338/1e6
    Xw=Xl+dx+ds*Xl+rz*Yl-ry*Zl; Yw=Yl+dy-rz*Xl+ds*Yl+rx*Zl; Zw=Zl+dz+ry*Xl-rx*Yl+ds*Zl
    aw=6378137.0; fw=1/298.257223563; e2w=2*fw-fw**2; bw=aw*(1-fw); ep2w=(aw**2-bw**2)/bw**2
    p=math.sqrt(Xw**2+Yw**2); th=math.atan2(Zw*aw,p*bw)
    lonw=math.atan2(Yw,Xw); latw=math.atan2(Zw+ep2w*bw*math.sin(th)**3,p-e2w*aw*math.cos(th)**3)
    return math.degrees(lonw), math.degrees(latw)

# =====================================================
# WGS84 → SLD99 (Inverse)
# =====================================================
def wgs84_to_sld99(lon, lat):
    aw = 6378137.0; fw = 1/298.257223563; ew2 = 2*fw - fw**2
    ae = 6377276.345; fe = 1/300.8017; ee2 = 2*fe - fe**2
    
    lat_rad = math.radians(lat)
    lon_rad = math.radians(lon)
    Nw = aw / math.sqrt(1 - ew2 * math.sin(lat_rad)**2)
    h = 0 
    Xw = (Nw + h) * math.cos(lat_rad) * math.cos(lon_rad)
    Yw = (Nw + h) * math.cos(lat_rad) * math.sin(lon_rad)
    Zw = (Nw * (1 - ew2) + h) * math.sin(lat_rad)
    
    dx=-0.293; dy=766.95; dz=87.713
    rx=math.radians(-0.195704/3600); ry=math.radians(-1.695068/3600); rz=math.radians(-3.473016/3600)
    ds=-0.039338/1e6
    
    Xs = Xw - dx; Ys = Yw - dy; Zs = Zw - dz
    X_e = Xs - ds*Xs + rz*Ys - ry*Zs
    Y_e = Ys - rz*Xs - ds*Ys + rx*Zs
    Z_e = Zs + ry*Xs - rx*Ys - ds*Zs
    
    p = math.sqrt(X_e**2 + Y_e**2)
    th = math.atan2(Z_e * ae, p * (ae*(1-fe)))
    ep2 = ee2 / (1-ee2)
    lat_e = math.atan2(Z_e + ep2 * ae*(1-fe) * math.sin(th)**3, p - ee2 * ae * math.cos(th)**3)
    lon_e = math.atan2(Y_e, X_e)
    
    lat0 = math.radians(7.00047152777778); lon0 = math.radians(80.7717130833333)
    k0 = 0.9999238418; fe_val = 500000.0; fn_val = 500000.0
    
    A = (lon_e - lon0) * math.cos(lat_e)
    T = math.tan(lat_e)**2
    C = ep2 * math.cos(lat_e)**2
    N = ae / math.sqrt(1 - ee2 * math.sin(lat_e)**2)
    
    def calc_M(phi):
        return ae * ((1 - ee2/4 - 3*ee2**2/64 - 5*ee2**3/256)*phi - 
                     (3*ee2/8 + 3*ee2**2/32)*math.sin(2*phi) + 
                     (15*ee2**3/256)*math.sin(4*phi))
                     
    M = calc_M(lat_e)
    M0 = calc_M(lat0)
    
    Easting = fe_val + k0 * N * (A + (1-T+C)*A**3/6 + (5-18*T+T**2+72*C-58*ep2)*A**5/120)
    Northing = fn_val + k0 * (M - M0 + N * math.tan(lat_e) * (A**2/2 + (5-T+9*C+4*C**2)*A**4/24 + (61-58*T+T**2+600*C-330*ep2)*A**6/720))
    
    return Easting, Northing

# =====================================================
# WhatsApp Sharing Intents
# =====================================================
def share_text_whatsapp(text_content):
    if platform != 'android':
        print("Share Text:", text_content)
        return False, "Works only on Android"
    try:
        from jnius import autoclass, cast
        Intent = autoclass('android.content.Intent')
        String = autoclass('java.lang.String')
        
        intent = Intent(Intent.ACTION_SEND)
        intent.setType("text/plain")
        intent.putExtra(Intent.EXTRA_TEXT, String(text_content))
        intent.setPackage("com.whatsapp")
        
        try:
            PA = autoclass('org.kivy.android.PythonActivity')
        except Exception:
            PA = autoclass('org.renpy.android.PythonActivity')
            
        currentActivity = cast('android.app.Activity', PA.mActivity)
        currentActivity.startActivity(intent)
        return True, "Opened WhatsApp"
    except Exception as e:
        return False, str(e)

def share_file_whatsapp(filepath):
    if platform != 'android':
        print("Share File:", filepath)
        return False, "Works only on Android"
    try:
        from jnius import autoclass, cast
        StrictMode = autoclass('android.os.StrictMode')
        VmB = autoclass('android.os.StrictMode$VmPolicy$Builder')
        StrictMode.setVmPolicy(VmB().build())
        
        Intent = autoclass('android.content.Intent')
        Uri = autoclass('android.net.Uri')
        File = autoclass('java.io.File')
        
        intent = Intent(Intent.ACTION_SEND)
        intent.setType("application/vnd.google-earth.kml+xml")
        intent.putExtra(Intent.EXTRA_STREAM, Uri.fromFile(File(filepath)))
        intent.setPackage("com.whatsapp")
        
        try:
            PA = autoclass('org.kivy.android.PythonActivity')
        except Exception:
            PA = autoclass('org.renpy.android.PythonActivity')
            
        currentActivity = cast('android.app.Activity', PA.mActivity)
        currentActivity.startActivity(intent)
        return True, "Opened WhatsApp"
    except Exception as e:
        return False, str(e)

# =====================================================
# KML open - Google Earth (Android)
# =====================================================
def auto_open_kml(filepath):
    if platform != 'android':
        return False, "PC test mode"

    import subprocess
    errors = []

    try:
        result = subprocess.run(
            ['am', 'start', '-n', 'com.google.earth/.EarthActivity', '-a', 'android.intent.action.VIEW', '-d', f'file://{filepath}', '-t', 'application/vnd.google-earth.kml+xml', '--activity-brought-to-front'],
            capture_output=True, text=True, timeout=8
        )
        if result.returncode == 0 and 'Error' not in result.stdout + result.stderr:
            return True, "Google Earth opened"
    except Exception as e: pass

    try:
        from jnius import autoclass, cast
        StrictMode = autoclass('android.os.StrictMode')
        VmB = autoclass('android.os.StrictMode$VmPolicy$Builder')
        StrictMode.setVmPolicy(VmB().build())
        Intent = autoclass('android.content.Intent')
        Uri = autoclass('android.net.Uri')
        File = autoclass('java.io.File')
        try: PA = autoclass('org.kivy.android.PythonActivity')
        except Exception: PA = autoclass('org.renpy.android.PythonActivity')
        intent = Intent(Intent.ACTION_VIEW)
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | 0x00000001)
        uri = Uri.fromFile(File(filepath))
        intent.setDataAndType(uri, "application/vnd.google-earth.kml+xml")
        act = cast('android.app.Activity', PA.mActivity)
        act.startActivity(intent)
        return True, "jnius opened"
    except Exception as e: return False, str(e)

# =====================================================
# KV Layout (Fully English)
# =====================================================
KV = '''
<MenuHeader@BoxLayout>:
    size_hint_y: None
    height: '50dp'
    canvas.before:
        Color:
            rgba: 0.12, 0.22, 0.32, 1
        Rectangle:
            pos: self.pos
            size: self.size
    Button:
        text: "Home"
        background_color: 0,0,0,0
        on_release: app.root.current = 'main'
    Button:
        text: "Help"
        background_color: 0,0,0,0
        on_release: app.root.current = 'help'
    Button:
        text: "About"
        background_color: 0,0,0,0
        on_release: app.root.current = 'about'

<MainScreen>:
    name: 'main'
    canvas.before:
        Color:
            rgba: 0.08, 0.08, 0.12, 1
        Rectangle:
            pos: self.pos
            size: self.size
    BoxLayout:
        orientation: 'vertical'
        MenuHeader:
        ScrollView:
            do_scroll_x: False
            BoxLayout:
                orientation: 'vertical'
                padding: '12dp'
                spacing: '12dp'
                size_hint_y: None
                height: self.minimum_height

                # ===== DXF Section =====
                BoxLayout:
                    orientation: 'vertical'
                    size_hint_y: None
                    height: self.minimum_height
                    padding: '14dp'
                    spacing: '8dp'
                    canvas.before:
                        Color:
                            rgba: 0.18, 0.28, 0.38, 0.6
                        RoundedRectangle:
                            pos: self.pos
                            size: self.size
                            radius: [12]

                    Label:
                        text: "DXF  →  KML Converter"
                        font_size: '17sp'
                        bold: True
                        size_hint_y: None
                        height: '36dp'
                        color: 0.5, 0.85, 1, 1
                        halign: 'left'
                        text_size: self.size
                        valign: 'middle'

                    Button:
                        text: "📂  Select DXF File"
                        size_hint_y: None
                        height: '46dp'
                        background_normal: ''
                        background_color: 0.18, 0.42, 0.82, 1
                        on_release: app.open_file_chooser()

                    Label:
                        id: file_label
                        text: "No DXF file selected..."
                        color: 0.55, 0.55, 0.55, 1
                        size_hint_y: None
                        height: '26dp'
                        halign: 'center'
                        text_size: self.size

                    Button:
                        id: layer_btn
                        text: "🗂  Select Layers & Colors"
                        size_hint_y: None
                        height: '0dp'
                        opacity: 0
                        disabled: True
                        background_normal: ''
                        background_color: 0.3, 0.2, 0.55, 1
                        on_release: app.show_layer_selector()

                    Label:
                        id: layer_status_label
                        text: ""
                        color: 0.7, 0.7, 1, 1
                        size_hint_y: None
                        height: '0dp'
                        halign: 'center'
                        text_size: self.size

                    Label:
                        text: "Save Folder for KML:"
                        size_hint_y: None
                        height: '22dp'
                        color: 0.7, 0.7, 0.7, 1
                        halign: 'left'
                        text_size: self.size

                    BoxLayout:
                        size_hint_y: None
                        height: '42dp'
                        spacing: '6dp'
                        TextInput:
                            id: save_path_input
                            text: "/storage/emulated/0/Download/"
                            multiline: False
                            font_size: '12sp'
                            background_color: 0.1, 0.1, 0.15, 1
                            foreground_color: 1, 1, 1, 1
                            cursor_color: 0.5, 0.8, 1, 1
                        Button:
                            text: "📁"
                            size_hint_x: None
                            width: '46dp'
                            background_normal: ''
                            background_color: 0.3, 0.3, 0.5, 1
                            on_release: app.open_save_folder_chooser()

                    Button:
                        id: convert_btn
                        text: "🔄  Convert & Create KML"
                        size_hint_y: None
                        height: '48dp'
                        background_normal: ''
                        background_color: 0.08, 0.6, 0.28, 1
                        on_release: app.convert_dxf()

                    BoxLayout:
                        id: progress_box
                        orientation: 'vertical'
                        size_hint_y: None
                        height: '0dp'
                        opacity: 0
                        spacing: '3dp'
                        Label:
                            id: progress_label
                            text: ""
                            font_size: '12sp'
                            color: 1, 1, 0.5, 1
                            size_hint_y: None
                            height: '20dp'
                        ProgressBar:
                            id: convert_progress
                            max: 100
                            value: 0

                    Label:
                        id: convert_status
                        text: ""
                        color: 0.6, 1, 0.65, 1
                        size_hint_y: None
                        height: '0dp'
                        text_size: self.width, None
                        halign: 'center'
                        valign: 'top'
                        
                    Button:
                        id: share_kml_btn
                        text: "💬 Share KML via WhatsApp"
                        size_hint_y: None
                        height: '0dp'
                        opacity: 0
                        disabled: True
                        background_normal: ''
                        background_color: 0.15, 0.82, 0.35, 1
                        on_release: app.share_kml()

                # ===== GPS Section =====
                BoxLayout:
                    orientation: 'vertical'
                    size_hint_y: None
                    height: self.minimum_height
                    padding: '14dp'
                    spacing: '8dp'
                    canvas.before:
                        Color:
                            rgba: 0.28, 0.18, 0.08, 0.6
                        RoundedRectangle:
                            pos: self.pos
                            size: self.size
                            radius: [12]

                    Label:
                        text: "Current Location (GPS)"
                        font_size: '17sp'
                        bold: True
                        size_hint_y: None
                        height: '36dp'
                        color: 1, 0.78, 0.3, 1
                        halign: 'left'
                        text_size: self.size
                        valign: 'middle'

                    Button:
                        id: gps_btn
                        text: "📍  Get Coordinates"
                        size_hint_y: None
                        height: '46dp'
                        background_normal: ''
                        background_color: 0.72, 0.32, 0.08, 1
                        on_release: app.toggle_gps()

                    Label:
                        id: gps_timer_label
                        text: ""
                        font_size: '12sp'
                        color: 1, 0.9, 0.4, 1
                        size_hint_y: None
                        height: '20dp'

                    Label:
                        id: gps_label
                        text: "Press the button to get coordinates."
                        font_size: '14sp'
                        color: 0.9, 0.9, 0.9, 1
                        size_hint_y: None
                        height: '140dp'
                        text_size: self.width, None
                        halign: 'center'
                        valign: 'top'

                    Button:
                        id: share_gps_btn
                        text: "💬 Share Location via WhatsApp"
                        size_hint_y: None
                        height: '0dp'
                        opacity: 0
                        disabled: True
                        background_normal: ''
                        background_color: 0.15, 0.82, 0.35, 1
                        on_release: app.share_gps()

<HelpScreen>:
    name: 'help'
    canvas.before:
        Color:
            rgba: 0.08, 0.08, 0.12, 1
        Rectangle:
            pos: self.pos
            size: self.size
    BoxLayout:
        orientation: 'vertical'
        MenuHeader:
        ScrollView:
            BoxLayout:
                padding: '16dp'
                size_hint_y: None
                height: self.minimum_height
                Label:
                    text: "[b][color=66ddff]DXF → KML:[/color][/b]\\n  1. Select your DXF file.\\n  2. Check or uncheck layers using the 'Select Layers' button.\\n  3. Tap the color dot to assign different colors.\\n  4. Choose your Save Folder (Default: Download).\\n  5. Press Convert. Google Earth will open automatically.\\n  6. Use the WhatsApp button to share the generated KML file.\\n\\n[b][color=ffcc44]GPS Coordinates:[/color][/b]\\n  1. Ensure Phone Location/GPS Settings are ON.\\n  2. Press 'Get Coordinates'.\\n  3. Stay in an open outdoor area for best signal.\\n  4. WGS84 (Lat/Lon) and SLD99 (North/East) will be displayed.\\n  5. Share the location directly via WhatsApp."
                    markup: True
                    text_size: self.width, None
                    size_hint_y: None
                    height: self.texture_size[1]
                    valign: 'top'

<AboutScreen>:
    name: 'about'
    canvas.before:
        Color:
            rgba: 0.08, 0.08, 0.12, 1
        Rectangle:
            pos: self.pos
            size: self.size
    BoxLayout:
        orientation: 'vertical'
        MenuHeader:
        BoxLayout:
            orientation: 'vertical'
            padding: '30dp'
            spacing: '18dp'
            Label:
                text: "SurveyMap SL"
                font_size: '26sp'
                bold: True
                color: 0.5, 0.85, 1, 1
            Label:
                text: "Version 4.1"
                color: 0.5, 0.5, 0.5, 1
            Label:
                text: "Developed by:\\nV.R.S. Vithana"
                font_size: '17sp'
                halign: 'center'
            Label:
                text: "SLD99 / WGS84 Converter & KML Generator"
                color: 0.6, 0.6, 0.6, 1
                halign: 'center'
                text_size: self.width, None
'''

# =====================================================
# Screen Classes
# =====================================================
class MainScreen(Screen): pass
class HelpScreen(Screen): pass
class AboutScreen(Screen): pass

# =====================================================
# App Class
# =====================================================
class SurveyApp(App):
    is_gps_running = False
    _gps_timeout_event = None
    _gps_timer_event = None
    _gps_elapsed = 0
    _layer_data = {}
    
    # Store data for sharing
    _last_kml_path = None
    _last_gps_text = None

    def on_start(self):
        # Request necessary permissions securely at startup
        request_android_permissions()

    def build(self):
        Builder.load_string(KV)
        self.selected_file_path = None
        sm = ScreenManager()
        sm.add_widget(MainScreen(name='main'))
        sm.add_widget(HelpScreen(name='help'))
        sm.add_widget(AboutScreen(name='about'))
        return sm
        
    # =================================================
    # Sharing Setup
    # =================================================
    def share_kml(self):
        if self._last_kml_path:
            success, msg = share_file_whatsapp(self._last_kml_path)
            if not success:
                self._set_convert_status(f"⚠ Share Error: {msg}")

    def share_gps(self):
        if self._last_gps_text:
            success, msg = share_text_whatsapp(self._last_gps_text)
            if not success:
                self._set_gps_label(f"{self.root.get_screen('main').ids.gps_label.text}\n\n⚠ Share Error: {msg}")

    # =================================================
    # GPS Tracking Thread (JNI)
    # =================================================
    def toggle_gps(self):
        if self.is_gps_running:
            self._cancel_gps_timers()
            self.is_gps_running = False
            try: self.root.get_screen('main').ids.gps_btn.text = "📍  Get Coordinates"
            except Exception: pass
            self._set_gps_label("GPS stopped.")
            self._set_gps_timer("")
            return

        if platform == 'android':
            # Hide share button initially
            main = self.root.get_screen('main')
            main.ids.share_gps_btn.height = '0dp'
            main.ids.share_gps_btn.opacity = 0
            main.ids.share_gps_btn.disabled = True
            
            threading.Thread(target=self._gps_fetch_thread, daemon=True).start()
        else:
            self._set_gps_label("GPS works on Android devices only.")

    def _gps_fetch_thread(self):
        import traceback, time
        def show(msg): Clock.schedule_once(lambda dt: self._set_gps_label(msg))

        try:
            from jnius import autoclass
            try:
                ActivityThread = autoclass('android.app.ActivityThread')
                app_context = ActivityThread.currentApplication().getApplicationContext()
            except Exception as e1:
                show(f"❌ Cannot access Android context.\nEnsure Location permission is allowed in Settings.")
                self._cancel_gps_timers()
                self.is_gps_running = False
                return

            Context = autoclass('android.content.Context')
            LM_cls  = autoclass('android.location.LocationManager')
            lm = app_context.getSystemService(Context.LOCATION_SERVICE)

            GPS_P     = LM_cls.GPS_PROVIDER
            NET_P     = LM_cls.NETWORK_PROVIDER
            PASSIVE_P = LM_cls.PASSIVE_PROVIDER

            # Permissions
            try:
                PackageManager  = autoclass('android.content.pm.PackageManager')
                PERMISSION_FINE = "android.permission.ACCESS_FINE_LOCATION"
                if app_context.checkSelfPermission(PERMISSION_FINE) != PackageManager.PERMISSION_GRANTED:
                    show("❌ Location permission NOT granted!\nPlease allow Location in App Settings.")
                    self._cancel_gps_timers()
                    self.is_gps_running = False
                    return
            except Exception: pass

            gps_on = False; net_on = False
            try:
                gps_on = lm.isProviderEnabled(GPS_P)
                net_on = lm.isProviderEnabled(NET_P)
            except Exception: pass

            if not gps_on and not net_on:
                show("⚠ Phone Location is OFF!\nPlease turn on GPS in your Phone Settings.")
                self._cancel_gps_timers()
                self.is_gps_running = False
                return

            Clock.schedule_once(lambda dt: self._set_gps_timer("Connecting to satellites..."))

            rough_loc = None
            for provider in [NET_P, GPS_P, PASSIVE_P]:
                try:
                    loc = lm.getLastKnownLocation(provider)
                    if loc is not None:
                        rough_loc = loc; break
                except Exception: pass

            self.is_gps_running = True
            self._gps_elapsed = 0
            Clock.schedule_once(lambda dt: self._set_btn_stop())
            self._gps_timer_event = Clock.schedule_interval(self._gps_count, 1)
            self._gps_timeout_event = Clock.schedule_once(self._gps_timed_out, GPS_TIMEOUT)

            start_time = time.time()
            best_acc   = 9999.0
            best_loc   = rough_loc

            while self.is_gps_running and (time.time() - start_time) < GPS_TIMEOUT:
                time.sleep(2)
                if not self.is_gps_running: break
                try:
                    for p in [GPS_P, NET_P]:
                        gloc = lm.getLastKnownLocation(p)
                        if gloc is None: continue
                        acc = gloc.getAccuracy()
                        if acc < best_acc - 2:
                            best_acc = acc
                            best_loc = gloc
                            lat = gloc.getLatitude()
                            lon = gloc.getLongitude()
                            alt = gloc.getAltitude()
                            if acc <= 20.0:
                                Clock.schedule_once(lambda dt, la=lat, lo=lon, al=alt, ac=acc: self._gps_done(la, lo, al, ac, live=True))
                                return
                            
                            Clock.schedule_once(lambda dt, la=lat, lo=lon, al=alt, ac=acc: self._set_gps_label(
                                    f"🛰 Improving Signal...\nLat: {la:.6f}°\nLon: {lo:.6f}°\nAccuracy: ±{ac:.0f} m"
                                ))
                except Exception: pass

            if self.is_gps_running:
                if best_loc is not None:
                    lat = best_loc.getLatitude()
                    lon = best_loc.getLongitude()
                    alt = best_loc.getAltitude()
                    acc = best_loc.getAccuracy()
                    Clock.schedule_once(lambda dt, la=lat, lo=lon, al=alt, ac=acc: self._gps_done(la, lo, al, ac, live=False))
                else:
                    show("⏰ Timeout — No location found.\nMove to an open area outside.")
                    self._cancel_gps_timers()
                    self.is_gps_running = False
                    Clock.schedule_once(lambda dt: setattr(self.root.get_screen('main').ids.gps_btn, 'text', '📍  Get Coordinates'))

        except Exception as e:
            show(f"❌ GPS Error:\n{str(e)[:120]}")
            self._cancel_gps_timers()
            self.is_gps_running = False

    def _set_btn_stop(self):
        try: self.root.get_screen('main').ids.gps_btn.text = "⏹  Stop GPS"
        except Exception: pass

    def _gps_done(self, lat, lon, alt, acc, live=True):
        self._cancel_gps_timers()
        self.is_gps_running = False
        try: self.root.get_screen('main').ids.gps_btn.text = "📍  Get Coordinates"
        except Exception: pass
        
        # SLD99 Transformation
        east, north = wgs84_to_sld99(lon, lat)
        
        tag = "✅ Live GPS" if live else "📍 Best Available"
        final_text = (
            f"--- WGS84 ---\n"
            f"Lat: {lat:.6f}°\n"
            f"Lon: {lon:.6f}°\n"
            f"--- SLD99 ---\n"
            f"North: {north:.3f} m\n"
            f"East: {east:.3f} m\n"
            f"Accuracy: ±{acc:.0f} m"
        )
        
        # Save text for WhatsApp Share
        self._last_gps_text = f"📍 Location Survey Data\n\n{final_text}\n\nMap: https://maps.google.com/?q={lat},{lon}"
        
        self._set_gps_label(f"{tag}:\n{final_text}")
        self._set_gps_timer("")
        
        # Show WhatsApp Button
        main = self.root.get_screen('main')
        main.ids.share_gps_btn.height = '48dp'
        main.ids.share_gps_btn.opacity = 1
        main.ids.share_gps_btn.disabled = False

    def _gps_count(self, dt):
        self._gps_elapsed += 1
        self._set_gps_timer(f"⏱  {self._gps_elapsed}s / {GPS_TIMEOUT}s")

    def _gps_timed_out(self, dt):
        self.is_gps_running = False
        self._cancel_gps_timers()

    def _cancel_gps_timers(self):
        if self._gps_timeout_event:
            self._gps_timeout_event.cancel(); self._gps_timeout_event = None
        if self._gps_timer_event:
            self._gps_timer_event.cancel(); self._gps_timer_event = None

    def _set_gps_label(self, t):
        try: self.root.get_screen('main').ids.gps_label.text = t
        except Exception: pass

    def _set_gps_timer(self, t):
        try: self.root.get_screen('main').ids.gps_timer_label.text = t
        except Exception: pass

    def _set_convert_status(self, t):
        try: self.root.get_screen('main').ids.convert_status.text = t
        except Exception: pass

    # =================================================
    # DXF / KML Converter Logic
    # =================================================
    def open_file_chooser(self):
        layout = BoxLayout(orientation='vertical')
        fc = FileChooserListView(path='/storage/emulated/0/', filters=['*.dxf', '*.DXF'])
        layout.add_widget(fc)
        row = BoxLayout(size_hint_y=None, height='52dp', spacing='8dp', padding='8dp')
        row.add_widget(Button(text="Cancel", background_color=(.8,.2,.2,1), on_release=lambda x: self._dxf_pop.dismiss()))
        row.add_widget(Button(text="Select ✓", background_color=(.1,.7,.3,1), on_release=lambda x: self._on_dxf_selected(fc.selection)))
        layout.add_widget(row)
        self._dxf_pop = Popup(title="Select DXF File", content=layout, size_hint=(.96,.93))
        self._dxf_pop.open()

    def _on_dxf_selected(self, sel):
        if sel:
            self.selected_file_path = sel[0]
            fname = os.path.basename(self.selected_file_path)
            dxf_dir = os.path.dirname(self.selected_file_path) + "/"
            main = self.root.get_screen('main')
            main.ids.file_label.text = f"✅  {fname}"
            main.ids.file_label.color = (.3, 1, .45, 1)
            main.ids.save_path_input.text = dxf_dir
            main.ids.layer_btn.height = '42dp'
            main.ids.layer_btn.opacity = 1
            main.ids.layer_btn.disabled = False
            main.ids.share_kml_btn.height = '0dp'
            main.ids.share_kml_btn.opacity = 0
            main.ids.share_kml_btn.disabled = True
            threading.Thread(target=self._scan_layers, daemon=True).start()
        self._dxf_pop.dismiss()

    def _scan_layers(self):
        try:
            import ezdxf
            doc = ezdxf.readfile(self.selected_file_path)
            msp = doc.modelspace()
            layers_found = {}
            for e in msp:
                if e.dxftype() in ['LWPOLYLINE', 'POLYLINE', 'LINE']:
                    ln = e.dxf.layer if hasattr(e.dxf, 'layer') else '0'
                    if ln not in layers_found:
                        idx = len(layers_found)
                        cname, ckml = get_layer_color(idx)
                        layers_found[ln] = {'enabled': True, 'color_name': cname, 'color_kml': ckml, 'count': 0}
                    layers_found[ln]['count'] += 1

            self._layer_data = layers_found
            Clock.schedule_once(lambda dt: self._update_layer_status())
        except Exception as e:
            Clock.schedule_once(lambda dt: self._set_layer_status(f"Scan error: {e}"))

    def _update_layer_status(self):
        n = len(self._layer_data)
        self._set_layer_status(f"{n} layer(s) found. Tap 'Select Layers' to manage.")
        self.root.get_screen('main').ids.layer_status_label.height = '24dp'

    def _set_layer_status(self, t):
        try:
            self.root.get_screen('main').ids.layer_status_label.text = t
            self.root.get_screen('main').ids.layer_status_label.height = '24dp'
        except Exception: pass

    def show_layer_selector(self):
        if not self._layer_data: return
        outer = BoxLayout(orientation='vertical', spacing='8dp', padding='10dp')
        outer.add_widget(Label(text="[b]Layer Manager[/b]", markup=True, size_hint_y=None, height='32dp', color=(.5,.85,1,1)))
        outer.add_widget(Label(text="Check = Include in KML  |  Tap color to change", size_hint_y=None, height='22dp', font_size='12sp', color=(.7,.7,.7,1)))

        scroll = ScrollView(size_hint=(1, 1))
        grid = GridLayout(cols=1, size_hint_y=None, spacing='4dp', padding='4dp')
        grid.bind(minimum_height=grid.setter('height'))

        self._layer_checkboxes = {}
        for lname, ldata in self._layer_data.items():
            row = BoxLayout(size_hint_y=None, height='46dp', spacing='8dp')
            cb = CheckBox(size_hint_x=None, width='40dp', active=ldata['enabled'])
            self._layer_checkboxes[lname] = cb
            rgb = kml_color_to_rgb(ldata['color_kml'])
            color_btn = Button(size_hint_x=None, width='44dp', background_normal='', background_color=(rgb[0], rgb[1], rgb[2], 1), text='')
            color_btn._layer_name = lname
            color_btn.bind(on_release=self._cycle_layer_color)
            lbl = Label(text=f"{lname}  ({ldata['count']} items)  [{ldata['color_name']}]", halign='left', valign='middle', text_size=(None, None), font_size='13sp')
            lbl.bind(size=lambda inst, val: setattr(inst, 'text_size', (val[0], None)))

            row.add_widget(cb); row.add_widget(color_btn); row.add_widget(lbl)
            grid.add_widget(row)
            ldata['_lbl'] = lbl; ldata['_color_btn'] = color_btn

        scroll.add_widget(grid)
        outer.add_widget(scroll)

        btn_row = BoxLayout(size_hint_y=None, height='48dp', spacing='8dp')
        btn_row.add_widget(Button(text="Select All", background_normal='', background_color=(.2,.5,.8,1), on_release=lambda x: self._select_all_layers(True)))
        btn_row.add_widget(Button(text="Deselect", background_normal='', background_color=(.5,.2,.2,1), on_release=lambda x: self._select_all_layers(False)))
        btn_row.add_widget(Button(text="✓  Done", background_normal='', background_color=(.1,.65,.3,1), on_release=self._apply_layer_selection))
        outer.add_widget(btn_row)

        self._layer_pop = Popup(title="Layer Manager", content=outer, size_hint=(.95, .88))
        self._layer_pop.open()

    def _cycle_layer_color(self, btn):
        lname = btn._layer_name
        ldata = self._layer_data[lname]
        cur_idx = next((i for i, c in enumerate(LAYER_COLORS_HEX) if c[1] == ldata['color_kml']), 0)
        next_idx = (cur_idx + 1) % len(LAYER_COLORS_HEX)
        cname, ckml = LAYER_COLORS_HEX[next_idx]
        ldata['color_name'] = cname; ldata['color_kml'] = ckml
        rgb = kml_color_to_rgb(ckml)
        btn.background_color = (rgb[0], rgb[1], rgb[2], 1)
        ldata['_lbl'].text = f"{lname}  ({ldata['count']} items)  [{cname}]"

    def _select_all_layers(self, state):
        for cb in self._layer_checkboxes.values(): cb.active = state

    def _apply_layer_selection(self, *args):
        for lname, cb in self._layer_checkboxes.items(): self._layer_data[lname]['enabled'] = cb.active
        enabled = sum(1 for l in self._layer_data.values() if l['enabled'])
        self._set_layer_status(f"✅ {enabled}/{len(self._layer_data)} layers selected.")
        self._layer_pop.dismiss()

    def open_save_folder_chooser(self):
        layout = BoxLayout(orientation='vertical')
        cur = self.root.get_screen('main').ids.save_path_input.text
        start = cur if os.path.isdir(cur) else '/storage/emulated/0/'
        fc = FileChooserListView(path=start, dirselect=True)
        layout.add_widget(fc)
        row = BoxLayout(size_hint_y=None, height='52dp', spacing='8dp', padding='8dp')
        row.add_widget(Button(text="Cancel", background_color=(.8,.2,.2,1), on_release=lambda x: self._folder_pop.dismiss()))
        row.add_widget(Button(text="Select ✓", background_color=(.15,.5,.85,1), on_release=lambda x: self._set_save_folder(fc.path)))
        layout.add_widget(row)
        self._folder_pop = Popup(title="Save Folder", content=layout, size_hint=(.96,.93))
        self._folder_pop.open()

    def _set_save_folder(self, path):
        self.root.get_screen('main').ids.save_path_input.text = path.rstrip('/') + '/'
        self._folder_pop.dismiss()

    def convert_dxf(self):
        main = self.root.get_screen('main')
        if not self.selected_file_path:
            main.ids.file_label.text = "❌  Please select a DXF file first!"
            main.ids.file_label.color = (1,.3,.3,1)
            return
            
        main.ids.share_kml_btn.height = '0dp'
        main.ids.share_kml_btn.opacity = 0
        main.ids.share_kml_btn.disabled = True
            
        main.ids.convert_btn.disabled = True
        main.ids.convert_btn.text = "⏳  Converting..."
        main.ids.progress_box.height = '52dp'
        main.ids.progress_box.opacity = 1
        main.ids.convert_progress.value = 0
        main.ids.progress_label.text = "Preparing..."
        main.ids.convert_status.text = ""
        main.ids.convert_status.height = '0dp'
        threading.Thread(target=self._run_conversion, daemon=True).start()

    def _run_conversion(self):
        def upd(v, msg): Clock.schedule_once(lambda dt: self._set_progress(v, msg))
        def done(ok, msg, path=None): Clock.schedule_once(lambda dt: self._finish(ok, msg, path))

        try: import ezdxf
        except ImportError:
            done(False, "❌ ezdxf not installed!"); return

        try:
            upd(10, "Reading DXF file...")
            doc = ezdxf.readfile(self.selected_file_path)
            msp = doc.modelspace()
            upd(20, "Scanning entities...")
            entities = [e for e in msp if e.dxftype() in ['LWPOLYLINE','POLYLINE','LINE']]
            total = max(len(entities), 1)

            active_layers = {ln for ln, ld in self._layer_data.items() if ld.get('enabled', True)} if self._layer_data else None
            upd(30, f"{len(entities)} entities found...")

            styles_xml = ""
            for ln, ld in self._layer_data.items():
                if not ld.get('enabled', True): continue
                style_id = ln.replace(' ', '_').replace('/', '_')
                styles_xml += f'  <Style id="layer_{style_id}"><LineStyle><color>{ld["color_kml"]}</color><width>2</width></LineStyle></Style>\n'
            styles_xml += '  <Style id="layer_default"><LineStyle><color>ff0000ff</color><width>2</width></LineStyle></Style>\n'

            kml = '<?xml version="1.0" encoding="UTF-8"?>\n<kml xmlns="http://www.opengis.net/kml/2.2">\n<Document>\n  <n>Survey Plan - SLD99</n>\n' + styles_xml
            lines_found = 0; skipped = 0

            for i, entity in enumerate(entities):
                if i % 10 == 0:
                    upd(30 + int((i / total) * 55), f"Converting {i+1} / {total}...")
                try:
                    layer_name = entity.dxf.layer if hasattr(entity.dxf, 'layer') else '0'
                    if active_layers is not None and layer_name not in active_layers:
                        skipped += 1; continue

                    style_id = layer_name.replace(' ', '_').replace('/', '_')
                    style_ref = f"layer_{style_id}" if layer_name in self._layer_data else "layer_default"

                    if entity.dxftype() in ['LWPOLYLINE', 'POLYLINE']:
                        pts = list(entity.get_points('xy')) if entity.dxftype() == 'LWPOLYLINE' else list(entity.points())
                        if len(pts) < 2: continue
                        coords = " ".join(f"{sld99_to_wgs84(p[0],p[1])[0]:.7f},{sld99_to_wgs84(p[0],p[1])[1]:.7f},0" for p in pts)
                    elif entity.dxftype() == 'LINE':
                        s = entity.dxf.start; e2 = entity.dxf.end
                        l1 = sld99_to_wgs84(s[0], s[1]); l2 = sld99_to_wgs84(e2[0], e2[1])
                        coords = f"{l1[0]:.7f},{l1[1]:.7f},0 {l2[0]:.7f},{l2[1]:.7f},0"
                    else: continue

                    kml += f'  <Placemark><n>{layer_name} #{lines_found+1}</n><styleUrl>#{style_ref}</styleUrl><LineString><tessellate>1</tessellate><coordinates>{coords}</coordinates></LineString></Placemark>\n'
                    lines_found += 1
                except Exception: continue

            kml += '</Document>\n</kml>'

            if lines_found == 0:
                done(False, "❌ No convertible entities found!")
                return

            upd(88, "Saving KML file...")
            save_folder = self.root.get_screen('main').ids.save_path_input.text.strip()
            os.makedirs(save_folder, exist_ok=True)
            base = os.path.splitext(os.path.basename(self.selected_file_path))[0]
            save_path = os.path.join(save_folder, base + ".kml")

            if os.path.exists(save_path):
                self._pending_kml = kml
                self._pending_save_path = save_path
                self._pending_lines = lines_found
                self._pending_skipped = skipped
                Clock.schedule_once(lambda dt: self._show_overwrite_popup())
                return

            with open(save_path, 'w', encoding='utf-8') as f:
                f.write(kml)

            upd(100, "✅ Done!")
            done(True, f"✅ KML created!\n{lines_found} lines converted.\n📁 {save_path}", save_path)

        except Exception as e:
            done(False, f"❌ Error:\n{str(e)[:80]}")

    def _show_overwrite_popup(self):
        base_path = self._pending_save_path
        fname = os.path.basename(base_path)
        folder  = os.path.dirname(base_path)

        content = BoxLayout(orientation='vertical', spacing='8dp', padding='12dp')
        content.add_widget(Label(text=f"[b]File already exists![/b]\n\n[color=ffcc44]{fname}[/color]\n\nOverwrite or New Name?", markup=True, halign='center', size_hint_y=None, height='90dp'))

        btn_row = BoxLayout(size_hint_y=None, height='48dp', spacing='8dp')
        pop = Popup(title="File Exists", content=content, size_hint=(.88, .42))

        def do_overwrite(x):
            pop.dismiss()
            self._save_kml_final(base_path, overwrite=True)

        def do_new_name(x):
            pop.dismiss()
            base_no_ext = os.path.splitext(fname)[0]
            counter = 1
            while True:
                new_path = os.path.join(folder, f"{base_no_ext}_{counter}.kml")
                if not os.path.exists(new_path): break
                counter += 1
            self._save_kml_final(new_path, overwrite=False)

        def do_cancel(x):
            pop.dismiss()
            self._reset_convert_ui("Save cancelled.")

        btn_row.add_widget(Button(text="Overwrite", background_color=(.8,.3,.1,1), on_release=do_overwrite))
        btn_row.add_widget(Button(text="New Name", background_color=(.1,.5,.85,1), on_release=do_new_name))
        btn_row.add_widget(Button(text="Cancel", background_color=(.35,.35,.35,1), on_release=do_cancel))
        content.add_widget(btn_row)
        pop.open()

    def _save_kml_final(self, save_path, overwrite):
        try:
            with open(save_path, 'w', encoding='utf-8') as f:
                f.write(self._pending_kml)
            tag = "Overwritten" if overwrite else "New File"
            self._finish(True, f"✅ KML Saved! ({tag})\n{self._pending_lines} lines.\n📁 {save_path}", save_path)
        except Exception as e:
            self._finish(False, f"❌ Save error: {e}")

    def _reset_convert_ui(self, status_msg=""):
        try:
            main = self.root.get_screen('main')
            main.ids.progress_box.height = '0dp'
            main.ids.progress_box.opacity = 0
            main.ids.convert_btn.disabled = False
            main.ids.convert_btn.text = "🔄  Convert & Create KML"
            if status_msg:
                main.ids.convert_status.text = status_msg
                main.ids.convert_status.height = '40dp'
                main.ids.convert_status.color = (.6,.6,.6,1)
        except Exception: pass

    def _set_progress(self, val, msg):
        try:
            main = self.root.get_screen('main')
            main.ids.convert_progress.value = val
            main.ids.progress_label.text = msg
        except Exception: pass

    def _finish(self, ok, msg, path=None):
        try:
            main = self.root.get_screen('main')
            main.ids.progress_box.height = '0dp'
            main.ids.progress_box.opacity = 0
            main.ids.convert_btn.disabled = False
            main.ids.convert_btn.text = "🔄  Convert & Create KML"
            main.ids.convert_status.text = msg
            main.ids.convert_status.height = '90dp'
            main.ids.convert_status.color = (.3,1,.5,1) if ok else (1,.4,.4,1)
            
            if ok and path:
                self._last_kml_path = path
                # Show WhatsApp Button
                main.ids.share_kml_btn.height = '48dp'
                main.ids.share_kml_btn.opacity = 1
                main.ids.share_kml_btn.disabled = False
                
                opened, err_msg = auto_open_kml(path)
                if not opened:
                    main.ids.convert_status.text += f"\n\n⚠ Auto-open failed:\n{err_msg[:80]}\n📁 Open manually."
        except Exception as e: print(f"Finish error: {e}")

if __name__ == '__main__':
    SurveyApp().run()


