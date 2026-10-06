"""Clasificador de intención de Kikos AI.

Diseño: puntuación ponderada con varias señales, solo librería estándar (~1 ms por mensaje,
coste cero). Cada intención suma puntos por:
  - vocabulario con raíces y sin tildes ("traduc", "resum"...), con pesos distintos
  - patrones de frase (verbo + objeto: "escribe ... correo", "arregla ... bug")
  - señales de estructura (bloques ```, trazas de error, operaciones 3*4, SQL, LaTeX)
  - contexto (archivos adjuntos y tipo de la respuesta anterior para mensajes de seguimiento)
Gana la intención con más puntos; si ninguna llega al mínimo se considera conversación o
"general". Devuelve también una confianza para que el router pueda ser prudente.

No es comprensión semántica real: entiende paráfrasis que comparten raíces o estructura, pero
no sinónimos que no estén en las listas. Si más adelante hiciera falta más precisión, el sitio
para añadir embeddings o un modelo pequeño es `analyze()`, solo para los casos de baja confianza.
"""
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Dict, List, Optional

# Orden de prioridad (también desempata): la primera gana si hay empate
INTENTS = (
    "coding", "data", "math", "translation", "summary", "documents", "writing",
    "creative", "reasoning", "technical", "research", "chat", "general",
)
_PRIORITY = {name: i for i, name in enumerate(INTENTS)}

MIN_SCORE = 2.5
SCORE_CAP = 10.0
FOLLOWUP_MAX_TOKENS = 7
# Intenciones cuya conversación suele continuar con mensajes cortos ("y en java?", "hazlo más corto")
_STICKY = {"coding", "data", "math", "translation", "summary", "writing", "creative", "documents"}


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFD", text.lower())
    return "".join(ch for ch in text if unicodedata.category(ch) != "Mn")


def _p(weight: float, pattern: str):
    return (re.compile(pattern), weight)


_LANGS = (
    "ingles|english|frances|french|aleman|german|italiano|italian|portugues|portuguese|espanol|spanish|"
    "catalan|chino|chinese|japones|japanese|ruso|russian|arabe|arabic|coreano|latin|gallego|euskera"
)

