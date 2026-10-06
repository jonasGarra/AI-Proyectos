# 🧠 Kikos AI — Enterprise Orchestrator

Kikos AI es un orquestador de Inteligencia Artificial diseñado para ejecutarse con un consumo mínimo de recursos en hardware limitado (optimizado para un servidor **PS4 con Linux**). Actúa como cerebro central, gestionando contexto, aislamiento de proyectos y enrutamiento inteligente hacia pasarelas multi-modelo (OmniRoute).

## 🏗️ Arquitectura del Sistema
- **Core Orchestrator (Local):** Construido con FastAPI y SQLite (modo WAL). Gestiona el aislamiento estricto entre proyectos, subproyectos y conversaciones.
- **Smart Router:** Clasificador semántico ultraligero que evalúa la intención del usuario y decide el mejor combo de modelo (coding, reasoning, fast) con latencia cero.
- **Memoria Aislada:** Inyección de contexto dinámica y segura. Un subproyecto jamás contamina a otro.
- **Frontend PWA:** Interfaz en Vanilla JS/CSS con tema oscuro/granate, libre de dependencias pesadas de Node.js.

## 🚀 Estado del Proyecto
Actualmente en **Fase 0 (Integración Base)**. La comunicación con la pasarela de LLMs es síncrona, con autenticación JWT integrada.
*Próxima actualización (Fase 1):* Implementación de Server-Sent Events (SSE) para Streaming Response y renderizado seguro de Markdown.

## 📦 Puesta en Marcha
1. Clonar el repositorio y configurar el entorno virtual:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
