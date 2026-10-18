"""Генератор BPMN 2.0 схемы пилота «Технотека.ИИ» (docs/pilot_process.bpmn).

Открывается в Camunda Modeler / demo.bpmn.io. Координаты (BPMN DI) задаются сеткой:
колонка → x, дорожка/ряд → y.

    python docs/make_bpmn.py
"""
from pathlib import Path
from xml.sax.saxutils import escape

OUT = Path(__file__).resolve().parent / "pilot_process.bpmn"

STEP = 150
X0 = 215
def X(c): return X0 + STEP * c

# дорожки: (id, название, y_top, высота)
LANES = [
    ("Lane_org", "Организация (МСП / НИИ)", 60, 290),
    ("Lane_sys", "Система Технотека.ИИ", 350, 170),
    ("Lane_mod", "Команда проекта (модератор)", 520, 290),
]
Y = {"top": 130, "main": 280, "sys": 435, "modA": 600, "modB": 735}
POOL_X, POOL_W = 120, X(17) + 80 - 120

SIZE = {"task": (120, 80), "gw": (50, 50), "ev": (36, 36)}
COLORS = {  # stroke, fill — по исполнителю
    "org": ("#b35c00", "#fff1e0"),
    "sys": ("#1f4e79", "#e6f0fa"),
    "mod": ("#5b3a99", "#efe9f8"),
}

# id: (тип BPMN, вид, колонка, ряд, текст, исполнитель)
E = {
    "s_start": ("startEvent", "ev", 0, "modA", "Организация согласилась на пилот", "mod"),
    "t_invite": ("userTask", "task", 1, "modA", "Создать приглашение и отправить ссылку", "mod"),
    "t_open": ("userTask", "task", 2, "main", "Открыть ссылку и начать карточку", "org"),
    "g_mode": ("exclusiveGateway", "gw", 3, "main", "Режим карточки?", "org"),
    "t_upload": ("userTask", "task", 4, "main", "Загрузить материалы (PDF, DOCX, PPTX)", "org"),
    "t_parse": ("serviceTask", "task", 5, "sys", "Извлечь текст из файлов", "sys"),
    "t_llm": ("serviceTask", "task", 6, "sys", "Заполнить поля моделью и проверить цитаты", "sys"),
    "g_ext": ("exclusiveGateway", "gw", 7, "sys", "Удалось заполнить?", "sys"),
    "t_manual": ("userTask", "task", 6, "top", "Заполнить поля вручную", "org"),
    "t_review": ("userTask", "task", 8, "main", "Проверить и дополнить поля", "org"),
    "g_join": ("exclusiveGateway", "gw", 9, "main", "", "org"),
    "t_submit": ("userTask", "task", 10, "main", "Отправить на модерацию", "org"),
    "t_validate": ("serviceTask", "task", 11, "sys", "Проверить обязательные поля и формат", "sys"),
    "g_valid": ("exclusiveGateway", "gw", 12, "sys", "Есть ошибки?", "sys"),
    "t_fix": ("userTask", "task", 12, "top", "Исправить отмеченные поля", "org"),
    "t_fixtime": ("serviceTask", "task", 13, "sys", "Зафиксировать время, статус «На модерации»", "sys"),
    "t_check": ("userTask", "task", 14, "modA", "Проверить карточку по чек-листу и материалам", "mod"),
    "g_ok": ("exclusiveGateway", "gw", 15, "modA", "Карточка корректна?", "mod"),
    "t_accept": ("userTask", "task", 16, "modA", "Принять карточку", "mod"),
    "e_accepted": ("endEvent", "ev", 17, "modA", "Карточка принята", "mod"),
    "t_return": ("userTask", "task", 16, "modB", "Вернуть с комментарием", "mod"),
    # отдельный поток: расчёт КПЭ по окончании окна пилота
    "s_window": ("startEvent", "ev", 0, "modB", "Окно пилота закрыто", "mod"),
    "t_export": ("userTask", "task", 1, "modB", "Выгрузить Excel и посчитать КПЭ", "mod"),
    "e_kpi": ("endEvent", "ev", 2, "modB", "КПЭ рассчитаны", "mod"),
}
TIMER = {"s_window"}