LEXICON: Dict[str, list] = {
    "coding": [
        _p(2.5, r"\b(python|java|javascript|typescript|golang|rust|kotlin|swift|php|ruby|bash|powershell|html|css|react|vue|angular|nodejs|fastapi|django|flask|spring|laravel|docker|kubernetes|git|github|linux|regex|npm|pip|venv|dockerfile|pytest|junit|nullpointerexception)\b"),
        _p(2.5, r"(?<!\w)(c#|c\+\+|node\.js)(?!\w)"),
        _p(1.8, r"\b(codigo|code|script|funcion|clase|metodo|variable|bucle|array|bug|bugs|compilar|compilador|debug\w*|depur\w*|refactor\w*|deploy\w*|despleg\w*|libreria|algoritmo|recursiv\w*|programa|programar|programacion|programador|commit|merge|socket|pipeline|dependencias)\b"),
        _p(0.9, r"\b(api|endpoint|backend|frontend|servidor|app|aplicacion|web|framework|componente|hook|callback|async|await|interfaz|herencia|getters|setters|list comprehension)\b"),
        _p(3.5, r"\b(escribe|crea|haz|genera|implementa|programa|desarrolla|necesito|quiero|dame|hazme)\b.{0,45}\b(funcion|clase|script|programa|api|endpoint|componente|aplicacion|bot|metodo|test|modulo|algoritmo|busqueda binaria)\b"),
        _p(3.5, r"\b(arregla|corrige|depura|soluciona|resuelve|refactoriza|optimiza|revisa)\w*\b.{0,45}\b(error|bug|fallo|excepcion|codigo|script|clase|funcion|bucle)\b"),
        _p(3.5, r"(traceback|exception|stack ?trace|segfault|syntaxerror|typeerror|referenceerror|modulenotfound\w*|nullpointer\w*|cannot read propert\w*|undefined is not|is not defined|no such file|command not found|permission denied|npm err|\berror:|se cae|se queda colgado)"),
        _p(2.0, r"\.(py|js|ts|tsx|jsx|java|cs|cpp|go|rs|php|rb|sh|yml|yaml|toml)\b"),
    ],
    "data": [
        _p(3.0, r"\b(sql|mysql|postgres\w*|sqlite|mongodb|nosql|csv|tsv|json|xml|excel|xlsx|dataframe|pandas|dataset|etl|esquema|schema|power ?bi|tabla dinamica|vlookup|buscarv)\b"),
        _p(1.8, r"\b(base de datos|bases de datos|tabla|tablas|columna|columnas|fila|filas|registros|consulta|query|normaliza\w*|formula|celdas?|hoja de calculo|campos)\b"),
        _p(4.0, r"\b(select\b.{1,60}\bfrom|insert into|group by|order by|inner join|left join|create table|where \w+ ?=)"),
        _p(3.5, r"\b(convierte|pasa|transforma|limpia|agrupa|filtra|ordena|extrae|normaliza|une|cruza)\w*\b.{0,40}\b(json|csv|tabla|datos|columna|excel|base de datos|dataframe)\b"),
    ],
    "math": [
        _p(3.5, r"\d+(?:[.,]\d+)?\s*[\+\*/x×÷\^]\s*\d+|\d\s*-\s*\d+\s*="),
        _p(3.0, r"\b(calcula\w*|cuanto es|cuanto da|cuanto vale|resuelve\w*|ecuacion\w*|integral\w*|derivada\w*|derivar|limite de|matriz|matrices|determinante|logaritmo|raiz cuadrada|porcentaje|probabilidad|estadistica|desviacion|factoriza\w*|polinomio|trigonometr\w*|seno|coseno|tangente|algebra|geometria|teorema|sumatorio|fraccion\w*|exponente|numero primo|mcd|mcm|simplifica|combinaciones|permutaciones|area de|volumen de|perimetro)\b"),
        _p(3.0, r"(\\frac|\\sum|\\int|\\sqrt|\bx\^\d|\bx2\b)"),
        _p(3.0, r"\b(que porcentaje|km/h|m/s|cuando se cruzan|cuanto tarda|cuantos\b.{0,25}\b(hay|quedan|sobran|caben))"),
        _p(1.0, r"\b[a-z]\s*=\s*-?\d"),
        _p(2.5, r"\bdemuestra\w*\b.{0,40}\b(que|teorema|irracional|primo|par|impar)\b"),
    ],
    "translation": [
        _p(5.0, r"\b(traduc\w*|traduzc\w*|translate|translation|traducir)\b"),
        _p(4.0, r"\b(como se dice|how do you say|como diria|que significa\b.{0,40}\ben\s+(" + _LANGS + r"))"),
        _p(4.0, r"\b(pasa|pon|ponlo|pasalo|pasame|dime|di|escribelo|vierte|conviertelo)\w*\b.{0,40}\b(al|en|a)\s+(" + _LANGS + r")\b"),
        _p(2.5, r"\b(al|en|a|to|into)\s+(" + _LANGS + r")\b"),
        _p(1.5, r"\b(idioma|nativo|fraseologia)\b"),
    ],
    "summary": [
        _p(4.5, r"\b(resum\w*|sintetiza\w*|sintesis|tl;?dr|abstract|puntos clave|ideas principales|en pocas palabras|en una frase|recapitula\w*|condensa\w*|version corta|version resumida|lo importante de|lo esencial de)\b"),
        _p(2.0, r"\b(en (tres|cinco|3|5|dos|2|pocas) (puntos|lineas|frases|palabras))\b"),
    ],
    "documents": [
        _p(2.5, r"\b(documento|pdf|contrato|clausula\w*|informe|paper|tesis|acta|factura|adjunto|adjunta|archivo adjunto|fichero|escritura|condiciones del|presupuesto)\b"),
        _p(4.0, r"\b(analiza|analizar|revisa|revisar|extrae|extraer|saca|lee|leer|evalua|compara)\w*\b.{0,45}\b(documento|texto|archivo|pdf|contrato|informe|articulo|fichero|adjunto|factura|importes|fechas|clausulas|condiciones)\b"),
        _p(4.0, r"\b(segun|en) (el|este) (documento|texto|archivo|contrato|informe|pdf)\b"),
    ],
    "writing": [
        _p(4.0, r"\b(redacta\w*|redaccion|reescribe\w*|parafrasea\w*|reformula\w*|ortografia|gramatica|proofread)\b"),
        _p(4.0, r"\b(escribe|escribeme|prepara|preparame|haz|hazme|necesito|quiero|ayudame a)\w*\b.{0,30}\b(correo|email|e-mail|carta|mensaje|articulo|post|publicacion|discurso|queja|reclamacion|comunicado|propuesta|ensayo|curriculum|biografia|presentacion|descripcion de producto|descripcion del producto|felicitacion|agradecimiento)\b"),
        _p(3.5, r"\b(mejora|corrige|revisa|pule|suaviza)\w*\b.{0,25}\b(texto|redaccion|escrito|mensaje|correo|parrafo|frase|tono)\b"),
        _p(3.0, r"\b(tono|suene|sonar|estilo)\b.{0,25}\b(formal|profesional|cercano|amable|elegante|serio|educado|mas)\b|\b(mas|con un) tono\b"),
        _p(2.0, r"\b(linkedin|carta de presentacion|asunto del correo|documentacion|readme|redactar)\b"),
    ],
    "creative": [
        _p(3.5, r"\b(cuento|relato|microrrelato|poema|poesia|cancion|letra de|novela|fabula|acrostico|haiku|soneto|chiste|adivinanza|guion)\b"),
        _p(3.0, r"\b(historia (de|sobre|con)|una historia|inventa\w*|inventate|imagina\w*|creativ\w*|lluvia de ideas|brainstorm|personaje|fantasia|ciencia ficcion|eslogan|slogan|rima\w*|aventura|juego de mesa|mundo ficticio)\b"),
        _p(3.5, r"\b(ideas?|nombres?|titulos?)\b.{0,12}\b(para|de)\b.{0,40}\b(cafeteria|negocio|marca|empresa|libro|juego|personaje|proyecto|banda|tienda|bebe|mascota|podcast|canal|restaurante|app)\b"),
        _p(2.0, r"\b(originales?|se me ocurre|desarrollala|desarrollalo)\b"),
    ],
    "reasoning": [
        _p(3.5, r"\b(razona\w*|paso a paso|justifica\w*|deduce\w*|infiere\w*|acertijo|paradoja|dilema|trade-?offs?|que pasaria si|que ocurriria si|implicaciones|toma de decisiones)\b"),
        _p(3.0, r"\b(pros y contras|estrategia|planifica\w*|escalabilidad|arquitectura|patrones? de diseno|monolito|microservicios|migrar|migracion|decidir|decido|merece la pena|me conviene|conviene)\b"),
        _p(3.0, r"\b(disena\w*|propon\w*|plantea\w*)\b.{0,25}\b(arquitectura|sistema|estrategia|plan|solucion)\b"),
        _p(2.5, r"\b(analiza\w*|evalua\w*|critica\w*|sopesa\w*)\b.{0,30}\b(pros|contras|ventajas|riesgos|opciones|decision|situacion|propuesta|oferta|ofertas)\b"),
        _p(2.0, r"\bpor que\b.{0,60}\b(no es|no siempre|realmente|contradictori\w*|mejor|peor)\b"),
        _p(1.5, r"\b(logica|logico|riesgo|beneficio|downtime|opciones?)\b"),
    ],
    "research": [
        _p(3.5, r"\b(investiga\w*|compara\w*|comparativa|ventajas y desventajas|alternativas? a|estado del arte|bibliografia|referencias|benchmark|analisis de mercado|tendencias)\b"),
        _p(3.0, r"\b(mejores?|mejor)\b.{0,12}\b(opciones|herramientas|librerias|frameworks|practicas|plataformas|hosting|alternativas)\b"),
        _p(3.0, r"\b(busca (informacion|datos)|que alternativas|alternativas existen|opciones (baratas|gratis|gratuitas)|recomiendame)\b"),
        _p(1.5, r"\b(fuentes|informacion sobre)\b"),
    ],
    "chat": [
        _p(4.5, r"^\W*(hola|holaa+|buenas|buenos dias|buenas tardes|buenas noches|hey|ey|ola|que tal|que onda|como estas|como andas|como va|gracias|muchas gracias|ok|okey|vale|perfecto|genial|adios|hasta luego|buenisimo|jaja\w*|jeje\w*|lol|si|no|me alegro|entendido|claro)\b"),
        _p(3.5, r"\b(como te llamas|quien eres|que puedes hacer|que modelo eres|cuentame algo|que tal tu dia|como va tu dia|estoy (aburrido|cansado|triste|contento|agobiado)|un poco aburrido|me alegro|que haces)\b"),
    ],
}


