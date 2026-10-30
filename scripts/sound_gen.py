"""Genera los WAV de retroalimentación con stdlib (wave + struct + math).

Los sonidos se escriben en un *tema*: una carpeta bajo `sounds/themes/` con
un WAV por evento, nombrado igual que el evento (p. ej. `mensaje_nuevo.wav`).
Así un usuario puede crear su propio tema simplemente dejando archivos con esos
mismos nombres en `sounds/themes/<su_tema>/` y seleccionándolo en `sounds.ini`.

Uso:  python scripts/sound_gen.py  [--forzar]  [--destino CARPETA]
"""

import math
import struct
import wave
from pathlib import Path


SR       = 44100
BITS     = 16
CANALES  = 2         # Estéreo real: permite un leve paneo por evento para que
                     # el oído los ubique sin pensar (útil sin lectura visual).
AMP      = 0.55      # Margen sobre 1.0 para evitar clipping al sumar ondas.
# Raíz del repositorio: la carpeta padre de scripts/.
RAIZ = Path(__file__).resolve().parent.parent
# Carpeta base de temas. Cada tema es una subcarpeta con un <evento>.wav.
THEMES_DIR = RAIZ / "sounds" / "themes"

C4, D4, E4, F4, G4, A4, B4 = 261.63, 293.66, 329.63, 349.23, 392.00, 440.00, 493.88
C5, D5, E5, F5, G5, A5, B5 = 523.25, 587.33, 659.25, 698.46, 783.99, 880.00, 987.77
C6, E6 = 1046.50, 1318.51
A3, F3, E3, B3 = 220.00, 174.61, 164.81, 246.94


# ── Primitivas ────────────────────────────────────────────────────────────────

def _seno(freq, dur, amp=AMP, fase=0.0):
    n = int(SR * dur)
    return [amp * math.sin(2 * math.pi * freq * i / SR + fase) for i in range(n)]


def _triangular(freq, dur, amp=AMP):
    # Más cálida que la senoidal y menos agresiva que la cuadrada: apta
    # para tonos de UI que van a sonar muchas veces seguidas.
    n = int(SR * dur)
    p = SR / freq
    out = []
    for i in range(n):
        x = (i % p) / p
        y = 4 * x - 1 if x < 0.5 else 3 - 4 * x
        out.append(amp * y)
    return out


def _glide(f0, f1, dur, amp=AMP, fn=math.sin):
    # Barrido de frecuencia (glissando) integrando la fase: para sonidos de
    # "deslizar/limpiar" sin saltos audibles entre notas.
    n = int(SR * dur)
    out = []
    fase = 0.0
    for i in range(n):
        t = i / max(1, n - 1)
        f = f0 * (f1 / f0) ** t            # interpolación exponencial (musical)
        fase += 2 * math.pi * f / SR
        out.append(amp * fn(fase))
    return out


def _silencio(dur):
    return [0.0] * int(SR * dur)


def _suma(*ondas):
    if not ondas:
        return []
    n = min(len(o) for o in ondas)
    return [sum(o[i] for o in ondas) for i in range(n)]


def _concat(*ondas):
    r = []
    for o in ondas:
        r.extend(o)
    return r


def _detune(freq, dur, amp=AMP, cents=7.0, fn=_triangular):
    # Dos osciladores levemente desafinados (unos pocos cents): añaden cuerpo
    # y un sutil efecto coro, sin que llegue a sonar desafinado de verdad.
    f2 = freq * (2 ** (cents / 1200.0))
    return _suma(fn(freq, dur, amp), fn(f2, dur, amp))


def _perc(muestras, ataque=0.004, tau=0.10):
    # Ataque rápido + caída EXPONENCIAL (e^-t/τ): imita cómo decae un sonido
    # real (campana, pulsación). Más natural y "premium" que el fade lineal
    # para blips y notas sueltas. τ menor = decae antes.
    n = len(muestras)
    if n == 0:
        return muestras
    na = min(max(1, int(SR * ataque)), n)
    out = []
    for i, m in enumerate(muestras):
        a = (i / na) if i < na else 1.0
        out.append(m * a * math.exp(-i / (SR * tau)))
    return out


def _normalizar(muestras, objetivo=0.85):
    if not muestras:
        return muestras
    pico = max(abs(x) for x in muestras)
    if pico < 1e-9:
        return muestras
    k = objetivo / pico
    return [x * k for x in muestras]


