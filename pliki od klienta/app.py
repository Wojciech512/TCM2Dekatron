# -*- coding: utf-8 -*-

from __future__ import annotations
import os, time, json, threading
from collections import deque
from functools import wraps
from threading import Thread, Lock
from flask import Flask, request, redirect, url_for, session, render_template, flash, jsonify, send_file, Response

# ---- Optional HW libs (on Raspberry Pi) ----
try:
    import RPi.GPIO as GPIO
    import spidev
    import Adafruit_DHT
except ImportError:
    GPIO = None
    spidev = None
    Adafruit_DHT = None

# ===================
# App / config
# ===================
app = Flask(__name__)
app.secret_key = 'tcm_secret_key'
CONFIG_FILE = 'config.json'
LOG_FILE = 'events.log'
MAX_LOG_ENTRIES = 1000

# GPIO / peripherals
BUZZER_PIN = 22
DHT_SENSOR = Adafruit_DHT.DHT11 if Adafruit_DHT else None
DHT_PIN_BATT = 4
DHT_PIN_CAB = 5

# MCP23S17 registers
IODIRA = 0x00
IODIRB = 0x01
GPIOA  = 0x12
GPIOB  = 0x13
OLATA  = 0x14
OLATB  = 0x15
IOCON  = 0x0A
GPPUA  = 0x0C
GPPUB  = 0x0D

# Strike
STRIKE_DURATION_SEC = 10.0
ALLOWED_STRIKE_TRANSISTORS = [f"T{i}" for i in range(2, 9)]  # T2..T8

# Runtime / state
spi1 = None  # expander 1 (CS: CE0 / GPIO8)
spi2 = None  # expander 2 (CS: CE1 / GPIO7)

last_dht = {'timestamp': 0.0, 'temp_batt': None, 'hum_batt': None, 'temp_cab': None, 'hum_cab': None}

LOGICAL_OUTPUTS = [
    'alarm',        # alarm outputs
    'klimatyzacja', # cooling
    'oświetlenie',  # light
    'grzałka',      # heating
    'went_48v',     # 48 VDC fans
    'went_230v',    # 230 VAC fans
]

LABELS_EN = {
    'alarm': 'ALARM', 'klimatyzacja': 'COOLER', 'oświetlenie': 'LIGHT',
    'grzałka': 'HEATER', 'went_48v': 'FAN 48V', 'went_230v': 'FAN 230V',
}

RT_LOCK = Lock()
RUNTIME = {
    'inputs': {},  # filled dynamically based on input_map
    'sensors': {'temp_batt': None, 'hum_batt': None, 'temp_cab': None, 'hum_cab': None},
    'outputs': {name: False for name in LOGICAL_OUTPUTS},
    'alarm_reason': None,
    'ts': 0.0,
    'error': None,
    'buzzer_muted': False, 

# Control loop intervals
LOGIC_INTERVAL_SEC = 60.0     # full cycle (DHT + logic) every 1 min
FAST_EVENTS_TICK_SEC = 0.25   # quick door scanning
FLOOD_REFRESH_SEC = 120.0     # flood sensors refresh every 2 min (anti-flap)

# Defaults
DEFAULT_CONFIG = {
    "id": "TCM-01",
    "ip": "192.168.0.100",
    "mask": "255.255.255.0",
    "gateway": "192.168.0.1",
    "temp_thresholds": {"grzałka": 5.0, "klimatyzacja": 25.0, "went": 30.0},
    "histereza": 1.0,
    # logic -> hardware mapping (single channel list)
    "mapowania": {
        "alarm": ["K1"],
        "klimatyzacja": ["K2"],
        "oświetlenie": ["K3"],
        "grzałka": ["K4"],
        "went_230v": ["K5"],
        "went_48v": ["T1"],
    },
    # manual mode
    "manual": {"włączony": False, "stany": {name: False for name in LOGICAL_OUTPUTS}},
    # input polarity
    "inputs": {"flood_low_is_flood": True, "door_open_is_high": True, "dip_on_is_high": True},
    # output polarity
    "outputs": {"active_low": {"K": False, "T": False}},
    # users
    "users": {"operator": "operator_tcm", "technik": "technik_tcm", "serwis": "Dekatron5890"},
    # dynamic input map (only GPIOA bits are used): up to 6 doors + 2 floods
    "input_map": {"doors": ["A0", "A1", "A2", "A3"], "flood": ["A4"]},
    # strikes mapping (only T2..T8), visible only if assigned
    "strikes": {
        "strike_1": {"transistor": None},
        "strike_2": {"transistor": None},
        "strike_3": {"transistor": None},
        "strike_4": {"transistor": None},
        "strike_5": {"transistor": None},
        "strike_6": {"transistor": None},
    },
}

# --- Custom hardware mapping (dopasuj do PCB) ---
TRANSISTOR_PIN_MAP = { 
    'T1': 3, 
    'T2': 2,  # T2 -> GPB2
    'T3': 1,  # T3 -> GPB1
    'T4': 0,
    'T5': 4,
    'T6': 5,
    'T7': 6,
    'T8': 7,
}

RELAY_PIN_MAP = { 
    'K1': 0,
    'K2': 1,
    'K3': 2,
    'K4': 3,
    'K5': 4,
    'K6': 5,
    'K7': 6,
    'K8': 7,
}

# Logs (ring buffer + file)
LOGS = deque(maxlen=MAX_LOG_ENTRIES)
LOG_LOCK = Lock()

def now_iso():
    return time.strftime('%Y-%m-%dT%H:%M:%S', time.localtime())

def load_logs_from_file():
    if not os.path.exists(LOG_FILE):
        return
    try:
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            lines = f.readlines()[-MAX_LOG_ENTRIES:]
        with LOG_LOCK:
            LOGS.clear()
            for ln in lines:
                try:
                    LOGS.append(json.loads(ln))
                except Exception:
                    continue
    except Exception:
        pass

def append_log(event_type:str, message:str, meta:dict|None=None):
    rec = {"ts": now_iso(), "type": event_type, "message": message}
    if meta:
        rec["meta"] = meta
    with LOG_LOCK:
        LOGS.append(rec)
        try:
            with open(LOG_FILE, 'a', encoding='utf-8') as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        except Exception:
            pass

# ===================
# Config helpers
# ===================
def load_config() -> dict:
    if not os.path.exists(CONFIG_FILE):
        return json.loads(json.dumps(DEFAULT_CONFIG))
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception:
        data = {}
    def deep_merge(base, add):
        if isinstance(base, dict) and isinstance(add, dict):
            out = dict(base)
            for k, v in add.items():
                out[k] = deep_merge(base.get(k), v)
            return out
        return add if add is not None else base
    cfg = deep_merge(DEFAULT_CONFIG, data)
    # hard limits: 6 doors, 2 flood, only A0..A7 unique
    aopts = [f"A{i}" for i in range(8)]
    doors = [p for p in cfg.get("input_map",{}).get("doors",[]) if p in aopts][:6]
    flood = [p for p in cfg.get("input_map",{}).get("flood",[]) if p in aopts][:2]
    used = []
    fixed_doors, fixed_flood = [], []
    for p in doors:
        if p not in used:
            fixed_doors.append(p); used.append(p)
    for p in flood:
        if p not in used:
            fixed_flood.append(p); used.append(p)
    cfg["input_map"] = {"doors": fixed_doors, "flood": fixed_flood}
    return cfg

def save_config(cfg: dict):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)

# ===================
# Hardware layer
# ===================
def mcp_probe(spi) -> bool:
    try:
        write_reg(spi, IOCON, 0x08)
        v = read_reg(spi, IOCON)
        return bool(v & 0x08)
    except Exception:
        return False

def mcp_init(spi, is_inputs=False):
    """Ustawia tryb pracy portów i podciągi."""
    # HAEN=1, pozostaw BANK=0, SEQOP=0 (sekwencyjny)
    write_reg(spi, IOCON, 0x08)

    if is_inputs:
        # Ekspander 2 = wejścia: GPA0..5 wejścia z pull-up, GPB wejścia (DIP) z pull-up
        write_reg(spi, IODIRA, 0xFF)        # A jako wejścia
        write_reg(spi, GPPUA,  0b0011_1111) # pull-up na A0..A5
        write_reg(spi, IODIRB, 0xFF)        # B jako wejścia
        write_reg(spi, GPPUB,  0xFF)        # pull-up na całym B
    else:
        # Ekspander 1 = wyjścia: oba porty OUT, wyzeruj OLAT
        write_reg(spi, IODIRA, 0x00)
        write_reg(spi, IODIRB, 0x00)
        write_reg(spi, OLATA,  0x00)
        write_reg(spi, OLATB,  0x00)