# "Explicación técnica" = petición de explicar (verbo) + vocabulario técnico. Por separado, ninguna basta.
_EXPLAIN = [
    _p(3.0, r"\b(explica\w*|explicame|como funciona\w*|como funcionan|que es (un|una|el|la)|que son|para que sirve|diferencia(s)? entre|en que consiste|introduccion a|que hace|por que se (usa|utiliza))\b"),
]
_TECH_VOCAB = [
    _p(1.4, r"\b(protocolo|algoritmo|redes?|servidor|kernel|tcp|udp|http\w*|dns|ssl|tls|cifrado|criptograf\w*|api|rest|graphql|indice|transaccion|concurrencia|hilo|hilos|proceso|memoria|cpu|gpu|compilador|sistema operativo|virtualizacion|contenedor|microservicios?|cache|latencia|ancho de banda|machine learning|aprendizaje automatico|red neuronal|embeddings?|transformers?|llm|blockchain|inteligencia artificial|firewall|vpn|hash|contrasenas?|recolector de basura|balanceo de carga|base de datos|sistema)\b"),
]


def _sum(patterns, norm: str) -> float:
    total = 0.0
    for regex, weight in patterns:
        hits = len(regex.findall(norm))
        if hits:
            total += weight * (1.0 + 0.25 * min(hits - 1, 3))
    return total


