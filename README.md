# 🤖 ATOMUM: Sistema Multi-Agente Autónomo & Auditoría de Seguridad

🚀 **[Abrir ATOMUM — Centro de Control Autónomo en Streamlit](https://atomum-4q6wztkaf77phzygcghzbl.streamlit.app/)**

Plataforma modular de ingeniería de IA y ciberseguridad ofensiva/defensiva diseñada para ejecutar directivas técnicas, gestionar ciclos controlados de auto-mejora de código mediante Pull Requests en GitHub y realizar auditorías de red asíncronas desde un panel operativo en tiempo real.

```text
+-------------------------------------------------------+
|          ATOMUM: Centro de Control Autónomo           |
|              (Streamlit Operations UI)                |
+-----------+---------------+---------------+-----------+
|               |               |               |
+-------+-------+ +-----+-------+ +-----+-------+ +-----+-------+
|   Consola     | | Multi-Agente  | | Auto-Mejora | | PortScanner |
|   Cognitiva   | | Orquestación  | | & GitHub PR | | & Audit UI  |
+---------------+ +-------------+ +-------------+ +-------------+
```


## ⚙️ Componentes Clave (/core, /atomum, /autonomous_loop & /security)

- **core/governance.py & pr_guard.py:** Capa de gobernanza, control de alcance, `EmergencyStop`, aprobación humana obligatoria (*Human-in-the-Loop*) y registro de auditoría inmutable. Valida el impacto de las acciones y sella evidencia técnica.

- **autonomous_loop/github_pr_client.py:** Cliente especializado para interactuar con la API de GitHub mediante tokens cifrados, automatizando la creación segura de Pull Requests tras validaciones robustas.

- **atomum/inference/ & runner.py:** Orquestador multi-agente que conecta motores cognitivos y ejecuta tareas desacopladas, validando sintácticamente el código candidato mediante AST.

- **security/port_scanner/:** Escáner asíncrono de puertos de alto rendimiento con resolución DNS, banner grabbing y auditorías detalladas.

## 🧬 Gobernanza Autónoma y Aprobación Humana (Human-in-the-Loop)

Toda propuesta crítica o de alto impacto originada por los agentes autónomos atraviesa un workflow protegido e inmutable antes de impactar en el repositorio remoto:

1. **Validación Sintáctica (AST):** El sistema parsea el código candidato en búsqueda de errores o truncamientos mediante validación obligatoria.

2. **Evaluación de Gobernanza:** El `GovernanceController` clasifica el impacto de la acción y evalúa si la directiva requiere aprobación explícita.

3. **Compuerta de Revisión Humana:** En caso de requerir aprobación, se pausa la ejecución local y se requiere el visto bueno del supervisor humano a través de la interfaz de Streamlit antes de avanzar a la creación del PR.

4. **Despliegue Asíncrono y Auditoría:** Una vez aprobado, el `GitHubPRClient` publica el cambio y el sistema registra el outcome de manera imborrable en el log de eventos.

## 🧠 Orquestación Multi-Agente y Flujo Modular

El núcleo de ATOMUM desacopla el razonamiento de la ejecución mediante una arquitectura de agentes especializados:

- **Cognitive Planner:** Recibe la instrucción técnica del usuario y descompone el objetivo en un plan estructurado, validando la viabilidad y alcance de las acciones solicitadas.
  
- **Autonomous Runner:** Toma el plan generado y coordina la ejecución asíncrona a través de los servicios de inferencia y los módulos operativos, asegurando que cada paso cumpla con las guardrails de gobernanza antes de cualquier interacción con el repositorio o la red.
  

## ⚡ Stack Tecnológico

- Python 3.11+

- Streamlit (Interfaz gráfica de operaciones en tiempo real)

- Groq API SDK (Inferencia ultrarrápida con modelos optimizados)

- Aiohttp & Aiohttp-Retry (Gestión de red asíncrona de alto rendimiento)

- Pandas / PyPDF2 / Python-Docx (Procesamiento y exportación de informes)

- Pydantic (Validación de esquemas y tipos de datos)  


## 💾 Arquitectura de Memoria y Persistencia (Módulos /memory)

El sistema implementa un modelo de memoria híbrido y desacoplado para garantizar la trazabilidad, el contexto a largo plazo y la autoevaluación:

- ** memory/store.py (PersistentStore): ** Gestor central de transacciones que combina ** Redis ** (para caché rápida de estado) y ** PostgreSQL ** (para almacenamiento inmutable a largo plazo de registros de ejecución e históricos).

- ** memory/context_manager.py (ContextManager): ** Administrador de contexto del sistema, conectado directamente a la infraestructura de datos para registrar y recuperar eventos críticos, garantizando que el estado del agente sea persistente y robusto tras reinicios.

- ** memory/episodic/ & memory/semantic/: ** Estructuras dedicadas a almacenar eventos específicos y conocimientos estructurados del dominio (amenazas, políticas, activos), todos alineados con timezones en formato UTC estandarizado.


## 🗺️ Roadmap & Próximas Actualizaciones

- [ ] Correlación Offline de CVEs (cpe_database.json): Mapeo local ultraligero entre banners de servicio y vulnerabilidades/CVSS sin requerir bases de datos pesadas.

- [ ] Escaneo de Aplicaciones Web (DAST): Fuzzing asíncrono de directorios, detección de tecnologías web y auditoría de cabeceras HTTP/HTTPS (HSTS, CSP, X-Frame-Options).

- [ ] Mapeo Topológico de Red (CIDR): Barrido de hosts activos en rangos completos de subred (ej. 192.168.1.0/24) y graficado de nodos vivos previo al escaneo de puertos.  


```markdown
## 🛠️ Requisitos de Entorno y Ejecución

Para ejecutar el sistema localmente o en un entorno cloud (como Streamlit Cloud), asegúrate de configurar las siguientes variables de entorno:

- **GITHUB_TOKEN:** Token de acceso personal con permisos para crear Pull Requests.

- **GROQ_API_KEY:** Clave de API de Groq para el motor de inferencia.

Asegúrate también de que los archivos necesarios para los módulos visuales (como el escáner de puertos) estén correctamente ubicados en sus respectivas carpetas.
```

## 📂 Estructura del Proyecto
```text
ATOMUM/
├── atomum/            # Capa de inferencia desacoplada (GroqClient, InferenceService)
├── core/              # Motor principal, guardrails y cliente HTTP asíncrono
├── security/          # Escáner TCP asíncrono, análisis de riesgos y reportes
├── skills/            # Herramientas modulares de sistema y procesamiento de datos
├── tests/             # Suite de pruebas unitarias automatizadas (pytest)
├── app.py             # Interfaz principal de control en Streamlit
├── runner.py          # Orquestador autónomo y flujo de PRs en GitHub
└── cli.py             # Interfaz de ejecución por línea de comandos
```

## 🚀 Despliegue y Configuración

**1. Clonar el repositorio:**
   ```bash
   git clone https://github.com/Proyecto-Laboratorios-Publicos/ATOMUM.git
   cd ATOMUM
   ```

**2. Instalar dependencias:**

   ```bash
   pip install -r requirements.txt
   ```

**3. Configurar variables de entorno (o secrets en Streamlit):**
   ```env
   GROQ_API_KEY=tu_clave_de_api_aqui
   ATOMUM_LLM_MODEL=openai/gpt-oss-120b
   ```
**4. Ejecutar la interfaz de control:**
   ```bash
   streamlit run app.py
   ```

## 🛡️ Principios Operativos 

Seguridad Primero: Ninguna directiva evade los guardarraíses constitucionales. 

Resiliencia: Reintentos automáticos y manejo elegante de excepciones de red para evitar interrupciones en el bucle principal.   

---

**Versión actual:** `ATOMUM v2.0` · **Estado:** Producción / Auditoría Activa · **Licencia:** Apache-2.0