def hw_init():
    global spi1, spi2
    if GPIO is None or spidev is None:
        print("[HW] Dev mode bez HW – pomijam init SPI.")
        return

    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(BUZZER_PIN, GPIO.OUT, initial=GPIO.LOW)

    # Jeżeli masz „enable” zasilania ekspanderów – ustaw:
    GPIO.setup(25, GPIO.OUT)
    GPIO.output(25, GPIO.HIGH)
    time.sleep(0.05)

    # Otwórz oba urządzenia SPI (CE0, CE1) i spróbuj kilka trybów SPI (0..3)
    def open_and_probe(bus, dev, is_inputs=False):
        s = spidev.SpiDev()
        s.open(bus, dev)
        s.max_speed_hz = 1_000_000
        for mode in (0, 1, 2, 3):
            s.mode = mode
            if mcp_probe(s):
                print(f"[HW] MCP23S17 wykryty na /dev/spi{bus}.{dev} w trybie SPI mode={mode}.")
                mcp_init(s, is_inputs=is_inputs)
                return s
        print(f"[HW] UWAGA: brak odpowiedzi MCP23S17 na /dev/spi{bus}.{dev} (sprawdź okablowanie).")
        return s  # zostaw otwarte, ale bez pewności komunikacji

    # CE0: ekspander wyjść, CE1: ekspander wejść
    spi1 = open_and_probe(0, 0, is_inputs=False)
    spi2 = open_and_probe(0, 1, is_inputs=True)

    # Szybki odczyt sanity-check
    try:
        a = read_reg(spi1, IODIRA); b = read_reg(spi1, IODIRB)
        print(f"[HW] EXP1 IODIR A/B = 0x{a:02X}/0x{b:02X}")
        a2 = read_reg(spi2, IODIRA); b2 = read_reg(spi2, IODIRB)
        print(f"[HW] EXP2 IODIR A/B = 0x{a2:02X}/0x{b2:02X}")
    except Exception as e:
        print("[HW] Błąd sanity-check SPI:", e)


def read_reg(spi, addr):
    if spi is None:
        return 0
    return spi.xfer2([0x41, addr, 0x00])[2]

def write_reg(spi, addr, val):
    if spi is None:
        return
    spi.xfer2([0x40, addr, val & 0xFF])

def read_pin(spi, reg, pin):
    val = read_reg(spi, reg)
    return (val >> pin) & 0x01

def dht_read_buffered():
    now = time.time()
    if (now - last_dht['timestamp']) > 2:
        if Adafruit_DHT:
            hb, tb = Adafruit_DHT.read(DHT_SENSOR, DHT_PIN_BATT)
            hc, tc = Adafruit_DHT.read(DHT_SENSOR, DHT_PIN_CAB)
        else:
            tb, hb = 24.5, 40.0
            tc, hc = 26.0, 38.0
        if tb is not None: last_dht['temp_batt'] = float(tb)
        if hb is not None: last_dht['hum_batt']  = float(hb)
        if tc is not None: last_dht['temp_cab']  = float(tc)
        if hc is not None: last_dht['hum_cab']   = float(hc)
        last_dht['timestamp'] = now
    return (last_dht['temp_batt'], last_dht['hum_batt'], last_dht['temp_cab'], last_dht['hum_cab'])

# ===================
# Inputs (doors/flood/DIP)
# ===================
def _a_label_to_index(lbl:str) -> int:
    lbl = lbl.upper().strip()
    assert lbl.startswith("A")
    idx = int(lbl[1:])
    if not (0 <= idx <= 7): raise ValueError("A-index out of range")
    return idx

def read_inputs_mapped(cfg:dict):
    """Return dict with dynamic keys: door_1..door_N, flood_1..flood_M (no DIP in result)."""
    door_open_is_high = bool(cfg.get('inputs', {}).get('door_open_is_high', True))
    low_is_flood = bool(cfg.get('inputs', {}).get('flood_low_is_flood', True))
    amap = cfg.get("input_map", {"doors":[], "flood":[]})
    # read entire GPIOA once
    a_val = read_reg(spi2, GPIOA) if spi2 else 0x00
    def door_state(bit):
        v = (a_val >> bit) & 0x01
        is_open = bool(v) if door_open_is_high else not bool(v)
        return 'OPEN' if is_open else 'CLOSE'
    def flood_state(bit):
        v = (a_val >> bit) & 0x01
        is_flood = (not bool(v)) if low_is_flood else bool(v)
        return 'FLOOD' if is_flood else 'OK'

    out = {}
    # doors
    for i, lbl in enumerate(amap.get("doors", [])[:6], start=1):
        bit = _a_label_to_index(lbl)
        out[f"door_{i}"] = door_state(bit)
    # floods
    for i, lbl in enumerate(amap.get("flood", [])[:2], start=1):
        bit = _a_label_to_index(lbl)
        out[f"flood_{i}"] = flood_state(bit)
    return out

def service_allowed_at_boot(cfg:dict|None=None) -> bool:
    """Service allowed only if DIP 1,3,5 = ON with configured polarity. No logging, no exposure."""
    if cfg is None: cfg = load_config()
    dip = read_reg(spi2, GPIOB) if spi2 else 0x00
    need = (1<<0) | (1<<2) | (1<<4)
    on_high = bool((dip & need) == need)
    on_low  = bool((((~dip) & 0xFF) & need) == need)
    prefer_high = bool(cfg.get('inputs',{}).get('dip_on_is_high', True))
    allowed = (on_high if prefer_high else on_low)
    if not allowed and (on_high or on_low):
        cfg.setdefault('inputs', {})
        cfg['inputs']['dip_on_is_high'] = True if on_high else False
        save_config(cfg)
        allowed = True
    return allowed

# ===================
# Outputs mapping / write
# ===================
def k_label_to_bank_pin(label:str):
    label = label.upper().strip()
    if label.startswith('K'):
        if label not in RELAY_PIN_MAP:
            raise ValueError(f'Bad relay label (map): {label}')
        return ('A', RELAY_PIN_MAP[label])
    if label.startswith('T'):
        if label not in TRANSISTOR_PIN_MAP:
            raise ValueError(f'Bad transistor label (map): {label}')
        return ('B', TRANSISTOR_PIN_MAP[label])
    raise ValueError('Bad channel label: %r' % label)


def write_outputs_from_logical(cfg:dict, logical_states:dict, force_on_labels:list[str]|None=None):
    active_low = cfg.get('outputs', {}).get('active_low', {"K": False, "T": False})
    a_mask = 0x00 if not active_low.get('K', False) else 0xFF
    b_mask = 0x00 if not active_low.get('T', False) else 0xFF

    force_on_labels = set(force_on_labels or [])

    for lname, is_on in logical_states.items():
        for label in cfg['mapowania'].get(lname, []):
            if label in force_on_labels:
                continue  
            bank, pin = k_label_to_bank_pin(label)
            if bank == 'A':
                if active_low.get('K', False):
                    a_mask = (a_mask & ~(1<<pin)) if is_on else (a_mask | (1<<pin))
                else:
                    a_mask = (a_mask | (1<<pin)) if is_on else (a_mask & ~(1<<pin))
            else:
                if active_low.get('T', False):
                    b_mask = (b_mask & ~(1<<pin)) if is_on else (b_mask | (1<<pin))
                else:
                    b_mask = (b_mask | (1<<pin)) if is_on else (b_mask & ~(1<<pin))

    for label in force_on_labels:
        bank, pin = k_label_to_bank_pin(label)
        if bank == 'A':
            if active_low.get('K', False):
                a_mask &= ~(1<<pin)
            else:
                a_mask |=  (1<<pin)
        else:
            if active_low.get('T', False):
                b_mask &= ~(1<<pin)
            else:
                b_mask |=  (1<<pin)

    write_reg(spi1, OLATA, a_mask)
    write_reg(spi1, OLATB, b_mask)


# ===================
# Control logic
# ===================
def compute_logic(cfg:dict, inputs:dict, temp_cab:float|None):
    th = cfg['temp_thresholds']; H = float(cfg['histereza'])
    st = {name: False for name in LOGICAL_OUTPUTS}; reasons = []

    door_keys = [k for k in inputs.keys() if k.startswith("door_")]
    flood_keys = [k for k in inputs.keys() if k.startswith("flood_")]
    door_open = any(inputs[k] == 'OPEN' for k in door_keys)
    flood = any(inputs[k] == 'FLOOD' for k in flood_keys)

    if door_open:
        st['alarm'] = True
        st['oświetlenie'] = True
        st['grzałka'] = False; st['klimatyzacja'] = False; st['went_48v'] = False; st['went_230v'] = False
        reasons.append('Door open')
        if flood: reasons.append('Flood detected')
        return st, ('; '.join(reasons) if reasons else None)

    if flood:
        st['alarm'] = True
        reasons.append('Flood detected')

    if temp_cab is None:
        st['grzałka'] = False; st['klimatyzacja'] = False
        return st, ('; '.join(reasons) if reasons else None)

    if temp_cab <= th['grzałka']:
        st['grzałka'] = True; st['klimatyzacja'] = False; st['went_48v'] = False; st['went_230v'] = False
    elif temp_cab >= th['grzałka'] + H:
        st['grzałka'] = False

    if temp_cab >= th['klimatyzacja']:
        st['klimatyzacja'] = True; st['grzałka'] = False; st['went_48v'] = False; st['went_230v'] = False
    elif temp_cab <= th['klimatyzacja'] - H:
        st['klimatyzacja'] = False

    if temp_cab >= th['went']:
        st['alarm'] = True; st['went_48v'] = True; st['went_230v'] = True; st['klimatyzacja'] = False; st['grzałka'] = False
        reasons.append('Overtemperature')
    elif temp_cab <= th['went'] - H:
        st['went_48v'] = False; st['went_230v'] = False

    return st, ('; '.join(reasons) if reasons else None)