def _structural_bonus(raw: str, norm: str) -> Dict[str, float]:
    """Señales que no dependen de palabras concretas."""
    bonus: Dict[str, float] = {}

    def add(intent: str, value: float) -> None:
        bonus[intent] = bonus.get(intent, 0.0) + value

    if "```" in raw:
        add("coding", 4.0)
    if len(re.findall(r"^\s*(def |class |import |from \w+ import |function |const |let |var |public |private |#include|using |package |<\?php|<[a-z]+[^>]*>)", raw, re.M | re.I)) >= 1:
        add("coding", 3.0)
    if len(re.findall(r"=>|->|::|\(\)|\[\]|[{};]\s*$", raw, re.M)) >= 2:
        add("coding", 2.0)
    if len(re.findall(r"[=+\-*/^]", norm)) >= 2 and len(re.findall(r"\d", norm)) >= 2 and "?" in raw:
        add("math", 1.0)
    # Texto largo pegado junto con una petición: apunta a documentos/resumen
    if len(raw) > 700:
        add("documents", 1.0)
        add("summary", 0.5)
    return bonus


@dataclass
class Classification:
    task: str
    confidence: float
    scores: Dict[str, float] = field(default_factory=dict)
    reason: str = ""


class TaskClassifier:
    def analyze(self, prompt: str, previous_task: Optional[str] = None,
                has_attachments: bool = False) -> Classification:
        raw = prompt or ""
        norm = normalize(raw)
        tokens = re.findall(r"[a-z0-9#+]+", norm)

        scores: Dict[str, float] = {name: 0.0 for name in INTENTS}
        for intent, patterns in LEXICON.items():
            scores[intent] = _sum(patterns, norm)
        explain, vocab = _sum(_EXPLAIN, norm), _sum(_TECH_VOCAB, norm)
        if explain > 0 and vocab > 0:
            scores["technical"] = explain + min(vocab, 3.6) + 1.0
        for intent, value in _structural_bonus(raw, norm).items():
            scores[intent] += value

        # Pregunta larga con varias interrogantes y razonamiento: sube el razonamiento
        if scores["reasoning"] > 0 and (raw.count("?") >= 2 or len(raw) > 500):
            scores["reasoning"] += 1.0
        if has_attachments:
            scores["documents"] += 2.5

        for intent in scores:
            scores[intent] = min(scores[intent], SCORE_CAP)

        ranked = sorted(INTENTS, key=lambda name: (-scores[name], _PRIORITY[name]))
        top, second = ranked[0], ranked[1]
        top_score, second_score = scores[top], scores[second]

        if top_score < MIN_SCORE:
            # Sin señales claras: seguimiento del tema anterior, charla corta o pregunta general
            if previous_task in _STICKY and 0 < len(tokens) <= FOLLOWUP_MAX_TOKENS:
                return Classification(previous_task, 0.4, _top(scores), "seguimiento de la respuesta anterior")
            if len(tokens) <= 3:
                return Classification("chat", 0.5, _top(scores), "mensaje muy corto sin señales")
            return Classification("general", 0.35, _top(scores), "sin señales claras")

        confidence = top_score / (top_score + second_score + 1.0)
        return Classification(top, round(confidence, 2), _top(scores), "puntuación")

    def classify(self, prompt: str) -> str:
        """Compatibilidad con la versión anterior: solo devuelve la intención."""
        return self.analyze(prompt).task


def _top(scores: Dict[str, float], n: int = 3) -> Dict[str, float]:
    ranked = sorted(scores.items(), key=lambda kv: (-kv[1], _PRIORITY[kv[0]]))
    return {name: round(value, 1) for name, value in ranked[:n] if value > 0}