def box(eid):
    _, kind, c, r, *_ = E[eid]
    w, h = SIZE[kind]
    return X(c) - w // 2, Y[r] - h // 2, w, h


def P(eid, side, d=0):
    """Точка на стороне элемента: l/r/t/b, d — смещение вдоль стороны."""
    x, y, w, h = box(eid)
    cx, cy = x + w // 2, y + h // 2
    return {"l": (x, cy + d), "r": (x + w, cy + d), "t": (cx + d, y), "b": (cx + d, y + h)}[side]


Ysys_bottom = 520
# поток: (id, откуда, куда, подпись, точки)
F = [
    ("f1", "s_start", "t_invite", "", [P("s_start", "r"), P("t_invite", "l")]),
    ("f2", "t_invite", "t_open", "", [P("t_invite", "t"), (X(1), Y["main"]), P("t_open", "l")]),
    ("f3", "t_open", "g_mode", "", [P("t_open", "r"), P("g_mode", "l")]),
    ("f4", "g_mode", "t_upload", "с ИИ", [P("g_mode", "r"), P("t_upload", "l")]),
    ("f5", "g_mode", "t_manual", "вручную", [P("g_mode", "t"), (X(3), Y["top"]), P("t_manual", "l")]),
    ("f6", "t_upload", "t_parse", "", [P("t_upload", "r"), (X(5), Y["main"]), P("t_parse", "t")]),
    ("f7", "t_parse", "t_llm", "", [P("t_parse", "r"), P("t_llm", "l")]),
    ("f8", "t_llm", "g_ext", "", [P("t_llm", "r"), P("g_ext", "l")]),
    ("f9", "g_ext", "t_review", "да", [P("g_ext", "t"), (X(7), Y["main"]), P("t_review", "l")]),
    ("f10", "g_ext", "t_upload", "нет: другие файлы", [P("g_ext", "b"), (X(7), Ysys_bottom - 18),
                                                       (X(4), Ysys_bottom - 18), P("t_upload", "b")]),
    ("f11", "t_review", "g_join", "", [P("t_review", "r"), P("g_join", "l")]),
    ("f12", "t_manual", "g_join", "", [P("t_manual", "r"), (X(9), Y["top"]), P("g_join", "t")]),
    ("f13", "g_join", "t_submit", "", [P("g_join", "r"), P("t_submit", "l")]),
    ("f14", "t_submit", "t_validate", "", [P("t_submit", "r"), (X(11), Y["main"]), P("t_validate", "t")]),
    ("f15", "t_validate", "g_valid", "", [P("t_validate", "r"), P("g_valid", "l")]),
    ("f16", "g_valid", "t_fix", "да", [P("g_valid", "t"), P("t_fix", "b")]),
    ("f17", "t_fix", "t_submit", "", [P("t_fix", "l"), (X(10), Y["top"]), P("t_submit", "t")]),
    ("f18", "g_valid", "t_fixtime", "нет", [P("g_valid", "r"), P("t_fixtime", "l")]),
    ("f19", "t_fixtime", "t_check", "", [P("t_fixtime", "b"), (X(13), Y["modA"]), P("t_check", "l")]),
    ("f20", "t_check", "g_ok", "", [P("t_check", "r"), P("g_ok", "l")]),
    ("f21", "g_ok", "t_accept", "да", [P("g_ok", "r"), P("t_accept", "l")]),
    ("f22", "t_accept", "e_accepted", "", [P("t_accept", "r"), P("e_accepted", "l")]),
    ("f23", "g_ok", "t_return", "нет", [P("g_ok", "b"), (X(15), Y["modB"]), P("t_return", "l")]),
    ("f24", "t_return", "t_fix", "", [P("t_return", "b"), (X(16), 795), (X(12) + 45, 795), P("t_fix", "b", 45)]),
    ("f25", "s_window", "t_export", "", [P("s_window", "r"), P("t_export", "l")]),
    ("f26", "t_export", "e_kpi", "", [P("t_export", "r"), P("e_kpi", "l")]),
]