def drive_buzzer(alarm_active: bool):
    if GPIO is None: return
    with RT_LOCK:
        muted = RUNTIME.get('buzzer_muted', False)
    GPIO.output(BUZZER_PIN, GPIO.HIGH if (alarm_active and not muted) else GPIO.LOW)

STRIKE_TIMERS = {}
STRIKE_LOCK = Lock()

def get_active_force_labels(now_ts:float) -> list[str]:
    with STRIKE_LOCK:
        expired = [lbl for lbl, until in STRIKE_TIMERS.items() if now_ts >= until]
        for lbl in expired:
            del STRIKE_TIMERS[lbl]
        return list(STRIKE_TIMERS.keys())

# Anti-glitch state for doors
DOOR_GLITCH_PENDING = {"active": False, "until": 0.0, "target_state": None, "last_good": {}}

def _doors_all_switched_simultaneously(prev:dict, cur:dict) -> tuple[bool,str|None]:
    """Return (True, 'OPEN'/'CLOSE') if all configured doors flipped to the same state at once."""
    door_keys = sorted([k for k in cur.keys() if k.startswith("door_") and k in prev])
    if not door_keys:
        return (False, None)
    changed = [cur[k] != prev[k] for k in door_keys]
    if all(changed):
        states = {cur[k] for k in door_keys}
        if len(states) == 1:
            return (True, list(states)[0])
    return (False, None)

def control_loop():
    global RUNTIME, DOOR_GLITCH_PENDING
    next_logic_ts = 0.0
    last_fast_inputs = None
    last_flood_ts = 0.0

    # initialize logs from file
    load_logs_from_file()

    while True:
        try:
            now = time.time()
            cfg = load_config()

            # -------- fast path: doors (250 ms), flood only per FLOOD_REFRESH_SEC --------
            fast_inputs = read_inputs_mapped(cfg)

            # freeze flood values between full cycles
            with RT_LOCK:
                prev_inputs = dict(RUNTIME['inputs'])
            if now < (last_flood_ts + FLOOD_REFRESH_SEC):
                for k in list(fast_inputs.keys()):
                    if k.startswith("flood_") and k in prev_inputs:
                        fast_inputs[k] = prev_inputs[k]

            # Anti-glitch: ignore "all doors at once" shorter than 250 ms
            door_glitch, tgt = (False, None)
            if last_fast_inputs is not None:
                door_glitch, tgt = _doors_all_switched_simultaneously(last_fast_inputs, fast_inputs)

            accept_inputs = dict(fast_inputs)
            if door_glitch:
                if not DOOR_GLITCH_PENDING["active"]:
                    DOOR_GLITCH_PENDING = {
                        "active": True,
                        "until": now + 0.250,
                        "target_state": tgt,
                        "last_good": {k:v for k,v in prev_inputs.items() if k.startswith("door_")}
                    }
                    for k,v in DOOR_GLITCH_PENDING["last_good"].items():
                        if k in accept_inputs:
                            accept_inputs[k] = v
                else:
                    for k,v in DOOR_GLITCH_PENDING["last_good"].items():
                        if k in accept_inputs:
                            accept_inputs[k] = v
            else:
                if DOOR_GLITCH_PENDING["active"] and now >= DOOR_GLITCH_PENDING["until"]:
                    DOOR_GLITCH_PENDING = {"active": False, "until": 0.0, "target_state": None, "last_good": {}}

            # Compute logic (manual or automatic)
            with RT_LOCK:
                last_tc = RUNTIME.get('sensors', {}).get('temp_cab')

            if cfg.get('manual', {}).get('włączony', False):
                logical = dict(cfg['manual']['stany']); alarm_reason = 'MANUAL MODE'
            else:
                logical, alarm_reason = compute_logic(cfg, accept_inputs, last_tc)

            # Strike forces
            force_labels = get_active_force_labels(now)

            # Write outputs
            write_outputs_from_logical(cfg, logical, force_on_labels=force_labels)
            drive_buzzer(bool(logical.get('alarm')))

            # Log input/output changes
            with RT_LOCK:
                prev_inputs_rt = dict(RUNTIME['inputs'])
                prev_outputs_rt = dict(RUNTIME['outputs'])

            for k, v in accept_inputs.items():
                pv = prev_inputs_rt.get(k)
                if pv is not None and pv != v:
                    if k.startswith('door_'):
                        append_log("INPUT", f"{k.upper()} -> {v}", {"category":"door"})
                    elif k.startswith('flood_'):
                        append_log("INPUT", f"{k.upper()} -> {v}", {"category":"flood"})

            for k, v in logical.items():
                pv = prev_outputs_rt.get(k)
                if pv is not None and pv != v:
                    append_log("OUTPUT", f"{LABELS_EN.get(k,k).upper()} -> {'ON' if v else 'OFF'}", {"logical":k})

            # update runtime
            with RT_LOCK:
                RUNTIME['inputs'] = accept_inputs
                RUNTIME['outputs'] = logical
                if alarm_reason is not None:
                    RUNTIME['alarm_reason'] = alarm_reason
                RUNTIME['ts'] = now

            last_fast_inputs = dict(accept_inputs)

            # -------- full cycle --------
            if now >= next_logic_ts:
                tb, hb, tc, hc = dht_read_buffered()
                inputs_snapshot = read_inputs_mapped(cfg)
                last_flood_ts = now

                if cfg.get('manual', {}).get('włączony', False):
                    logical = dict(cfg['manual']['stany']); alarm_reason = 'MANUAL MODE'
                else:
                    logical, alarm_reason = compute_logic(cfg, inputs_snapshot, tc)

                force_labels = get_active_force_labels(now)
                write_outputs_from_logical(cfg, logical, force_on_labels=force_labels)
                drive_buzzer(bool(logical.get('alarm')))

                with RT_LOCK:
                    old_sens = dict(RUNTIME['sensors'])
                    new_sens = {
                        'temp_batt': round(tb,1) if isinstance(tb,(int,float)) else None,
                        'hum_batt':  round(hb,1) if isinstance(hb,(int,float)) else None,
                        'temp_cab':  round(tc,1) if isinstance(tc,(int,float)) else None,
                        'hum_cab':   round(hc,1) if isinstance(hc,(int,float)) else None,
                    }
                    for k,v in new_sens.items():
                        if v != old_sens.get(k):
                            append_log("SENSOR", f"{k} -> {v}", {"unit":"C/%"})

                    RUNTIME['inputs'] = inputs_snapshot
                    RUNTIME['sensors'] = new_sens
                    RUNTIME['outputs'] = logical
                    RUNTIME['alarm_reason'] = alarm_reason
                    RUNTIME['ts'] = now
                    RUNTIME['error'] = None

                next_logic_ts = now + LOGIC_INTERVAL_SEC

        except Exception as e:
            with RT_LOCK:
                RUNTIME['error'] = str(e)
        time.sleep(FAST_EVENTS_TICK_SEC)

# ===================
# Auth / roles
# ===================
def require_login(fn):
    @wraps(fn)
    def w(*a, **kw):
        if 'user' not in session:
            return redirect(url_for('login'))
        return fn(*a, **kw)
    return w

def require_role(*roles):
    def deco(fn):
        @wraps(fn)
        def w(*a, **kw):
            if 'user' not in session:
                return redirect(url_for('login'))
            if session.get('user') not in roles:
                flash('Insufficient permissions for this operation.', 'error')
                return redirect(url_for('dashboard'))
            return fn(*a, **kw)
        return w
    return deco

# Inject buzzer state into all templates
@app.context_processor
def inject_state():
    with RT_LOCK:
        return {"buzzer_muted": bool(RUNTIME.get('buzzer_muted', False))}

# ===================
# Templates
# ===================