def _escribir_wav(path: Path, muestras, pan: float = 0.0):
    """Escribe el WAV. `pan` en [-1, 1] reparte la señal entre L y R con ley de
    'balance': el lado dominante queda a nivel completo y solo se atenúa el
    contrario. Así el centro (pan=0) conserva todo el volumen (a diferencia de
    la ley de potencia constante, que dejaría el centro a -3 dB)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    maxv = (1 << (BITS - 1)) - 1
    frames = bytearray()
    if CANALES == 1:
        for x in muestras:
            x = max(-1.0, min(1.0, x))
            frames += struct.pack("<h", int(x * maxv))
    else:
        pan = max(-1.0, min(1.0, pan))
        gl = 1.0 if pan <= 0 else (1.0 - pan)
        gr = 1.0 if pan >= 0 else (1.0 + pan)
        for x in muestras:
            x = max(-1.0, min(1.0, x))
            l = int(max(-1.0, min(1.0, x * gl)) * maxv)
            r = int(max(-1.0, min(1.0, x * gr)) * maxv)
            frames += struct.pack("<hh", l, r)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(CANALES)
        w.setsampwidth(BITS // 8)
        w.setframerate(SR)
        w.writeframes(bytes(frames))


# ── Diseño de cada sonido ─────────────────────────────────────────────────────
# Cada función devuelve las muestras listas para escribir. Las decisiones
# tonales buscan sobriedad: nada infantil, nada estridente.

def gen_app_inicio():
    # Acorde mayor C-E-G en arpegio rápido, con cuerpo (detune) y caída
    # natural: da la bienvenida sin sonar a videojuego.
    d = 0.16
    partes = [
        _perc(_detune(C4, d,        0.40), 0.004, 0.14),
        _perc(_detune(E4, d,        0.40), 0.004, 0.14),
        _perc(_detune(G4, d + 0.10, 0.45), 0.004, 0.22),
    ]
    retardo = int(SR * 0.075)
    n_total = max(retardo * (i + 1) + len(p) for i, p in enumerate(partes))
    mix = [0.0] * n_total
    for i, p in enumerate(partes):
        off = retardo * i
        for j, v in enumerate(p):
            mix[off + j] += v
    return _normalizar(mix, 0.75)


def gen_conectando():
    # Dos pulsos con hueco: leído como "esperando", no como "listo".
    pulso = _perc(_triangular(A4, 0.10, 0.40), 0.006, 0.05)
    return _concat(pulso, _silencio(0.06), pulso, _silencio(0.02))


def gen_conectado():
    # Quinta C5-G5 cálida y abierta, con cuerpo y decaimiento suave.
    a = _detune(C5, 0.26, 0.34)
    b = _detune(G5, 0.26, 0.22)
    return _normalizar(_perc(_suma(a, b), 0.005, 0.20), 0.8)


def gen_desconectado():
    # Caída E5→C5: gesto descendente = "se cierra".
    t1 = _perc(_triangular(E5, 0.13, 0.35), 0.005, 0.10)
    t2 = _perc(_triangular(C5, 0.16, 0.32), 0.005, 0.14)
    return _normalizar(_concat(t1, t2), 0.75)


def gen_mensaje():
    # Amplitud baja y duración corta porque suena potencialmente cientos
    # de veces por sesión: cualquier cosa más notable cansa rapidísimo.
    return _normalizar(_perc(_seno(G5, 0.07, 0.22), 0.010, 0.045), 0.42)


def gen_superchat():
    # Parcial inarmónico (f * 4.2) imita el espectro de una campana real;
    # sin él suena a órgano y pierde la asociación con "importante". Cada
    # parcial decae a su ritmo (los agudos antes), como una campana de verdad.
    f = A5
    partes = [
        _perc(_seno(f,       0.45, 0.32), 0.002, 0.34),
        _perc(_seno(f * 2,   0.40, 0.14), 0.002, 0.20),
        _perc(_seno(f * 3,   0.30, 0.08), 0.002, 0.12),
        _perc(_seno(f * 4.2, 0.20, 0.05), 0.002, 0.07),
    ]
    return _normalizar(_suma(*partes), 0.8)


def gen_miembro():
    # Tríada ascendente C-E-G brillante: alguien "sube" al canal. Leve paneo
    # a la derecha (ver PANEO) para distinguirla del arranque.
    d = 0.11
    n1 = _perc(_detune(C5, d,        0.35), 0.005, 0.10)
    n2 = _perc(_detune(E5, d,        0.38), 0.005, 0.10)
    n3 = _perc(_detune(G5, d + 0.08, 0.42), 0.005, 0.18)
    return _normalizar(_concat(n1, n2, n3), 0.80)


def gen_error():
    # Dos senos muy cercanos producen un batido (beat) que el oído asocia
    # a aviso; más limpio que un zumbido grave solo.
    a = _seno(175, 0.20, 0.35)
    b = _seno(185, 0.20, 0.35)
    return _normalizar(_perc(_suma(a, b), 0.003, 0.16), 0.75)


def gen_pausa():
    # Descendente G4→D4: "se detiene".
    n1 = _perc(_triangular(G4, 0.07, 0.32), 0.004, 0.07)
    n2 = _perc(_triangular(D4, 0.10, 0.32), 0.004, 0.10)
    return _normalizar(_concat(n1, n2), 0.7)


def gen_reanudar():
    # Ascendente D4→G4: espejo de la pausa, "se reanuda".
    n1 = _perc(_triangular(D4, 0.07, 0.32), 0.004, 0.07)
    n2 = _perc(_triangular(G4, 0.10, 0.32), 0.004, 0.10)
    return _normalizar(_concat(n1, n2), 0.7)


def gen_transporte_en_curso():
    return _normalizar(_perc(_triangular(A4, 0.07, 0.28), 0.003, 0.05), 0.52)


def gen_copiar():
    # Tic agudo y muy breve: confirmación discreta.
    return _normalizar(_perc(_triangular(C6, 0.05, 0.30), 0.002, 0.04), 0.55)


def gen_voz_cambiada():
    return _normalizar(_perc(_triangular(E5, 0.10, 0.30), 0.005, 0.07), 0.65)


# ── Sonidos nuevos (v0.6 online y acciones que antes reusaban otros) ──────────

def gen_enviado():
    # Mensaje enviado al chat en vivo. Dos notas ascendentes E5→A5, brillante
    # y resuelto: "salió". Leve paneo a la derecha (acción saliente).
    n1 = _perc(_triangular(E5, 0.06, 0.34), 0.003, 0.06)
    n2 = _perc(_detune(A5, 0.12, 0.36),     0.003, 0.12)
    return _normalizar(_concat(n1, n2), 0.7)


def gen_comentario():
    # Comentario publicado/respondido. Doble blip G5→C6, suave y claro,
    # emparentado con "enviado" pero distinguible (más agudo y corto).
    n1 = _perc(_triangular(G5, 0.05, 0.30), 0.003, 0.05)
    n2 = _perc(_triangular(C6, 0.09, 0.32), 0.003, 0.09)
    return _normalizar(_concat(n1, n2), 0.62)


def gen_moderacion():
    # Banear / expulsar (timeout). Dos notas graves y firmes A3→E3 con cuerpo:
    # autoritario y serio, sin ser alarmante como el error. Paneo a la izquierda.
    n1 = _perc(_detune(A3, 0.14, 0.40, cents=5), 0.004, 0.12)
    n2 = _perc(_detune(E3, 0.20, 0.40, cents=5), 0.004, 0.18)
    return _normalizar(_concat(n1, n2), 0.78)


def gen_cola_vaciada():
    # Cola de lectura vaciada. Barrido descendente A5→D5: gesto de "barrer/
    # limpiar". Corto y suave para no competir con nada importante.
    sweep = _glide(A5, D5, 0.16, 0.30)
    return _normalizar(_perc(sweep, 0.004, 0.13), 0.55)


# ── Avisos con sonido propio (encargo 174) ───────────────────────────────────
# Familias por timbre: descargas en triangular con cuerpo (detune), transmisión
# en seno cálido, actualización en barrido y acorde, y un aviso neutro en
# campanita de dos notas. Dentro de cada familia el contorno dice el resultado.

def gen_descarga_iniciada():
    # Dos notas cortas ascendentes E5→G5: "arranca".
    n1 = _perc(_detune(E5, 0.07, 0.36), 0.003, 0.06)
    n2 = _perc(_detune(G5, 0.09, 0.38), 0.003, 0.08)
    return _normalizar(_concat(n1, n2), 0.7)


def gen_descarga_completada():
    # Tres notas ascendentes que cierran en acorde mayor: "salió bien".
    n1 = _perc(_detune(C5, 0.07, 0.34), 0.003, 0.06)
    n2 = _perc(_detune(E5, 0.07, 0.34), 0.003, 0.06)
    cierre = _perc(_suma(_detune(C5, 0.20, 0.30),
                         _detune(E5, 0.20, 0.30),
                         _detune(G5, 0.20, 0.32)), 0.004, 0.16)
    return _normalizar(_concat(n1, n2, cierre), 0.75)


def gen_descarga_fallida():
    # Tercera menor descendente G5→E5: "salió mal", sin aspereza de error.
    n1 = _perc(_detune(G5, 0.11, 0.36), 0.004, 0.10)
    n2 = _perc(_detune(E5, 0.18, 0.36), 0.004, 0.15)
    return _normalizar(_concat(n1, n2), 0.72)


def gen_descarga_cancelada():
    # Dos notas cortas descendentes E5→C5: "se cortó", espejo de la iniciada.
    n1 = _perc(_detune(E5, 0.07, 0.34), 0.003, 0.06)
    n2 = _perc(_detune(C5, 0.09, 0.34), 0.003, 0.08)
    return _normalizar(_concat(n1, n2), 0.68)


def gen_al_aire():
    # Arpegio brillante C5-E5-G5-C6: el directo ya se ve.
    notas = [_perc(_seno(f, d, 0.32), 0.003, t)
             for f, d, t in ((C5, 0.07, 0.06), (E5, 0.07, 0.06),
                             (G5, 0.07, 0.06), (C6, 0.14, 0.12))]
    return _normalizar(_concat(*notas), 0.78)


def gen_transmision_detenida():
    # Descenso calmo G5-E5-C5: "se terminó", sin alarma.
    notas = [_perc(_seno(f, d, 0.30), 0.005, t)
             for f, d, t in ((G5, 0.12, 0.10), (E5, 0.12, 0.10),
                             (C5, 0.22, 0.18))]
    return _normalizar(_concat(*notas), 0.7)


def gen_transmision_problema():
    # Doble pulso grave A3 con hueco: insiste sin estridencia.
    pulso = _perc(_seno(A3, 0.12, 0.40), 0.004, 0.10)
    return _concat(pulso, _silencio(0.08), pulso, _silencio(0.02))


def gen_grabacion_problema():
    # Pulso grave y otro más agudo y corto: la grabación no arrancó.
    grave = _perc(_seno(A3, 0.14, 0.38), 0.004, 0.11)
    agudo = _perc(_seno(E4, 0.08, 0.34), 0.003, 0.06)
    return _normalizar(
        _concat(grave, _silencio(0.04), agudo, _silencio(0.02)), 0.7)


def gen_directo_finalizado():
    # Confirmación de cierre corta y resuelta: subida E5→C6 que asienta.
    # Distinta del descenso de transmision_detenida y del arpegio de al_aire.
    n1 = _perc(_seno(E5, 0.10, 0.34), 0.004, 0.09)
    n2 = _perc(_seno(C6, 0.20, 0.34), 0.004, 0.16)
    return _normalizar(_concat(n1, n2), 0.72)


def gen_transmision_recuperada():
    # Vuelta de la conexión: subida corta G4→C5, cálida y breve. Es un alivio,
    # no una alarma, y no comparte registro con transmision_problema (A3),
    # al_aire (C5-C6), conectado (C5-G5) ni directo_finalizado (E5-C6).
    n1 = _perc(_seno(G4, 0.09, 0.34), 0.004, 0.07)
    n2 = _perc(_seno(C5, 0.16, 0.36), 0.004, 0.13)
    return _normalizar(_concat(n1, n2), 0.7)


def gen_aviso():
    # Campanita neutra de dos notas E6→B5: avisa sin calificar.
    n1 = _perc(_seno(E6, 0.12, 0.30), 0.002, 0.10)
    n2 = _perc(_seno(B5, 0.22, 0.30), 0.002, 0.18)
    return _normalizar(_concat(n1, n2), 0.65)


def gen_actualizacion_disponible():
    # Brillo ascendente C5→G5: "hay algo nuevo".
    barrido = _glide(C5, G5, 0.22, 0.30)
    return _normalizar(_perc(barrido, 0.004, 0.18), 0.7)


def gen_actualizacion_lista():
    # Acorde mayor C-E-G sostenido y resuelto: "quedó instalada".
    acorde = _suma(_detune(C5, 0.45, 0.28),
                   _detune(E5, 0.45, 0.28),
                   _detune(G5, 0.45, 0.30))
    return _normalizar(_perc(acorde, 0.005, 0.34), 0.75)


# ── Música: cambio, fin y fallo (encargo 209) ────────────────────────────────
# Suenan con música de fondo, así que son cortos y de amplitud baja para no
# tapar ni la música ni el chat. Comparten registro de seno cálido.

def gen_musica_tema():
    # Suena sobre la música y el fundido: por eso grave, lento y bajo.
    acorde = _suma(_seno(A3, 0.45, 0.30), _seno(E4, 0.45, 0.24))
    return _normalizar(_perc(acorde, 0.025, 0.22), 0.35)


def gen_musica_fin():
    # Descenso B4→G4 que resuelve abajo: gesto de cierre, distinto del
    # E5→C5 de desconectado y del fin_directo.
    n1 = _perc(_seno(B4, 0.11, 0.28), 0.005, 0.10)
    n2 = _perc(_seno(G4, 0.20, 0.28), 0.005, 0.16)
    return _normalizar(_concat(n1, n2), 0.6)


def gen_musica_fallo():
    # Tercera menor descendente D5→B4, mate y sin alarma: un tema se saltó,
    # no es una acción pedida como el error.
    n1 = _perc(_seno(D5, 0.09, 0.24), 0.004, 0.08)
    n2 = _perc(_seno(B4, 0.17, 0.24), 0.004, 0.14)
    return _normalizar(_concat(n1, n2), 0.56)


def gen_musica_igualando():
    # Tres notas cortas ascendentes E4→G4→A4, suaves y bajas: avisa que
    # empieza a medir muchas canciones. Tres notas porque los otros tres
    # de música son de dos (tema, fin y fallo).
    n1 = _perc(_seno(E4, 0.08, 0.24), 0.004, 0.07)
    n2 = _perc(_seno(G4, 0.08, 0.24), 0.004, 0.07)
    n3 = _perc(_seno(A4, 0.14, 0.24), 0.004, 0.12)
    return _normalizar(_concat(n1, n2, n3), 0.55)


# ── Preguntar a la IA: consulta, respuesta y fallo ────────────────────────────
# Cortos y sobrios: la respuesta suena justo antes de que lea el lector.

def gen_ia_enviada():
    # Glide ascendente continuo E4→A4, grave: la pregunta sale.
    barrido = _glide(E4, A4, 0.20, 0.30)
    return _normalizar(_perc(barrido, 0.004, 0.16), 0.7)


def gen_ia_respuesta():
    # Dos notas cálidas A4→D5, la segunda más aguda: llegó la respuesta.
    n1 = _perc(_seno(A4, 0.08, 0.26), 0.004, 0.07)
    n2 = _perc(_seno(D5, 0.14, 0.26), 0.004, 0.12)
    return _normalizar(_concat(n1, n2), 0.58)


def gen_ia_error():
    # Dos notas graves descendentes C4→A3: la consulta falló.
    n1 = _perc(_seno(C4, 0.11, 0.30), 0.005, 0.10)
    n2 = _perc(_seno(A3, 0.18, 0.30), 0.005, 0.15)
    return _normalizar(_concat(n1, n2), 0.72)


# ── Preguntar a la IA: espera, captura, cancelación y captura negra ──────────
# El de espera se repite cada 2 segundos: figura melódica baja y suave que
# no tapa al lector. El resto sigue el lenguaje de gestos del archivo.

def gen_ia_analizando():
    # Cuatro notas que suben y bajan sin resolver (E4→G4→A4→G4): suena a
    # "pensando", no a aviso. Normalizada bajo porque se repite.
    n1 = _perc(_seno(E4, 0.22, 0.24), 0.006, 0.20)
    n2 = _perc(_seno(G4, 0.22, 0.24), 0.006, 0.20)
    n3 = _perc(_seno(A4, 0.22, 0.24), 0.006, 0.20)
    n4 = _perc(_seno(G4, 0.30, 0.24), 0.006, 0.26)
    return _normalizar(_concat(n1, n2, n3, n4), 0.4)


def gen_ia_captura():
    # Clic de obturador: dos toques brevísimos y secos, menos de 0,2 segundos.
    c1 = _perc(_seno(E6, 0.05, 0.35), 0.001, 0.035)
    c2 = _perc(_seno(B5, 0.11, 0.35), 0.001, 0.08)
    return _normalizar(_concat(c1, c2), 0.7)


def gen_ia_cancelada():
    # Dos notas descendentes cortas y más agudas que ia_error: se canceló
    # a pedido, no falló nada.
    n1 = _perc(_seno(B5, 0.06, 0.30), 0.003, 0.05)
    n2 = _perc(_seno(G5, 0.10, 0.30), 0.003, 0.08)
    return _normalizar(_concat(n1, n2), 0.68)


def gen_ia_imagen_negra():
    # Nota grave sostenida con pulso: hay que cambiar algo en OBS. Distinta
    # del doble descenso de ia_error y del par agudo de ia_cancelada.
    base = _seno(F3, 0.45, 0.32)
    pulsada = [m * (0.65 + 0.35 * math.sin(2 * math.pi * 7 * i / SR))
               for i, m in enumerate(base)]
    return _normalizar(_perc(pulsada, 0.005, 0.38), 0.72)


# ── Atajos globales ocupados ──────────────────────────────────────────────────

def gen_atajos_ocupados():
    # Tono de ocupado, como el del teléfono: dos toques graves iguales.
    toque = _perc(_triangular(E4, 0.07, 0.40), 0.005, 0.10)
    return _normalizar(_concat(toque, _silencio(0.06), toque), 0.5)


def gen_microfono_sin_senal():
    # Dos notas que bajan, G4 y D4: la línea se cae.
    arriba = _perc(_seno(G4, 0.12, 0.45), 0.005, 0.35)
    abajo = _perc(_seno(D4, 0.12, 0.45), 0.005, 0.35)
    return _normalizar(_concat(arriba, _silencio(0.03), abajo), 0.5)


def gen_directo_pausado():
    # Pausa del directo: dos notas graves que bajan, E4 y C4, con hueco.
    alta = _perc(_seno(E4, 0.12, 0.45), 0.005, 0.35)
    baja = _perc(_seno(C4, 0.14, 0.45), 0.005, 0.35)
    return _normalizar(_concat(alta, _silencio(0.03), baja), 0.5)


def gen_directo_reanudado():
    # Vuelta del directo: espejo ascendente de la pausa, C4 y E4.
    baja = _perc(_seno(C4, 0.12, 0.45), 0.005, 0.35)
    alta = _perc(_seno(E4, 0.14, 0.45), 0.005, 0.35)
    return _normalizar(_concat(baja, _silencio(0.03), alta), 0.5)


# ── Búsqueda y cola de descargas ────────────────────────────────────────────
# La búsqueda es una familia nueva en seno claro, distinta del triangular
# con detune de las descargas. Dentro de cada familia el contorno dice el
# resultado.

def gen_busqueda_iniciada():
    # Barrido corto ascendente: una pregunta.
    barrido = _glide(E5, A5, 0.20, 0.30)
    return _normalizar(_perc(barrido, 0.004, 0.16), 0.7)


def gen_busqueda_resultados():
    # Dos notas ascendentes con la segunda sostenida: "hay algo".
    n1 = _perc(_seno(E5, 0.08, 0.32), 0.004, 0.07)
    n2 = _perc(_seno(A5, 0.20, 0.34), 0.004, 0.16)
    return _normalizar(_concat(n1, n2), 0.7)


def gen_busqueda_sin_resultados():
    # Una nota sola media que cae apenas al final: "no hay nada".
    nota = _perc(_seno(A4, 0.22, 0.32), 0.005, 0.18)
    caida = _perc(_glide(A4, G4, 0.10, 0.30), 0.005, 0.08)
    return _normalizar(_concat(nota, caida), 0.68)


def gen_busqueda_fallida():
    # Dos notas graves descendentes: "no se pudo buscar".
    n1 = _perc(_seno(D4, 0.12, 0.32), 0.005, 0.10)
    n2 = _perc(_seno(B3, 0.20, 0.32), 0.005, 0.16)
    return _normalizar(_concat(n1, n2), 0.72)


def gen_escucha_cargando():
    # Dos pulsos cortos ascendentes en seno claro: se carga la previa.
    n1 = _perc(_seno(E5, 0.06, 0.32), 0.004, 0.05)
    n2 = _perc(_seno(G5, 0.10, 0.34), 0.004, 0.08)
    return _normalizar(_concat(n1, n2), 0.7)


def gen_escucha_fallida():
    # Dos pulsos graves en la misma nota: no se pudo escuchar, sin el
    # descenso de la búsqueda fallida ni la aspereza del error.
    n1 = _perc(_seno(E3, 0.12, 0.34), 0.005, 0.10)
    n2 = _perc(_seno(E3, 0.18, 0.34), 0.005, 0.14)
    return _normalizar(_concat(n1, n2), 0.7)


def gen_descarga_encolada():
    # Una nota corta con golpe: breve para no cansar al agregar muchas.
    return _normalizar(_perc(_detune(A5, 0.16, 0.42), 0.003, 0.10), 0.7)


def gen_descarga_procesando():
    # Tres pulsos iguales en la misma nota: trabajo en curso.
    pulso = _perc(_detune(E5, 0.07, 0.36), 0.003, 0.05)
    return _normalizar(
        _concat(pulso, _silencio(0.04), pulso, _silencio(0.04), pulso,
                _silencio(0.02)), 0.7)


def gen_cola_descargas_terminada():
    # Arpegio ascendente de cuatro notas, más largo que descarga_completada.
    notas = [_perc(_detune(f, d, 0.34), 0.003, t)
             for f, d, t in ((C5, 0.07, 0.06), (E5, 0.07, 0.06),
                             (G5, 0.07, 0.06), (C6, 0.24, 0.20))]
    return _normalizar(_concat(*notas), 0.75)


def gen_descarga_parcial():
    # Sube y baja: ni bien ni mal, distinta de descarga_fallida.
    subida = _perc(_detune(E5, 0.08, 0.36), 0.003, 0.06)
    cima = _perc(_detune(G5, 0.08, 0.36), 0.003, 0.06)
    bajada = _perc(_detune(E5, 0.14, 0.36), 0.003, 0.12)
    return _normalizar(_concat(subida, cima, bajada), 0.7)


# ── Tema "suave": senos cálidos con decaimiento tipo marimba/madera ───────────
# Más redondo, bajo y mate que el tema por defecto: nada de aristas brillantes
# ni regusto a videojuego. Mismo lenguaje de gestos (ascendente = abrir, etc.).

def _madera(freq, dur, amp, tau=0.12):
    # Seno fundamental + un toque de octava: timbre de madera/marimba, suave.
    base = _suma(_seno(freq, dur, amp), _seno(freq * 2, dur, amp * 0.18))
    return _perc(base, 0.005, tau)


def _seq(*notas):
    return _normalizar(_concat(*notas), 0.7)


def s_app_inicio():
    # Quinta y octava abiertas C4-G4-C5: cálido, recibe sin estridencia.
    return _seq(_madera(C4, 0.10, 0.42, 0.10),
                _madera(G4, 0.10, 0.42, 0.10),
                _madera(C5, 0.30, 0.46, 0.26))


def s_conectando():
    pulso = _madera(A3, 0.12, 0.40, 0.09)
    return _concat(pulso, _silencio(0.07), pulso, _silencio(0.02))


def s_conectado():
    # Tercera mayor C5-E5 sostenida y redonda.
    return _normalizar(_perc(_suma(_seno(C5, 0.30, 0.34), _seno(E5, 0.30, 0.26)),
                             0.006, 0.24), 0.78)


def s_desconectado():
    return _seq(_madera(E5, 0.12, 0.34, 0.10), _madera(C5, 0.22, 0.32, 0.16))


def s_mensaje():
    # Toque de madera muy breve y bajo: el evento más frecuente, casi un roce.
    return _normalizar(_madera(C5, 0.08, 0.20, 0.05), 0.40)


def s_superchat():
    # Campana cálida: pocos parciales y mucho seno, registro medio (F5).
    f = F5
    partes = [
        _perc(_seno(f,       0.55, 0.34), 0.003, 0.42),
        _perc(_seno(f * 2,   0.45, 0.12), 0.003, 0.26),
        _perc(_seno(f * 3.1, 0.30, 0.05), 0.003, 0.14),
    ]
    return _normalizar(_suma(*partes), 0.78)


def s_miembro():
    return _seq(_madera(C5, 0.11, 0.36, 0.10),
                _madera(E5, 0.11, 0.38, 0.10),
                _madera(G5, 0.26, 0.42, 0.20))


def s_error():
    # Dos notas graves y mates descendentes A3→F3: "algo no fue", sin aspereza.
    return _seq(_madera(A3, 0.16, 0.40, 0.13), _madera(F3, 0.24, 0.40, 0.18))


def s_pausa():
    return _seq(_madera(G4, 0.10, 0.34, 0.08), _madera(D4, 0.16, 0.34, 0.12))


def s_reanudar():
    return _seq(_madera(D4, 0.10, 0.34, 0.08), _madera(G4, 0.16, 0.34, 0.12))


def s_transporte_en_curso():
    return _normalizar(_madera(A4, 0.08, 0.26, 0.05), 0.48)


def s_copiar():
    return _normalizar(_madera(C6, 0.07, 0.30, 0.04), 0.5)


def s_voz_cambiada():
    return _normalizar(_madera(E5, 0.12, 0.30, 0.08), 0.6)


def s_enviado():
    return _seq(_madera(E5, 0.09, 0.34, 0.07), _madera(A5, 0.16, 0.36, 0.13))


def s_comentario():
    return _seq(_madera(G5, 0.08, 0.30, 0.06), _madera(C6, 0.13, 0.32, 0.10))


def s_moderacion():
    return _seq(_madera(A3, 0.16, 0.42, 0.13), _madera(E3, 0.24, 0.42, 0.20))


def s_cola_vaciada():
    return _normalizar(_perc(_glide(A5, D5, 0.18, 0.28), 0.005, 0.14), 0.5)


# ── Avisos con sonido propio, versión suave ──────────────────────────────────
# Los mismos gestos que en el tema por defecto, en madera cálida.

def s_descarga_iniciada():
    return _seq(_madera(D5, 0.07, 0.34, 0.06),
                _madera(A5, 0.10, 0.36, 0.08))


def s_descarga_completada():
    # Tríada menor ascendente D-F-A con cierre largo: "salió bien".
    return _seq(_madera(D5, 0.07, 0.34, 0.06),
                _madera(F5, 0.07, 0.34, 0.06),
                _madera(A5, 0.24, 0.38, 0.18))


def s_descarga_fallida():
    return _seq(_madera(G5, 0.11, 0.36, 0.09),
                _madera(E5, 0.18, 0.36, 0.14))


def s_descarga_cancelada():
    return _seq(_madera(E5, 0.07, 0.32, 0.06),
                _madera(C5, 0.10, 0.32, 0.08))


def s_al_aire():
    return _seq(_madera(C5, 0.07, 0.34, 0.06),
                _madera(E5, 0.07, 0.34, 0.06),
                _madera(G5, 0.07, 0.36, 0.06),
                _madera(C6, 0.16, 0.38, 0.13))


def s_transmision_detenida():
    return _seq(_madera(G5, 0.13, 0.32, 0.10),
                _madera(E5, 0.13, 0.32, 0.10),
                _madera(C5, 0.24, 0.32, 0.18))


def s_transmision_problema():
    pulso = _madera(A3, 0.12, 0.40, 0.10)
    return _concat(pulso, _silencio(0.08), pulso, _silencio(0.02))


def s_grabacion_problema():
    grave = _madera(A3, 0.14, 0.38, 0.11)
    agudo = _madera(E4, 0.08, 0.34, 0.06)
    return _concat(grave, _silencio(0.04), agudo, _silencio(0.02))


def s_directo_finalizado():
    return _seq(_madera(E5, 0.11, 0.34, 0.09),
                _madera(C6, 0.20, 0.36, 0.16))


def s_transmision_recuperada():
    # Vuelta de la conexión: subida corta G4→C5 en madera cálida, distinta del
    # descenso de transmision_detenida y de transmision_problema.
    return _seq(_madera(G4, 0.09, 0.34, 0.07),
                _madera(C5, 0.16, 0.36, 0.13))


def s_aviso():
    return _seq(_madera(E6, 0.10, 0.32, 0.08),
                _madera(B5, 0.20, 0.34, 0.15))


def s_actualizacion_disponible():
    return _normalizar(_perc(_glide(C5, A5, 0.24, 0.28), 0.005, 0.18), 0.6)


def s_actualizacion_lista():
    return _normalizar(_perc(_suma(_seno(C5, 0.45, 0.30), _seno(E5, 0.45, 0.24),
                                  _seno(G5, 0.45, 0.22)), 0.006, 0.34), 0.75)


# ── Música en el tema suave (encargo 209) ────────────────────────────────────
# Los mismos gestos en madera cálida, cortos y bajos por sonar con música.

def s_musica_tema():
    # Suena sobre la música y el fundido: por eso grave, lento y bajo.
    base = _suma(_madera(A3, 0.45, 0.30, 0.22),
                 _madera(E4, 0.45, 0.24, 0.22))
    na = int(SR * 0.025)
    con_ataque = [m * (i / na) if i < na else m for i, m in enumerate(base)]
    return _normalizar(con_ataque, 0.32)


def s_musica_fin():
    return _seq(_madera(B4, 0.11, 0.30, 0.09),
                _madera(G4, 0.20, 0.30, 0.16))


def s_musica_fallo():
    return _seq(_madera(D5, 0.10, 0.28, 0.08),
                _madera(B4, 0.17, 0.28, 0.14))


def s_musica_igualando():
    # Las mismas tres notas ascendentes en madera cálida.
    return _seq(_madera(E4, 0.08, 0.28, 0.06),
                _madera(G4, 0.08, 0.28, 0.06),
                _madera(A4, 0.14, 0.28, 0.11))


# ── Preguntar a la IA en el tema suave ────────────────────────────────────────
# Los mismos gestos en madera cálida, bajos y breves por el lector.

def s_ia_enviada():
    # El mismo glide ascendente continuo, grave y mate.
    return _normalizar(_perc(_glide(E4, A4, 0.20, 0.28), 0.005, 0.16), 0.6)


def s_ia_respuesta():
    # Las mismas dos notas cálidas, la segunda más aguda, sin tapar al lector.
    return _normalizar(_concat(_madera(A4, 0.08, 0.28, 0.06),
                               _madera(D5, 0.14, 0.28, 0.11)), 0.58)


def s_ia_error():
    # Las mismas dos notas graves descendentes en madera.
    return _seq(_madera(C4, 0.11, 0.32, 0.09),
                _madera(A3, 0.18, 0.32, 0.14))


# ── Preguntar a la IA en el tema suave: espera, captura y demás ──────────────
# Los mismos gestos en madera cálida; la espera va baja porque se repite.

def s_ia_analizando():
    # La misma figura que sube y baja sin resolver, en madera y baja.
    return _normalizar(_concat(_madera(E4, 0.22, 0.26, 0.18),
                               _madera(G4, 0.22, 0.26, 0.18),
                               _madera(A4, 0.22, 0.26, 0.18),
                               _madera(G4, 0.30, 0.26, 0.24)), 0.4)


def s_ia_captura():
    # El mismo clic de obturador en madera, brevísimo y seco.
    return _normalizar(_concat(_madera(E6, 0.05, 0.34, 0.035),
                               _madera(B5, 0.11, 0.34, 0.08)), 0.65)


def s_ia_cancelada():
    # El mismo par descendente agudo en madera, más breve que el error.
    return _normalizar(_concat(_madera(B5, 0.06, 0.32, 0.05),
                               _madera(G5, 0.10, 0.32, 0.08)), 0.62)


def s_ia_imagen_negra():
    # La misma nota grave sostenida con pulso, en madera cálida.
    base = _suma(_seno(F3, 0.45, 0.32), _seno(F3 * 2, 0.45, 0.06))
    pulsada = [m * (0.65 + 0.35 * math.sin(2 * math.pi * 7 * i / SR))
               for i, m in enumerate(base)]
    return _normalizar(_perc(pulsada, 0.006, 0.38), 0.7)


# ── Atajos globales ocupados en el tema suave ─────────────────────────────────

def s_atajos_ocupados():
    # El mismo tono de ocupado en madera: dos toques graves iguales.
    toque = _madera(E4, 0.07, 0.40)
    return _normalizar(_concat(toque, _silencio(0.06), toque), 0.45)


def s_microfono_sin_senal():
    # Las mismas dos notas que bajan, en madera.
    arriba = _madera(G4, 0.12, 0.45, 0.35)
    abajo = _madera(D4, 0.12, 0.45, 0.35)
    return _normalizar(_concat(arriba, _silencio(0.03), abajo), 0.45)


def s_directo_pausado():
    # La misma pausa grave que baja, en madera.
    alta = _madera(E4, 0.12, 0.45, 0.35)
    baja = _madera(C4, 0.14, 0.45, 0.35)
    return _normalizar(_concat(alta, _silencio(0.03), baja), 0.45)


def s_directo_reanudado():
    # El mismo espejo ascendente de la pausa, en madera.
    baja = _madera(C4, 0.12, 0.45, 0.35)
    alta = _madera(E4, 0.14, 0.45, 0.35)
    return _normalizar(_concat(baja, _silencio(0.03), alta), 0.45)


# ── Búsqueda y cola de descargas en el tema suave ───────────────────────────
# Los mismos gestos: la búsqueda en seno claro como en el tema por defecto,
# las descargas en madera cálida.

def s_busqueda_iniciada():
    # El mismo barrido ascendente en seno claro.
    barrido = _glide(D5, A5, 0.22, 0.28)
    return _normalizar(_perc(barrido, 0.005, 0.17), 0.62)


def s_busqueda_resultados():
    # Las mismas dos notas ascendentes, la segunda sostenida.
    n1 = _perc(_seno(E5, 0.09, 0.30), 0.005, 0.07)
    n2 = _perc(_seno(A5, 0.22, 0.30), 0.005, 0.17)
    return _normalizar(_concat(n1, n2), 0.62)


def s_busqueda_sin_resultados():
    # La misma nota sola que cae apenas al final.
    nota = _perc(_seno(A4, 0.24, 0.30), 0.006, 0.19)
    caida = _perc(_glide(A4, G4, 0.11, 0.28), 0.006, 0.09)
    return _normalizar(_concat(nota, caida), 0.6)


def s_busqueda_fallida():
    # Las mismas dos notas graves descendentes.
    n1 = _perc(_seno(D4, 0.13, 0.30), 0.006, 0.11)
    n2 = _perc(_seno(B3, 0.21, 0.30), 0.006, 0.17)
    return _normalizar(_concat(n1, n2), 0.65)


def s_escucha_cargando():
    # Los mismos dos pulsos cortos ascendentes, en madera cálida.
    return _seq(_madera(E5, 0.06, 0.32, 0.05),
                _madera(G5, 0.10, 0.34, 0.08))


def s_escucha_fallida():
    # Los mismos dos pulsos graves en la misma nota, en madera cálida.
    return _seq(_madera(E3, 0.12, 0.34, 0.10),
                _madera(E3, 0.18, 0.34, 0.14))


def s_descarga_encolada():
    # La misma nota corta con golpe, en madera.
    return _normalizar(_madera(A5, 0.16, 0.40, 0.10), 0.65)


def s_descarga_procesando():
    # Los mismos tres pulsos iguales, en madera.
    pulso = _madera(E5, 0.07, 0.36, 0.05)
    return _concat(pulso, _silencio(0.04), pulso, _silencio(0.04), pulso,
                   _silencio(0.02))


def s_cola_descargas_terminada():
    # El mismo arpegio de cuatro notas, en madera.
    return _seq(_madera(C5, 0.07, 0.34, 0.06),
                _madera(E5, 0.07, 0.34, 0.06),
                _madera(G5, 0.07, 0.36, 0.06),
                _madera(C6, 0.26, 0.38, 0.20))


def s_descarga_parcial():
    # La misma subida y bajada, en madera.
    return _seq(_madera(E5, 0.08, 0.36, 0.06),
                _madera(G5, 0.08, 0.36, 0.06),
                _madera(E5, 0.16, 0.36, 0.12))


# ── Reemplazos del tema suave (encargo 174) ──────────────────────────────────
# Generadores propios para los que eran copia de otro dentro del tema.
# Cada uno conserva el gesto del evento con notas o duraciones distintas.

def s_fin_directo():
    # Cierre A5-D5-G4: termina abajo, distinto del descenso E5-C5.
    return _seq(_madera(A5, 0.10, 0.32, 0.08),
                _madera(D5, 0.10, 0.32, 0.08),
                _madera(G4, 0.20, 0.32, 0.15))


def s_cofre():
    # Arpegio E5-G5-B5: premio, distinto de la campana del superchat.
    return _seq(_madera(E5, 0.09, 0.34, 0.07),
                _madera(G5, 0.09, 0.34, 0.07),
                _madera(B5, 0.18, 0.36, 0.14))


def s_mensaje_propietario():
    # Campana en B5, registro más alto que la del superchat (F5).
    f = B5
    partes = [
        _perc(_seno(f,       0.50, 0.32), 0.003, 0.38),
        _perc(_seno(f * 2,   0.40, 0.11), 0.003, 0.24),
        _perc(_seno(f * 3.05, 0.28, 0.05), 0.003, 0.13),
    ]
    return _normalizar(_suma(*partes), 0.76)


def s_seguir():
    # Subida G4-C5-E5: alguien llega, una cuarta más abajo que el miembro.
    return _seq(_madera(G4, 0.10, 0.34, 0.08),
                _madera(C5, 0.10, 0.36, 0.08),
                _madera(E5, 0.20, 0.38, 0.15))


def s_regalo_grande():
    # Fanfarria E4-G4-C5-E5: cuatro notas, el inicio trae una más.
    return _seq(_madera(E4, 0.09, 0.36, 0.07),
                _madera(G4, 0.09, 0.36, 0.07),
                _madera(C5, 0.09, 0.38, 0.07),
                _madera(E5, 0.20, 0.40, 0.16))


def s_entrada():
    # Entrada D4-E4-G4: tres pasos ascendentes, no el salto de reanudar.
    return _seq(_madera(D4, 0.09, 0.32, 0.07),
                _madera(E4, 0.09, 0.32, 0.07),
                _madera(G4, 0.18, 0.34, 0.14))


def s_me_gusta():
    # Toque doble y mínimo A5-E6: el gesto más chico del tema.
    return _seq(_madera(A5, 0.08, 0.30, 0.06),
                _madera(E6, 0.10, 0.30, 0.07))


def s_mensaje_verificado():
    # Doble F5-C6: confirma en otro registro que el comentario (G5-C6).
    return _seq(_madera(F5, 0.08, 0.30, 0.06),
                _madera(C6, 0.12, 0.32, 0.09))


def s_orilla():
    # Tope suave G4-D4: grave y corto, no el tic agudo de copiar.
    return _seq(_madera(G4, 0.08, 0.32, 0.06),
                _madera(D4, 0.12, 0.32, 0.09))


def s_regalo_mediano():
    # Díada D5-A5 sostenida: regalo medio, otra quinta que la de conectado.
    return _normalizar(_perc(_suma(_seno(D5, 0.35, 0.30), _seno(A5, 0.35, 0.24)),
                             0.006, 0.28), 0.75)


# Catálogo de temas: nombre → {archivo (= evento) .wav : generador}.
TEMAS = {
    "default": {
        "app_inicio.wav":    gen_app_inicio,
        "conectando.wav":    gen_conectando,
        "conectado.wav":     gen_conectado,
        "desconectado.wav":  gen_desconectado,
        "mensaje_nuevo.wav": gen_mensaje,
        # Sonidos provisorios de roles hasta que el dueño elija los definitivos.
        "mensaje_propietario.wav": gen_superchat,
        "mensaje_moderador.wav": gen_moderacion,
        "mensaje_verificado.wav": gen_copiar,
        "mensaje_miembro.wav": gen_miembro,
        "superchat.wav":     gen_superchat,
        "nuevo_miembro.wav": gen_miembro,
        "error.wav":         gen_error,
        "pausa.wav":         gen_pausa,
        "reanudar.wav":      gen_reanudar,
        "transporte_en_curso.wav": gen_transporte_en_curso,
        "copiar.wav":        gen_copiar,
        "voz_cambiada.wav":  gen_voz_cambiada,
        "enviado.wav":       gen_enviado,
        "comentario.wav":    gen_comentario,
        "moderacion.wav":    gen_moderacion,
        "cola_vaciada.wav":  gen_cola_vaciada,
        # Sonidos provisorios de eventos de TikTok hasta que el dueño elija
        # los definitivos: reutilizan otros generadores, nunca el común.
        "seguir.wav":         gen_miembro,
        "compartir.wav":      gen_enviado,
        "cofre.wav":          gen_superchat,
        "me_gusta.wav":       gen_copiar,
        "regalo_chico.wav":   gen_comentario,
        "regalo_mediano.wav": gen_conectado,
        "regalo_grande.wav":  gen_app_inicio,
        "entrada.wav":        gen_reanudar,
        # Provisorios hasta que el dueño elija los definitivos (los WAV ya
        # existen y no se pisan): la orilla es un tic breve, el fin del
        # directo un gesto de cierre como el de desconexión.
        "orilla.wav":         gen_copiar,
        "fin_directo.wav":    gen_desconectado,
        # Avisos con sonido propio (encargo 174).
        "descarga_iniciada.wav":       gen_descarga_iniciada,
        "descarga_completada.wav":     gen_descarga_completada,
        "descarga_fallida.wav":        gen_descarga_fallida,
        "descarga_cancelada.wav":      gen_descarga_cancelada,
        "al_aire.wav":                 gen_al_aire,
        "transmision_detenida.wav":    gen_transmision_detenida,
        "transmision_problema.wav":    gen_transmision_problema,
        "grabacion_problema.wav":      gen_grabacion_problema,
        "transmision_recuperada.wav":  gen_transmision_recuperada,
        "directo_finalizado.wav":      gen_directo_finalizado,
        "aviso.wav":                   gen_aviso,
        "actualizacion_disponible.wav": gen_actualizacion_disponible,
        "actualizacion_lista.wav":      gen_actualizacion_lista,
        # Música (encargo 209).
        "musica_tema.wav":             gen_musica_tema,
        "musica_fin.wav":              gen_musica_fin,
        "musica_fallo.wav":            gen_musica_fallo,
        "musica_igualando.wav":        gen_musica_igualando,
        # Preguntar a la IA.
        "ia_enviada.wav":              gen_ia_enviada,
        "ia_respuesta.wav":            gen_ia_respuesta,
        "ia_error.wav":                gen_ia_error,
        "ia_analizando.wav":           gen_ia_analizando,
        "ia_captura.wav":              gen_ia_captura,
        "ia_cancelada.wav":            gen_ia_cancelada,
        "ia_imagen_negra.wav":         gen_ia_imagen_negra,
        # Atajos globales ocupados.
        "atajos_ocupados.wav":         gen_atajos_ocupados,
        # Micrófono activado sin señal que entre.
        "microfono_sin_senal.wav":     gen_microfono_sin_senal,
        # Pausa del directo de TikTok y su vuelta.
        "directo_pausado.wav":         gen_directo_pausado,
        "directo_reanudado.wav":       gen_directo_reanudado,
        # Búsqueda y cola de descargas.
        "busqueda_iniciada.wav":       gen_busqueda_iniciada,
        "busqueda_resultados.wav":     gen_busqueda_resultados,
        "busqueda_sin_resultados.wav": gen_busqueda_sin_resultados,
        "busqueda_fallida.wav":        gen_busqueda_fallida,
        "escucha_cargando.wav":        gen_escucha_cargando,
        "escucha_fallida.wav":         gen_escucha_fallida,
        "descarga_encolada.wav":       gen_descarga_encolada,
        "descarga_procesando.wav":     gen_descarga_procesando,
        "cola_descargas_terminada.wav": gen_cola_descargas_terminada,
        "descarga_parcial.wav":        gen_descarga_parcial,
    },
    "suave": {
        "app_inicio.wav":    s_app_inicio,
        "conectando.wav":    s_conectando,
        "conectado.wav":     s_conectado,
        "desconectado.wav":  s_desconectado,
        "mensaje_nuevo.wav": s_mensaje,
        # Sonidos provisorios de roles hasta que el dueño elija los definitivos.
        "mensaje_propietario.wav": s_mensaje_propietario,
        "mensaje_moderador.wav": s_moderacion,
        "mensaje_verificado.wav": s_mensaje_verificado,
        "mensaje_miembro.wav": s_miembro,
        "superchat.wav":     s_superchat,
        "nuevo_miembro.wav": s_miembro,
        "error.wav":         s_error,
        "pausa.wav":         s_pausa,
        "reanudar.wav":      s_reanudar,
        "transporte_en_curso.wav": s_transporte_en_curso,
        "copiar.wav":        s_copiar,
        "voz_cambiada.wav":  s_voz_cambiada,
        "enviado.wav":       s_enviado,
        "comentario.wav":    s_comentario,
        "moderacion.wav":    s_moderacion,
        "cola_vaciada.wav":  s_cola_vaciada,
        # Sonidos provisorios de eventos de TikTok hasta que el dueño elija
        # los definitivos: reutilizan otros generadores, nunca el común.
        "seguir.wav":         s_seguir,
        "compartir.wav":      s_enviado,
        "cofre.wav":          s_cofre,
        "me_gusta.wav":       s_me_gusta,
        "regalo_chico.wav":   s_comentario,
        "regalo_mediano.wav": s_regalo_mediano,
        "regalo_grande.wav":  s_regalo_grande,
        "entrada.wav":        s_entrada,
        # La orilla y el fin del directo ya tienen generador propio; el resto
        # de los provisorios sigue reutilizando otros generadores.
        "orilla.wav":         s_orilla,
        "fin_directo.wav":    s_fin_directo,
        # Avisos con sonido propio (encargo 174).
        "descarga_iniciada.wav":       s_descarga_iniciada,
        "descarga_completada.wav":     s_descarga_completada,
        "descarga_fallida.wav":        s_descarga_fallida,
        "descarga_cancelada.wav":      s_descarga_cancelada,
        "al_aire.wav":                 s_al_aire,
        "transmision_detenida.wav":    s_transmision_detenida,
        "transmision_problema.wav":    s_transmision_problema,
        "grabacion_problema.wav":      s_grabacion_problema,
        "transmision_recuperada.wav":  s_transmision_recuperada,
        "directo_finalizado.wav":      s_directo_finalizado,
        "aviso.wav":                   s_aviso,
        "actualizacion_disponible.wav": s_actualizacion_disponible,
        "actualizacion_lista.wav":      s_actualizacion_lista,
        # Música (encargo 209).
        "musica_tema.wav":             s_musica_tema,
        "musica_fin.wav":              s_musica_fin,
        "musica_fallo.wav":            s_musica_fallo,
        "musica_igualando.wav":        s_musica_igualando,
        # Preguntar a la IA.
        "ia_enviada.wav":              s_ia_enviada,
        "ia_respuesta.wav":            s_ia_respuesta,
        "ia_error.wav":                s_ia_error,
        "ia_analizando.wav":           s_ia_analizando,
        "ia_captura.wav":              s_ia_captura,
        "ia_cancelada.wav":            s_ia_cancelada,
        "ia_imagen_negra.wav":         s_ia_imagen_negra,
        # Atajos globales ocupados.
        "atajos_ocupados.wav":         s_atajos_ocupados,
        # Micrófono activado sin señal que entre.
        "microfono_sin_senal.wav":     s_microfono_sin_senal,
        # Pausa del directo de TikTok y su vuelta.
        "directo_pausado.wav":         s_directo_pausado,
        "directo_reanudado.wav":       s_directo_reanudado,
        # Búsqueda y cola de descargas.
        "busqueda_iniciada.wav":       s_busqueda_iniciada,
        "busqueda_resultados.wav":     s_busqueda_resultados,
        "busqueda_sin_resultados.wav": s_busqueda_sin_resultados,
        "busqueda_fallida.wav":        s_busqueda_fallida,
        "escucha_cargando.wav":        s_escucha_cargando,
        "escucha_fallida.wav":         s_escucha_fallida,
        "descarga_encolada.wav":       s_descarga_encolada,
        "descarga_procesando.wav":     s_descarga_procesando,
        "cola_descargas_terminada.wav": s_cola_descargas_terminada,
        "descarga_parcial.wav":        s_descarga_parcial,
    },
}

# Paneo estéreo por evento, en [-1, 1] (0 = centro). Muy sutil y solo donde
# ayuda a diferenciar; el resto va centrado. Compartido por todos los temas.
PANEO = {
    "nuevo_miembro.wav": 0.25,    # llega alguien → ligeramente a la derecha
    "enviado.wav":       0.20,    # acción saliente → derecha
    "comentario.wav":    0.20,
    "moderacion.wav":   -0.25,    # acción de moderación → izquierda
}


# ── Entrada ───────────────────────────────────────────────────────────────────

def generar_tema(tema: str, destino: Path | None = None,
                 sobreescribir: bool = False) -> int:
    sonidos = TEMAS[tema]
    destino = destino or (THEMES_DIR / tema)
    destino.mkdir(parents=True, exist_ok=True)
    n = 0
    for nombre, fn in sonidos.items():
        ruta = destino / nombre
        if ruta.exists() and not sobreescribir:
            print(f"  [saltar]  {nombre}  (ya existe)")
            continue
        _escribir_wav(ruta, fn(), pan=PANEO.get(nombre, 0.0))
        print(f"  [crear ]  {nombre:20s}  {ruta.stat().st_size:6d} bytes")
        n += 1
    return n


def main():
    import argparse
    ap = argparse.ArgumentParser(description="Genera los WAV de retroalimentación.")
    ap.add_argument("-f", "--forzar", action="store_true", help="Sobreescribir existentes")
    ap.add_argument("-t", "--tema", default="all",
                    help=f"Tema a generar: {', '.join(TEMAS)} o 'all' (por defecto)")
    ap.add_argument("-d", "--destino", default=None,
                    help="Carpeta de salida (por defecto sounds/themes/<tema>)")
    args = ap.parse_args()

    temas = list(TEMAS) if args.tema == "all" else [args.tema]
    if any(t not in TEMAS for t in temas):
        ap.error(f"tema desconocido. Opciones: {', '.join(TEMAS)}, all")

    total = 0
    for t in temas:
        destino = Path(args.destino) if args.destino else (THEMES_DIR / t)
        print(f"\n  Tema '{t}' -> {destino}")
        print("-" * 60)
        n = generar_tema(t, destino, sobreescribir=args.forzar)
        total += n
        print("-" * 60)
        print(f"  {n} creado(s). {len(TEMAS[t]) - n} saltado(s).")
    if not args.forzar and total < sum(len(TEMAS[t]) for t in temas):
        print("\n  Usa --forzar para regenerar los existentes.")
    print()


if __name__ == "__main__":
    main()