# аннотации: id, текст, x, y, w, h, к какому элементу
A = [
    ("a1", "Порядок двух карточек чередуем: половине организаций — сначала ИИ, половине — сначала вручную",
     X(2) - 40, 560, 300, 70, "t_invite"),
    ("a2", "Рядом с каждым полем — цитата из материалов. Метка «проверьте» — цитата не найдена в тексте",
     X(8) - 10, 395, 240, 80, "t_review"),
    ("a3", "КПЭ 1: время заполнения — от открытия карточки до первой отправки (журнал действий)",
     X(14) - 50, 395, 300, 70, "t_fixtime"),
    ("a4", "КПЭ 2: доля карточек, принятых с первого раза",
     X(14) - 55, 690, 170, 55, "g_ok"),
]


LABEL_AT = {"g_ext": "right", "g_ok": "above"}  # где стрелка уходит вниз — подпись в другом месте


def label_bounds(eid):
    """Подписи событий и шлюзов — под фигурой (или справа/сверху, см. LABEL_AT)."""
    x, y, w, h = box(eid)
    where = LABEL_AT.get(eid, "below")
    if where == "right":
        return x + w + 4, y + h - 8, 90, 30
    if where == "above":
        return x + w // 2 - 55, y - 34, 110, 28
    return x + w // 2 - 55, y + h + 6, 110, 40


FLOW_LABEL_AT = {"f10": (X(5) + 10, Ysys_bottom - 38)}


def flow_label(pts, text, fid=""):
    if fid in FLOW_LABEL_AT:
        x, y = FLOW_LABEL_AT[fid]
        return x, y, 7 * len(text), 18
    (x1, y1), (x2, y2) = pts[0], pts[1]
    w = max(28, 7 * len(text))
    if x1 == x2:  # первый отрезок вертикальный
        return x1 + 6, min(y1, y2) + abs(y2 - y1) // 2 - 10 if abs(y2 - y1) > 30 else y1 + 4, w, 18
    return min(x1, x2) + 6, y1 - 20, w, 18