TEMPLATE_BASE = u"""
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>TCM Panel</title>
  <style>
    :root{
      --bg:#0b1020; --panel:#0c1330; --glass:rgba(255,255,255,0.06);
      --muted:#9fb1e3; --accent:#7aa2ff; --good:#22c55e; --bad:#ef4444; --warn:#f59e0b;
      --radius:18px;
    }
    *{box-sizing:border-box}
    body{
      font-family: Inter, system-ui, Segoe UI, Roboto, Arial, sans-serif; margin:0; color:#eaf0ff;
      background:
        radial-gradient(1200px 800px at -10% -10%, #1d2a6b44, transparent 60%),
        radial-gradient(1200px 800px at 110% -10%, #0ea5e955, transparent 60%),
        linear-gradient(180deg,#0a0f23 0%, #0b1020 100%);
    }
    header,footer{padding:16px 22px; background:var(--panel); border-bottom:1px solid #ffffff0f}
    footer{border-top:1px solid #ffffff0f; border-bottom:0}
    main{padding:22px; max-width:1280px; margin:0 auto}
    .row{display:flex; flex-wrap:wrap; gap:22px}
    .col{flex:1 1 360px}
    .card{
      background:var(--glass); border:1px solid #ffffff12; border-radius:var(--radius);
      padding:18px; box-shadow:0 10px 40px rgba(0,0,0,.35); backdrop-filter: blur(10px);
    }
    h2,h3{margin:.2rem 0 1rem 0; display:flex; align-items:center; gap:10px}
    table{width:100%; border-collapse:collapse}
    th,td{padding:12px 10px; border-bottom:1px dashed rgba(255,255,255,0.08); font-size:14px}
    .badge{display:inline-flex; align-items:center; gap:8px; padding:6px 10px; border-radius:999px; font-weight:700; font-size:11px; border:1px solid #ffffff22}
    .badge.input{color:#e5f6ff; background:#103247}
    .badge.output{color:#eaffef; background:#133a22}
    .badge.sensor{color:#fff4db; background:#3a2b0d}
    .badge.auth{color:#f0eaff; background:#2e1b47}
    .badge.cfg{color:#ffe; background:#3c3c14}
    .badge.strike{color:#ffeaf0; background:#461b2b}
    .pill{display:inline-flex; align-items:center; justify-content:center; min-width:140px; padding:10px 12px; border-radius:12px; font-weight:800; letter-spacing:.4px; text-transform:uppercase; border:1px solid #ffffff22}
    .on{background:rgba(34,197,94,.12); color:#b7f7c6}
    .off{background:rgba(239,68,68,.12); color:#fecaca}
    .ok{color:#86efac} .bad{color:#fecaca} .warn{color:#fde68a}
    .btn{display:inline-flex; align-items:center; gap:8px; background:linear-gradient(90deg,#1e2a5a,#2b3a8a); color:#fff; padding:10px 14px; border-radius:12px; text-decoration:none; border:0; cursor:pointer; transition:.2s}
    .btn:hover{filter:brightness(1.1)}
    input,select,textarea{background:#0f1637; color:#fff; border:1px solid #ffffff1f; border-radius:12px; padding:10px 12px; min-width:120px; outline:none}
    input:focus,select:focus,textarea:focus{border-color:#7aa2ff66; box-shadow:0 0 0 3px #7aa2ff22}
    .grid{display:grid; grid-template-columns: repeat(auto-fit,minmax(200px,1fr)); gap:12px}
    .flash{padding:12px 14px; border-radius:12px; margin-bottom:12px}
    .flash.error{background:#3b1e1e} .flash.ok{background:#1e3b2a}
    .brand{font-weight:700;letter-spacing:.4px; display:flex; align-items:center; gap:10px}
    .chip{display:inline-flex; align-items:center; gap:6px; font-size:12px; background:#ffffff12; padding:6px 10px; border-radius:999px; border:1px solid #ffffff22}
    .icon{width:18px;height:18px;display:inline-block;vertical-align:middle}
    .section{margin:22px 0}
    .kpis{display:grid; grid-template-columns: repeat(auto-fit,minmax(240px,1fr)); gap:16px}
    .kpi{background:#141b27; border:1px solid #1e293b; border-radius:12px; padding:14px}
    .kpi .label{color:#93a4c3; font-size:12px; letter-spacing:.4px}
    .kpi .value{font-size:20px; font-weight:700; margin-top:6px}
    .toolbar{display:flex; gap:10px; flex-wrap:wrap; align-items:center}
    .mono{font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace}
  </style>
</head>
<body>
  <header>
    <div style="display:flex;justify-content:space-between;align-items:center">
      <div class="brand">
        <svg class="icon" viewBox="0 0 24 24" fill="none"><path d="M4 7a3 3 0 0 1 3-3h10a3 3 0 0 1 3 3v10a3 3 0 0 1-3 3H7a3 3 0 0 1-3-3V7Z" stroke="#7aa2ff" stroke-width="1.5"/><path d="M7 9h10M7 13h6" stroke="#7aa2ff" stroke-width="1.5"/></svg>
        TCM Panel <span class="chip">ID: {{ cfg['id'] }}</span>
      </div>
      <div class="toolbar">
        <a class="btn" href="{{ url_for('logs_page') }}">Logs</a>
        <form method="post" action="{{ url_for('buzzer_toggle') }}">
          <button class="btn" type="submit">{{ 'Unmute buzzer' if buzzer_muted else 'Mute buzzer' }}</button>
        </form>
        {% if session.get('user') %}
          Signed in: <b>{{ session['user'] }}</b>
          <a href="{{ url_for('logout') }}" class="btn">Logout</a>
        {% endif %}
      </div>
    </div>
  </header>
  <main>
    {% with messages = get_flashed_messages(with_categories=true) %}
      {% if messages %}
        {% for cat, msg in messages %}
          <div class="flash {{ 'ok' if cat=='ok' else 'error' }}">{{ msg }}</div>
        {% endfor %}
      {% endif %}
    {% endwith %}
    {% block content %}{% endblock %}
  </main>
  <footer>
    <span class="chip">IP: {{ cfg['ip'] }}</span>
    <span class="chip">Mask: {{ cfg['mask'] }}</span>
    <span class="chip">Gateway: {{ cfg['gateway'] }}</span>
  </footer>
  {% block scripts %}{% endblock %}
</body>
</html>
"""

TEMPLATE_LOGIN = u"""
{% extends 'base.html' %}
{% block content %}
<div class="card" style="max-width:460px; margin:40px auto">
  <h2>Sign in</h2>
  <form method="post">
    <div class="grid">
      <label>Username<br><input name="username" required></label>
      <label>Password<br><input type="password" name="password" required></label>
    </div>
    <div style="margin-top:12px"><button class="btn">Sign in</button></div>
  </form>
</div>
{% endblock %}
"""

TEMPLATE_DASHBOARD = u"""
{% extends 'base.html' %}
{% block content %}

<div class="section">
  <h2>Sensor data</h2>
  <div class="kpis">
    <div class="kpi"><div class="label">BATT TEMP:</div><div class="value"><span data-sensor="temp_batt">{{ sensors['temp_batt'] if sensors['temp_batt'] is not none else '—' }}</span> °C</div></div>
    <div class="kpi"><div class="label">BATT HUM:</div><div class="value"><span data-sensor="hum_batt">{{ sensors['hum_batt'] if sensors['hum_batt'] is not none else '—' }}</span> %</div></div>
    <div class="kpi"><div class="label">CAB TEMP:</div><div class="value"><span data-sensor="temp_cab">{{ sensors['temp_cab'] if sensors['temp_cab'] is not none else '—' }}</span> °C</div></div>
    <div class="kpi"><div class="label">CAB HUM:</div><div class="value"><span data-sensor="hum_cab">{{ sensors['hum_cab'] if sensors['hum_cab'] is not none else '—' }}</span> %</div></div>
  </div>
</div>

<div class="row">
  <div class="col">
    <div class="section">
      <h2>Inputs</h2>
      <div class="card"><table>
        {% for name in door_names %}
          <tr><th>{{ name|upper }}:</th>
              <td><span class="pill {{ 'bad' if inputs[name]=='OPEN' else 'ok' }}" data-input="{{ name }}">{{ 'OPEN' if inputs[name]=='OPEN' else 'CLOSED' }}</span></td></tr>
        {% endfor %}
        {% for name in flood_names %}
          <tr><th>{{ name|upper }}:</th>
              <td><span class="pill {{ 'bad' if inputs[name]=='FLOOD' else 'ok' }}" data-input="{{ name }}">{{ inputs[name] }}</span></td></tr>
        {% endfor %}
        {% if (door_names|length)==0 and (flood_names|length)==0 %}
          <tr><td colspan="2"><i>No inputs mapped. Configure in Service panel.</i></td></tr>
        {% endif %}
      </table></div>
    </div>
  </div>

  <div class="col">
    <div class="section">
      <h2>Outputs</h2>
      <div class="card"><table>
        {% for name in logical_names %}
          <tr><th>{{ labels[name] if labels.get(name) else name|upper }}:</th>
              <td><span class="pill {{ 'on' if outputs[name] else 'off' }}" data-output="{{ name }}">{{ 'ON' if outputs[name] else 'OFF' }}</span></td></tr>
        {% endfor %}
      </table></div>

      {% if strikes %}
      <div class="section">
        <h3>Electronic strike</h3>
        <div class="card">
          <div class="grid">
            {% for s in strikes %}
              <form method="post" action="{{ url_for('trigger_strike', num=s.num) }}">
                <button class="btn" type="submit">Release {{ s.name }} ({{ s.tr }})</button>
              </form>
            {% endfor %}
          </div>
        </div>
      </div>
      {% endif %}

      {% if alarm_reason %}<div class="flash error" style="margin-top:10px">Alarm: {{ alarm_reason }}</div>{% endif %}
      {% if session.get('user') in ['technik','serwis'] %}
        <div style="margin-top:12px"><a class="btn" href="{{ url_for('settings') }}">Settings (technician)</a></div>
      {% endif %}
      {% if session.get('user') == 'serwis' %}
        <div style="margin-top:8px;display:flex;gap:10px;flex-wrap:wrap">
          <a class="btn" href="{{ url_for('service_panel') }}">Service panel</a>
        </div>
      {% endif %}
    </div>
  </div>
</div>

{% endblock %}
{% block scripts %}
<script>
  async function refreshState(){
    try{
      const r = await fetch("{{ url_for('api_state') }}", {cache: 'no-store'});
      const s = await r.json();
      if(s.inputs){
        for(const k in s.inputs){
          const v = s.inputs[k];
          const el = document.querySelector(`[data-input="${k}"]`);
          if(el){
            if(k.startsWith('door_')){ el.textContent = (v==='OPEN' ? 'OPEN' : 'CLOSED'); el.classList.toggle('bad', v==='OPEN'); el.classList.toggle('ok', v!=='OPEN'); }
            else { el.textContent = v; el.classList.toggle('bad', v==='FLOOD'); el.classList.toggle('ok', v!=='FLOOD'); }
          }
        }
      }
      if(s.outputs){
        for(const k in s.outputs){
          const on = !!s.outputs[k];
          const el = document.querySelector(`[data-output="${k}"]`);
          if(el){ el.textContent = on ? 'ON' : 'OFF'; el.classList.toggle('on', on); el.classList.toggle('off', !on); }
        }
      }
      if(s.sensors){
        for(const k in s.sensors){
          const v = s.sensors[k];
          const el = document.querySelector(`[data-sensor="${k}"]`);
          if(el){ el.textContent = (v==null? '—' : v); }
        }
      }
    }catch(e){}
  }
  setInterval(refreshState, 1000);
</script>
{% endblock %}
"""

TEMPLATE_SETTINGS = u"""
{% extends 'base.html' %}
{% block content %}
<div class="section">
  <h2>Settings</h2>
  <form method="post">
    <div class="row">
      <div class="col">
        <div class="card">
          <h3 style="margin-top:0">Network</h3>
          <div class="grid">
            <label>Device ID<br><input name="id" value="{{ cfg['id'] }}" required></label>
            <label>IP address<br><input name="ip" value="{{ cfg['ip'] }}" required></label>
            <label>Netmask<br><input name="mask" value="{{ cfg['mask'] }}" required></label>
            <label>Gateway<br><input name="gateway" value="{{ cfg['gateway'] }}" required></label>
          </div>
        </div>
      </div>
      <div class="col">
        <div class="card">
          <h3 style="margin-top:0">Temperature thresholds</h3>
          <div class="grid">
            <label>Heater (°C)<br><input type="number" step="0.1" name="t_grz" value="{{ cfg['temp_thresholds']['grzałka'] }}" required></label>
            <label>Cooler (°C)<br><input type="number" step="0.1" name="t_kli" value="{{ cfg['temp_thresholds']['klimatyzacja'] }}" required></label>
            <label>Ventilation (°C)<br><input type="number" step="0.1" name="t_wen" value="{{ cfg['temp_thresholds']['went'] }}" required></label>
            <label>Hysteresis (°C)<br><input type="number" step="0.1" name="h" value="{{ cfg['histereza'] }}" required></label>
          </div>
        </div>
      </div>
    </div>
    <div style="margin-top:12px">
      <button class="btn" type="submit">Save</button>
      <a class="btn" href="{{ url_for('dashboard') }}">Back</a>
    </div>
  </form>
</div>
{% endblock %}
"""
TEMPLATE_SERVICE = u"""
{% extends 'base.html' %}
{% block content %}
<div class="row">
  <div class="col">
    <div class="section">
      <h2>Service status</h2>
      <div class="card">
        <div style="display:flex; gap:10px; flex-wrap:wrap">
          <a class="btn" href="{{ url_for('diag') }}">Diagnostics (MCP registers)</a>
          <a class="btn" href="{{ url_for('dashboard') }}">Back to dashboard</a>
        </div>
      </div>
    </div>

    <div class="section">
      <h2>Inputs polarity</h2>
      <div class="card">
        <form method="post" action="{{ url_for('service_inputs') }}">
          <div class="grid">
            <label>Flood sensors
              <select name="flood_low_is_flood">
                <option value="1" {{ 'selected' if cfg['inputs']['flood_low_is_flood'] else '' }}>LOW = FLOOD (NO to GND)</option>
                <option value="0" {{ '' if cfg['inputs']['flood_low_is_flood'] else 'selected' }}>HIGH = FLOOD (NC)</option>
              </select>
            </label>
            <label>Door sensors (bit=1)
              <select name="door_open_is_high">
                <option value="1" {{ 'selected' if cfg['inputs']['door_open_is_high'] else '' }}>1 = OPEN</option>
                <option value="0" {{ '' if cfg['inputs']['door_open_is_high'] else 'selected' }}>0 = OPEN</option>
              </select>
            </label>
            <label>DIP polarity (bit=1)
              <select name="dip_on_is_high">
                <option value="1" {{ 'selected' if cfg['inputs']['dip_on_is_high'] else '' }}>1 = ON</option>
                <option value="0" {{ '' if cfg['inputs']['dip_on_is_high'] else 'selected' }}>0 = ON</option>
              </select>
            </label>
          </div>
          <button class="btn" style="margin-top:10px">Save inputs polarity</button>
        </form>
      </div>
    </div>

    <div class="section">
      <h2>Input map (A0..A7) — max 6 doors + 2 flood</h2>
      <div class="card">
        <form method="post" action="{{ url_for('service_input_map') }}">
          <div class="grid">
            {% for i in range(1,7) %}
              <label>Door {{ i }}
                <select name="door_{{ i }}">
                  <option value="">—</option>
                  {% for a in aopts %}
                    <option value="{{ a }}" {{ 'selected' if a == door_sel.get(i) else '' }}>{{ a }}</option>
                  {% endfor %}
                </select>
              </label>
            {% endfor %}
            {% for i in range(1,3) %}
              <label>Flood {{ i }}
                <select name="flood_{{ i }}">
                  <option value="">—</option>
                  {% for a in aopts %}
                    <option value="{{ a }}" {{ 'selected' if a == flood_sel.get(i) else '' }}>{{ a }}</option>
                  {% endfor %}
                </select>
              </label>
            {% endfor %}
          </div>
          <div style="margin-top:10px"><button class="btn">Save input map</button></div>
        </form>
      </div>
    </div>

    <div class="section">
      <h2>Outputs polarity</h2>
      <div class="card">
        <form method="post" action="{{ url_for('service_outputs_polarity') }}">
          <label>Active LOW:
            <select name="active_low_K">
              <option value="0" {{ '' if cfg['outputs']['active_low']['K'] else 'selected' }}>K: HIGH=ON</option>
              <option value="1" {{ 'selected' if cfg['outputs']['active_low']['K'] else '' }}>K: LOW=ON</option>
            </select>
            <select name="active_low_T" style="margin-left:8px">
              <option value="0" {{ '' if cfg['outputs']['active_low']['T'] else 'selected' }}>T: HIGH=ON</option>
              <option value="1" {{ 'selected' if cfg['outputs']['active_low']['T'] else '' }}>T: LOW=ON</option>
            </select>
          </label>
          <button class="btn" style="margin-left:8px">Save outputs</button>
        </form>
      </div>
    </div>
  </div>

  <div class="col">
    <div class="section">
      <h2>Logical output mapping</h2>
      <div class="card">
        <form method="post" action="{{ url_for('service_map') }}">
          <div class="grid">
            {% for lname in logical_names %}
              <label>{{ labels.get(lname, lname) }}<br>
                <select name="map_{{ lname }}">
                  {% for opt in channels %}
                    <option value="{{ opt }}" {{ 'selected' if opt in cfg['mapowania'].get(lname, []) else '' }}>{{ opt }}</option>
                  {% endfor %}
                </select>
              </label>
            {% endfor %}
          </div>
          <div style="margin-top:10px"><button class="btn">Save mapping</button></div>
        </form>
      </div>
    </div>

    <div class="section">
      <h2>Electronic strike mapping</h2>
      <div class="card">
        <form method="post" action="{{ url_for('service_strikes') }}">
          <div class="grid">
            {% for s in range(1,7) %}
              <label>Strike {{ s }}
                <select name="strike_{{ s }}">
                  <option value="-">-</option>
                  {% for t in strike_opts %}
                    <option value="{{ t }}" {{ 'selected' if t == strike_sel.get(s) else '' }}>{{ t }}</option>
                  {% endfor %}
                </select>
              </label>
            {% endfor %}
          </div>
          <div style="margin-top:10px"><button class="btn">Save strikes</button></div>
        </form>
      </div>
    </div>

    <div class="section">
      <h2>Manual mode</h2>
      <div class="card">
        <form method="post" action="{{ url_for('service_manual') }}">
          <label><input type="checkbox" name="manual_on" value="1" {{ 'checked' if cfg['manual']['włączony'] else '' }}> Enable manual mode</label>
          <div class="grid" style="margin-top:10px">
            {% for lname in logical_names %}
              <label>{{ labels.get(lname, lname) }}<br>
                <select name="man_{{ lname }}">
                  <option value="0" {{ '' if cfg['manual']['stany'][lname] else 'selected' }}>OFF</option>
                  <option value="1" {{ 'selected' if cfg['manual']['stany'][lname] else '' }}>ON</option>
                </select>
              </label>
            {% endfor %}
          </div>
          <div style="margin-top:10px"><button class="btn">Save manual</button></div>
        </form>
      </div>
    </div>

    <div class="section">
      <h2>Live states</h2>
      <div class="card"><table>
        {% for name in logical_names %}
          <tr><th>{{ labels.get(name, name) }}</th><td><span class="pill {{ 'on' if outputs[name] else 'off' }}" data-output="{{ name }}">{{ 'ON' if outputs[name] else 'OFF' }}</span></td></tr>
        {% endfor %}
      </table></div>
    </div>
  </div>
</div>
{% endblock %}
"""