def build() -> str:
    q = escape
    proc, di = [], []
    for eid, (typ, kind, c, r, name, who) in E.items():
        inc = [f for f in F if f[2] == eid]
        out = [f for f in F if f[1] == eid]
        inner = "".join(f"<bpmn:incoming>{f[0]}</bpmn:incoming>" for f in inc)
        inner += "".join(f"<bpmn:outgoing>{f[0]}</bpmn:outgoing>" for f in out)
        if eid in TIMER:
            inner += '<bpmn:timerEventDefinition id="td_window" />'
        proc.append(f'    <bpmn:{typ} id="{eid}" name="{q(name)}">{inner}</bpmn:{typ}>')
        x, y, w, h = box(eid)
        stroke, fill = COLORS[who]
        lab = ""
        if kind != "task" and name:
            lx, ly, lw, lh = label_bounds(eid)
            lab = f'<bpmndi:BPMNLabel><dc:Bounds x="{lx}" y="{ly}" width="{lw}" height="{lh}" /></bpmndi:BPMNLabel>'
        marker = ' isMarkerVisible="true"' if kind == "gw" else ""
        di.append(f'      <bpmndi:BPMNShape id="{eid}_di" bpmnElement="{eid}"{marker} bioc:stroke="{stroke}" bioc:fill="{fill}" '
                  f'color:border-color="{stroke}" color:background-color="{fill}">'
                  f'<dc:Bounds x="{x}" y="{y}" width="{w}" height="{h}" />{lab}</bpmndi:BPMNShape>')
    for fid, src, dst, name, pts in F:
        nm = f' name="{q(name)}"' if name else ""
        proc.append(f'    <bpmn:sequenceFlow id="{fid}"{nm} sourceRef="{src}" targetRef="{dst}" />')
        wps = "".join(f'<di:waypoint x="{x}" y="{y}" />' for x, y in pts)
        lab = ""
        if name:
            lx, ly, lw, lh = flow_label(pts, name, fid)
            lab = f'<bpmndi:BPMNLabel><dc:Bounds x="{lx}" y="{ly}" width="{lw}" height="{lh}" /></bpmndi:BPMNLabel>'
        di.append(f'      <bpmndi:BPMNEdge id="{fid}_di" bpmnElement="{fid}">{wps}{lab}</bpmndi:BPMNEdge>')
    for aid, text, x, y, w, h, target in A:
        proc.append(f'    <bpmn:textAnnotation id="{aid}"><bpmn:text>{q(text)}</bpmn:text></bpmn:textAnnotation>')
        proc.append(f'    <bpmn:association id="{aid}_as" sourceRef="{target}" targetRef="{aid}" />')
        di.append(f'      <bpmndi:BPMNShape id="{aid}_di" bpmnElement="{aid}"><dc:Bounds x="{x}" y="{y}" width="{w}" height="{h}" /></bpmndi:BPMNShape>')
        tx, ty, tw, th = box(target)
        cx, cy = tx + tw // 2, ty + th // 2
        ax = x if cx < x else (x + w if cx > x + w else cx)
        ay = y if cy < y else (y + h if cy > y + h else cy)
        sx = tx + tw if ax >= tx + tw else (tx if ax <= tx else cx)
        sy = ty + th if ay >= ty + th else (ty if ay <= ty else cy)
        di.append(f'      <bpmndi:BPMNEdge id="{aid}_as_di" bpmnElement="{aid}_as"><di:waypoint x="{sx}" y="{sy}" />'
                  f'<di:waypoint x="{ax}" y="{ay}" /></bpmndi:BPMNEdge>')

    lanes_xml, lanes_di = [], []
    for lid, lname, ly, lh in LANES:
        refs = "".join(f"<bpmn:flowNodeRef>{eid}</bpmn:flowNodeRef>" for eid, v in E.items()
                       if ly <= Y[v[3]] < ly + lh)
        lanes_xml.append(f'      <bpmn:lane id="{lid}" name="{q(lname)}">{refs}</bpmn:lane>')
        lanes_di.append(f'      <bpmndi:BPMNShape id="{lid}_di" bpmnElement="{lid}" isHorizontal="true">'
                        f'<dc:Bounds x="{POOL_X + 30}" y="{ly}" width="{POOL_W - 30}" height="{lh}" /></bpmndi:BPMNShape>')
    pool_y, pool_h = LANES[0][2], sum(l[3] for l in LANES)

    return f'''<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL"
  xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI"
  xmlns:dc="http://www.omg.org/spec/DD/20100524/DC"
  xmlns:di="http://www.omg.org/spec/DD/20100524/DI"
  xmlns:bioc="http://bpmn.io/schema/bpmn/biocolor/1.0"
  xmlns:color="http://www.omg.org/spec/BPMN/non-normative/color/1.0"
  id="Definitions_tehnoteka" targetNamespace="https://tehnoteka.example/bpmn"
  exporter="tehnoteka docs/make_bpmn.py" exporterVersion="1">
  <bpmn:collaboration id="Collab_pilot">
    <bpmn:participant id="Pool_pilot" name="Пилот Технотека.ИИ: заполнение карточки разработки" processRef="Process_pilot" />
  </bpmn:collaboration>
  <bpmn:process id="Process_pilot" name="Заполнение и модерация карточки" isExecutable="false">
    <bpmn:laneSet id="LaneSet_pilot">
{chr(10).join(lanes_xml)}
    </bpmn:laneSet>
{chr(10).join(proc)}
  </bpmn:process>
  <bpmndi:BPMNDiagram id="Diagram_pilot">
    <bpmndi:BPMNPlane id="Plane_pilot" bpmnElement="Collab_pilot">
      <bpmndi:BPMNShape id="Pool_pilot_di" bpmnElement="Pool_pilot" isHorizontal="true">
        <dc:Bounds x="{POOL_X}" y="{pool_y}" width="{POOL_W}" height="{pool_h}" />
      </bpmndi:BPMNShape>
{chr(10).join(lanes_di)}
{chr(10).join(di)}
    </bpmndi:BPMNPlane>
  </bpmndi:BPMNDiagram>
</bpmn:definitions>
'''


if __name__ == "__main__":
    OUT.write_text(build(), encoding="utf-8")
    print("готово:", OUT)