TEMPLATE_DIAG = u"""
{% extends 'base.html' %}
{% block content %}

<style>
  .mono{font-family: ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; letter-spacing:.2px}
  .subtle{color:#c7d2fe99; font-size:12px}
  .bitgrid{display:flex; gap:6px; flex-wrap:wrap; align-items:center}
  .bit{width:32px;height:32px;line-height:32px;text-align:center;border-radius:8px;border:1px solid #ffffff22;background:#ffffff12;font-weight:800}
  .bit.on{border-color:#22c55e; box-shadow:0 0 0 2px #22c55e33 inset; color:#b7f7c6}
  .kv{display:grid; grid-template-columns: 180px 1fr; gap:6px; align-items:center}
  .inline-controls{display:flex; gap:8px; flex-wrap:wrap; align-items:center}
  .small{font-size:12px; opacity:.85}
</style>

<div class="row">
  <div class="col">
    <div class="section">
      <h2>Expander 1 (CE0) – outputs</h2>
      <div class="card">
        <table>
          {% for k,v in exp1.items() %}
            <tr><th>{{ k }}</th><td class="mono">{{ v }}</td></tr>
          {% endfor %}
        </table>
      </div>
    </div>
  </div>

  <div class="col">
    <div class="section">
      <h2>Expander 2 (CE1) – inputs</h2>
      <div class="card">
        <table>
          {% for k,v in exp2.items() %}
            <tr><th>{{ k }}</th><td class="mono">{{ v }}</td></tr>
          {% endfor %}
        </table>
      </div>
    </div>
  </div>
</div>

<div class="section">
  <h2>MCP23S17 quick reference — how to read these registers</h2>
  <div class="card">
    <table>
      <thead>
        <tr>
          <th style="width:140px">Register</th>
          <th>What it stores</th>
          <th style="width:260px">Typical use / notes</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td class="mono">IODIRA / IODIRB</td>
          <td>Direction of pins on port A / B. <b>1 = INPUT</b>, <b>0 = OUTPUT</b> (bit per pin).</td>
          <td>For CE0 (outputs) expect <span class="mono">0x00</span>. For CE1 (inputs) expect <span class="mono">0xFF</span>.</td>
        </tr>
        <tr>
          <td class="mono">GPIOA / GPIOB</td>
          <td>Current logic level on pins (read live state).</td>
          <td>For inputs (CE1): doors/flood; for outputs (CE0): mirrors pin level if configured as outputs.</td>
        </tr>
        <tr>
          <td class="mono">OLATA / OLATB</td>
          <td>Output latch (the value we wrote to drive outputs).</td>
          <td>For CE0: state that drives relays/transistors (after polarity rules).</td>
        </tr>
        <tr>
          <td class="mono">GPPUA / GPPUB</td>
          <td>Internal pull-up enable. <b>1 = pull-up ON</b>, <b>0 = OFF</b> (bit per pin).</td>
          <td>Inputs usually use pull-ups; outputs don’t.</td>
        </tr>
        <tr>
          <td class="mono">IOCON</td>
          <td>Global config. Bits: BANK, MIRROR, SEQOP, DISSLW, HAEN, ODR, INTPOL.</td>
          <td>We use default <span class="mono">0x00</span>.</td>
        </tr>
      </tbody>
    </table>

    <div style="margin-top:14px">
      <h3 style="margin:0 0 8px 0">Bit numbering & pin mapping</h3>
      <ul>
        <li><b>Bits go 7…0</b> (MSB→LSB). On port A: <b>GPA7…GPA0</b>; on port B: <b>GPB7…GPB0</b>.</li>
        <li><b>Expander 1 (CE0)</b> — hardware outputs:
          <ul>
            <li>Relays <b>K1…K8</b> ⇄ <b>GPA0…GPA7</b> (mask in <span class="mono">OLATA</span>).</li>
            <li>Transistors <b>T1…T8</b> ⇄ <b>GPB0…GPB7</b> (mask in <span class="mono">OLATB</span>).</li>
          </ul>
        </li>
        <li><b>Expander 2 (CE1)</b> — hardware inputs:
          <ul>
            <li>Doors / flood mapped onto <b>GPIOA</b> (A0…A7) per “Input map”.</li>
            <li>DIPs are on <b>GPIOB</b> and not logged.</li>
          </ul>
        </li>
      </ul>
    </div>

    <div style="margin-top:14px">
      <h3 style="margin:0 0 8px 0">Active LOW / HIGH reminder</h3>
      <p>
        In “Outputs polarity” you can set a bank to active-LOW. Then <b>ON in UI</b> may be a <b>0</b> in <span class="mono">OLAT</span>.
      </p>
    </div>
  </div>
</div>

<!-- LIVE DECODER -->
<div class="section">
  <h2>Live decoder</h2>
  <div class="card">
    <div class="inline-controls" style="margin-bottom:10px">
      <label>Register type
        <select id="regType">
          <option value="IODIR">IODIR (1=INPUT,0=OUTPUT)</option>
          <option value="GPIO">GPIO (live level)</option>
          <option value="OLAT">OLAT (output latch)</option>
          <option value="GPPU">GPPU (1=pull-up ON)</option>
        </select>
      </label>
      <button class="btn" id="prefillCE0" type="button" title="Load values from CE0 readouts">Prefill from CE0 (outputs)</button>
      <button class="btn" id="prefillCE1" type="button" title="Load values from CE1 readouts">Prefill from CE1 (inputs)</button>
      <span class="small">Accepts hex <span class="mono">0xF3</span> / <span class="mono">F3</span> or decimal.</span>
    </div>

    <div class="row">
      <div class="col">
        <div class="kv">
          <div class="mono">PORT A value</div>
          <div class="inline-controls">
            <input id="valA" placeholder="e.g. 0xF3" />
            <span class="subtle mono" id="valAhex">0x00</span>
          </div>
          <div class="mono">Bits A7…A0</div>
          <div class="bitgrid" id="gridA"></div>
        </div>
        <div class="subtle" style="margin-top:8px">
          CE0 mapping: <b>GPA0…GPA7 = K1…K8</b><br/>
          CE1 mapping: inputs per your “Input map”.
        </div>
      </div>

      <div class="col">
        <div class="kv">
          <div class="mono">PORT B value</div>
          <div class="inline-controls">
            <input id="valB" placeholder="e.g. 0x3C" />
            <span class="subtle mono" id="valBhex">0x00</span>
          </div>
          <div class="mono">Bits B7…B0</div>
          <div class="bitgrid" id="gridB"></div>
        </div>
        <div class="subtle" style="margin-top:8px">
          CE0 mapping: <b>GPB0…GPB7 = T1…T8</b><br/>
          CE1 mapping: DIP (not logged) unless remapped for inputs.
        </div>
      </div>
    </div>

    <div style="margin-top:12px" id="legend" class="small">
      <span class="mono">IODIR</span>: 1 = INPUT, 0 = OUTPUT •
      <span class="mono">GPIO</span>: live logic level •
      <span class="mono">OLAT</span>: what we latched to outputs •
      <span class="mono">GPPU</span>: 1 = pull-up enabled
    </div>
  </div>
</div>

<div style="margin-top:12px">
  <a class="btn" href="{{ url_for('service_panel') }}">Back</a>
</div>

{% endblock %}

{% block scripts %}
{{ super() }}
<script>
(function(){
  const CE0 = {{ exp1|tojson }};
  const CE1 = {{ exp2|tojson }};

  const regSel = document.getElementById('regType');
  const valA = document.getElementById('valA');
  const valB = document.getElementById('valB');
  const valAhex = document.getElementById('valAhex');
  const valBhex = document.getElementById('valBhex');
  const gridA = document.getElementById('gridA');
  const gridB = document.getElementById('gridB');

  const parseByte = (s) => {
    if(!s) return 0;
    s = String(s).trim();
    let v = 0;
    if(/^0x/i.test(s)) v = parseInt(s, 16);
    else if(/[a-f]/i.test(s)) v = parseInt(s, 16);
    else v = parseInt(s, 10);
    if(Number.isNaN(v)) v = 0;
    return Math.max(0, Math.min(255, v|0));
  };

  const byteHex = (n) => '0x' + (n & 0xFF).toString(16).toUpperCase().padStart(2,'0');

  const renderBits = (n, container, port) => {
    container.innerHTML = '';
    for(let b = 7; b >= 0; b--){
      const bit = (n >> b) & 1;
      const el = document.createElement('div');
      el.className = 'bit' + (bit ? ' on' : '');
      el.textContent = String(b);
      el.title = (port==='A' ? 'GPA' : 'GPB') + b + ' = ' + bit;
      container.appendChild(el);
    }
  };

  const getRegNames = (type) => {
    // returns ['<A reg name>', '<B reg name>']
    switch(type){
      case 'IODIR': return ['IODIRA', 'IODIRB'];
      case 'GPIO':  return ['GPIOA',  'GPIOB'];
      case 'OLAT':  return ['OLATA',  'OLATB'];
      case 'GPPU':  return ['GPPUA',  'GPPUB'];
      default: return ['GPIOA','GPIOB'];
    }
  };

  const prefill = (src) => {
    const [ra, rb] = getRegNames(regSel.value);
    const S = (src==='CE0') ? CE0 : CE1;
    const a = parseByte(S[ra]);
    const b = parseByte(S[rb]);
    valA.value = byteHex(a);
    valB.value = byteHex(b);
    update();
  };

  const update = () => {
    const a = parseByte(valA.value);
    const b = parseByte(valB.value);
    valAhex.textContent = byteHex(a);
    valBhex.textContent = byteHex(b);
    renderBits(a, gridA, 'A');
    renderBits(b, gridB, 'B');
  };

  document.getElementById('prefillCE0').addEventListener('click', () => prefill('CE0'));
  document.getElementById('prefillCE1').addEventListener('click', () => prefill('CE1'));
  regSel.addEventListener('change', () => {
    // changing reg type doesn’t alter values, but affects "Prefill" mapping
  });
  valA.addEventListener('input', update);
  valB.addEventListener('input', update);

  // Default: prefill GPIO from CE1 (inputs)
  regSel.value = 'GPIO';
  prefill('CE1');
})();
</script>
{% endblock %}
"""


TEMPLATE_LOGS = u"""
{% extends 'base.html' %}
{% block content %}
<div class="section">
  <h2>Event logs</h2>
  <div class="card" style="overflow:auto; max-height:65vh">
    <table>
      <thead><tr><th style="width:190px">Time</th><th style="width:120px">Type</th><th>Message</th></tr></thead>
      <tbody class="mono">
        {% for r in rows %}
          {% set cls = r.type.lower() %}
          <tr>
            <td>{{ r.ts }}</td>
            <td>
              <span class="badge {{ cls }}">
                {{ r.type.upper() }}
              </span>
            </td>
            <td>{{ r.message }}</td>
          </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
  <div style="margin-top:12px; display:flex; gap:10px; flex-wrap:wrap">
    <a class="btn" href="{{ url_for('logs_export') }}">Export</a>
    <a class="btn" href="{{ url_for('dashboard') }}">Back</a>
  </div>
</div>
{% endblock %}
"""

# ===================
# Diagnostics helpers
# ===================
def mcp_dump(spi):
    def r(addr):
        try:
            return f"0x{read_reg(spi, addr):02X}"
        except Exception:
            return "ERR"
    return {'IODIRA': r(IODIRA), 'IODIRB': r(IODIRB), 'GPIOA': r(GPIOA), 'GPIOB': r(GPIOB),
            'OLATA': r(OLATA), 'OLATB': r(OLATB), 'GPPUA': r(GPPUA), 'GPPUB': r(GPPUB), 'IOCON': r(IOCON)}

# ===================
# Jinja loader
# ===================
from jinja2 import DictLoader, ChoiceLoader
app.jinja_loader = ChoiceLoader([
    DictLoader({
        'base.html': TEMPLATE_BASE,
        'login.html': TEMPLATE_LOGIN,
        'dashboard.html': TEMPLATE_DASHBOARD,
        'settings.html': TEMPLATE_SETTINGS,
        'service.html': TEMPLATE_SERVICE,
        'diag.html': TEMPLATE_DIAG,
        'logs.html': TEMPLATE_LOGS,
    }),
    app.jinja_loader,
])

# ===================
# Routes
# ===================

@app.route('/')
def root():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET','POST'])
def login():
    cfg = load_config()
    if request.method == 'POST':
        u = request.form.get('username','').strip()
        p = request.form.get('password','')
        if u == 'serwis':
            if not service_allowed_at_boot(cfg):
                flash('Access denied.', 'error')  # no DIP details
                append_log("AUTH", "Service login denied", {"user": u})
                return render_template('login.html', cfg=cfg)
        if cfg['users'].get(u) == p:
            session['user'] = u
            append_log("AUTH", "Login success", {"user": u})
            return redirect(url_for('dashboard'))
        append_log("AUTH", "Login failed", {"user": u})
        flash('Invalid username or password.', 'error')
    return render_template('login.html', cfg=cfg)

@app.route('/logout')
def logout():
    u = session.get('user')
    session.clear()
    if u:
        append_log("AUTH", "Logout", {"user": u})
    return redirect(url_for('login'))

@app.route('/buzzer/toggle', methods=['POST'])
@require_login
def buzzer_toggle():
    with RT_LOCK:
        current = bool(RUNTIME.get('buzzer_muted', False))
        RUNTIME['buzzer_muted'] = not current
        muted = RUNTIME['buzzer_muted']
        alarm_on = bool(RUNTIME.get('outputs',{}).get('alarm'))
    append_log("CFG", f"Buzzer {'muted' if muted else 'unmuted'}", {"by": session.get('user')})
    # enforce hardware state immediately
    drive_buzzer(alarm_on)
    return redirect(request.referrer or url_for('dashboard'))

@app.route('/dashboard')
@require_login
def dashboard():
    cfg = load_config()
    with RT_LOCK:
        inputs = dict(RUNTIME['inputs'])
        sensors = dict(RUNTIME['sensors'])
        logical = dict(RUNTIME['outputs'])
        alarm_reason = RUNTIME.get('alarm_reason')
    amap = cfg.get("input_map", {"doors":[], "flood":[]})
    door_names = [f"door_{i+1}" for i in range(len(amap.get("doors",[])[:6]))]
    flood_names = [f"flood_{i+1}" for i in range(len(amap.get("flood",[])[:2]))]
    strikes = []
    for idx in range(1,7):
        tr = cfg.get("strikes",{}).get(f"strike_{idx}",{}).get("transistor")
        if tr:
            strikes.append({"num": idx, "name": f"Strike {idx}", "tr": tr})
    return render_template('dashboard.html',
        cfg=cfg, inputs=inputs, sensors=sensors,
        logical_names=LOGICAL_OUTPUTS, outputs=logical,
        alarm_reason=alarm_reason, labels=LABELS_EN,
        door_names=door_names, flood_names=flood_names,
        strikes=strikes)

@app.route('/api/state')
@require_login
def api_state():
    with RT_LOCK:
        return jsonify({
            'inputs':  RUNTIME['inputs'],
            'outputs': RUNTIME['outputs'],
            'sensors': RUNTIME['sensors'],
            'alarm_reason': RUNTIME['alarm_reason'],
            'ts': RUNTIME['ts'],
            'error': RUNTIME['error'],
        })

# Simple REST (GET) for separate sections
@app.route('/api/v1/inputs')
def api_inputs_v1():
    with RT_LOCK:
        return jsonify(RUNTIME['inputs'])

@app.route('/api/v1/outputs')
def api_outputs_v1():
    with RT_LOCK:
        return jsonify(RUNTIME['outputs'])

@app.route('/api/v1/sensors')
def api_sensors_v1():
    with RT_LOCK:
        return jsonify(RUNTIME['sensors'])

# Trigger strike (panel button)
@app.route('/strike/<int:num>', methods=['POST'])
@require_login
def trigger_strike(num:int):
    cfg = load_config()
    key = f"strike_{num}"
    tr = cfg.get("strikes",{}).get(key,{}).get("transistor")
    if not tr or tr not in ALLOWED_STRIKE_TRANSISTORS:
        flash('Strike not configured.', 'error'); return redirect(url_for('dashboard'))
    now = time.time()
    with STRIKE_LOCK:
        STRIKE_TIMERS[tr] = now + STRIKE_DURATION_SEC
    append_log("STRIKE", f"Triggered {key} on {tr} for {int(STRIKE_DURATION_SEC)}s", {"strike": key, "transistor": tr})
    return redirect(url_for('dashboard'))

# REST trigger strike individually (GET)
@app.route('/api/v1/strike/<int:num>/trigger')
def api_trigger_strike(num:int):
    cfg = load_config()
    key = f"strike_{num}"
    tr = cfg.get("strikes",{}).get(key,{}).get("transistor")
    if not tr or tr not in ALLOWED_STRIKE_TRANSISTORS:
        return jsonify({"ok": False, "error": "Not configured"}), 400
    now = time.time()
    with STRIKE_LOCK:
        STRIKE_TIMERS[tr] = now + STRIKE_DURATION_SEC
    append_log("STRIKE", f"Triggered {key} via API on {tr} for {int(STRIKE_DURATION_SEC)}s", {"strike": key, "transistor": tr})
    return jsonify({"ok": True, "strike": key, "transistor": tr, "seconds": STRIKE_DURATION_SEC})

@app.route('/settings', methods=['GET','POST'])
@require_role('technik','serwis')
def settings():
    cfg = load_config()
    if request.method == 'POST':
        cfg['id'] = request.form['id'].strip() or cfg['id']
        cfg['ip'] = request.form['ip'].strip()
        cfg['mask'] = request.form['mask'].strip()
        cfg['gateway'] = request.form['gateway'].strip()
        cfg['temp_thresholds']['grzałka'] = float(request.form['t_grz'])
        cfg['temp_thresholds']['klimatyzacja'] = float(request.form['t_kli'])
        cfg['temp_thresholds']['went'] = float(request.form['t_wen'])
        cfg['histereza'] = float(request.form['h'])
        new_op = request.form.get('pw_operator','').strip()
        new_te = request.form.get('pw_technik','').strip()
        if new_op: cfg['users']['operator'] = new_op
        if new_te: cfg['users']['technik'] = new_te
        save_config(cfg)
        append_log("CFG", "Settings updated", {"who": session.get('user')})
        flash('Settings saved.', 'ok')
        return redirect(url_for('settings'))
    return render_template('settings.html', cfg=cfg)

@app.route('/service', methods=['GET'])
@require_role('serwis')
def service_panel():
    cfg = load_config()
    with RT_LOCK:
        logical = dict(RUNTIME['outputs'])
    return render_template('service.html',
        cfg=cfg,
        logical_names=LOGICAL_OUTPUTS,
        outputs=logical,
        channels=[*(f'K{i}' for i in range(1,9)), *(f'T{i}' for i in range(1,9))],
        labels=LABELS_EN,
        aopts=[f"A{i}" for i in range(8)],
        door_sel={i+1: (cfg.get("input_map",{}).get("doors",[])[i] if i < len(cfg.get("input_map",{}).get("doors",[])) else None) for i in range(6)},
        flood_sel={i+1: (cfg.get("input_map",{}).get("flood",[])[i] if i < len(cfg.get("input_map",{}).get("flood",[])) else None) for i in range(2)},
        strike_opts=ALLOWED_STRIKE_TRANSISTORS,
        strike_sel={i+1: cfg.get("strikes",{}).get(f"strike_{i+1}",{}).get("transistor") for i in range(6)},
    )

@app.route('/service/map', methods=['POST'])
@require_role('serwis')
def service_map():
    cfg = load_config()
    for lname in LOGICAL_OUTPUTS:
        val = request.form.get(f'map_{lname}')
        if val:
            cfg['mapowania'][lname] = [val]
    save_config(cfg)
    append_log("CFG", "Logical outputs mapping updated", {"who": session.get('user')})
    flash('Output mapping saved.', 'ok')
    return redirect(url_for('service_panel'))

@app.route('/service/manual', methods=['POST'])
@require_role('serwis')
def service_manual():
    cfg = load_config()
    cfg['manual']['włączony'] = bool(request.form.get('manual_on'))
    for lname in LOGICAL_OUTPUTS:
        cfg['manual']['stany'][lname] = (request.form.get(f'man_{lname}') == '1')
    save_config(cfg)
    append_log("CFG", "Manual mode updated", {"enabled": cfg['manual']['włączony']})
    flash('Manual mode saved.', 'ok')
    return redirect(url_for('service_panel'))

@app.route('/service/outputs_polarity', methods=['POST'])
@require_role('serwis')
def service_outputs_polarity():
    cfg = load_config()
    cfg.setdefault('outputs', {}).setdefault('active_low', {})
    cfg['outputs']['active_low']['K'] = (request.form.get('active_low_K') == '1')
    cfg['outputs']['active_low']['T'] = (request.form.get('active_low_T') == '1')
    save_config(cfg)
    append_log("CFG", "Outputs polarity updated", {"K_low": cfg['outputs']['active_low']['K'], "T_low": cfg['outputs']['active_low']['T']})
    flash('Outputs polarity saved.', 'ok')
    return redirect(url_for('service_panel'))

@app.route('/service/inputs', methods=['POST'])
@require_role('serwis')
def service_inputs():
    cfg = load_config()
    cfg.setdefault('inputs', {})
    cfg['inputs']['flood_low_is_flood'] = (request.form.get('flood_low_is_flood') == '1')
    cfg['inputs']['door_open_is_high'] = (request.form.get('door_open_is_high') == '1')
    cfg['inputs']['dip_on_is_high'] = (request.form.get('dip_on_is_high') == '1')
    save_config(cfg)
    append_log("CFG", "Inputs polarity updated", {})
    flash('Inputs settings saved.', 'ok')
    return redirect(url_for('service_panel'))

@app.route('/service/input_map', methods=['POST'])
@require_role('serwis')
def service_input_map():
    cfg = load_config()
    aopts = [f"A{i}" for i in range(8)]
    doors = []
    floods = []
    for i in range(1,7):
        v = (request.form.get(f"door_{i}") or "").strip().upper()
        if v and v in aopts: doors.append(v)
    for i in range(1,3):
        v = (request.form.get(f"flood_{i}") or "").strip().upper()
        if v and v in aopts: floods.append(v)
    used = set()
    doors2, floods2 = [], []
    for p in doors:
        if p not in used: doors2.append(p); used.add(p)
    for p in floods:
        if p not in used: floods2.append(p); used.add(p)
    if len(doors2) > 6 or len(floods2) > 2 or len(doors2)+len(floods2) > 8:
        flash('Invalid mapping (max 6 doors + 2 flood, unique A-pins, total ≤ 8).', 'error')
        return redirect(url_for('service_panel'))
    cfg["input_map"] = {"doors": doors2, "flood": floods2}
    save_config(cfg)
    append_log("CFG", "Input map updated", {"doors": doors2, "flood": floods2})
    flash('Input map saved.', 'ok')
    return redirect(url_for('service_panel'))

@app.route('/service/strikes', methods=['POST'])
@require_role('serwis')
def service_strikes():
    cfg = load_config()
    for i in range(1,7):
        v_raw = request.form.get(f"strike_{i}")
        v = (v_raw or "").strip().upper()
        # Treat "-", "—", "NONE", "OFF", "" as unassigned
        if v in {"", "-", "—", "NONE", "OFF"}:
            v = None
        elif v and v not in ALLOWED_STRIKE_TRANSISTORS:
            flash(f'Invalid transistor for Strike {i}.', 'error'); return redirect(url_for('service_panel'))
        cfg["strikes"][f"strike_{i}"]["transistor"] = v
    save_config(cfg)
    append_log("CFG", "Strike mapping updated", cfg["strikes"])
    flash('Strikes mapping saved.', 'ok')
    return redirect(url_for('service_panel'))

@app.route('/diag')
@require_role('serwis')
def diag():
    cfg = load_config()
    exp1 = mcp_dump(spi1)
    exp2 = mcp_dump(spi2)
    return render_template('diag.html', cfg=cfg, exp1=exp1, exp2=exp2)

# Logs UI + export
@app.route('/logs')
@require_login
def logs_page():
    with LOG_LOCK:
        rows = list(LOGS)[-300:][::-1]  # newest first
    cfg = load_config()
    return render_template('logs.html', cfg=cfg, rows=rows)

@app.route('/logs/export')
@require_login
def logs_export():
    # stream JSONL
    def gen():
        with LOG_LOCK:
            for rec in LOGS:
                yield json.dumps(rec, ensure_ascii=False) + "\n"
    headers = {'Content-Disposition': 'attachment; filename="events.jsonl"'}
    return Response(gen(), mimetype='application/json', headers=headers)

# ===================
# Start
# ===================
if __name__ == '__main__':
    hw_init()
    t = Thread(target=control_loop, daemon=True)
    t.start()
    app.run(host='0.0.0.0', port=8080, debug=True)
