# 🤖 ATOMUM: Sistema Multi-Agente Autónomo & Auditoría de Seguridad

🚀 **[Abrir ATOMUM — Centro de Control Autónomo en Streamlit](https://atomum-4q6wztkaf77phzygcghzbl.streamlit.app/)**

Plataforma modular de ingeniería de IA y ciberseguridad ofensiva/defensiva diseñada para ejecutar directivas técnicas, gestionar ciclos controlados de auto-mejora de código mediante Pull Requests en GitHub y realizar auditorías de red asíncronas desde un panel operativo en tiempo real.

```text
+-------------------------------------------------------+
|          ATOMUM: Centro de Control Autónomo           |
|              (Streamlit Operations UI)                |
+-----------+---------------+---------------+-----------+
            |               |               |
            v               v               v
    +-------+-------+ +-----+-------+ +-----+-------+
    |   Consola     | | Auto-Mejora | | PortScanner |
    |   Cognitiva   | | & GitHub PR | | & Audit UI  |
    +---------------+ +-------------+ +-------------+
```


## ⚙️ Componentes Clave (/core, /atomum & /security)

- [ ] core/engine.py: Núcleo de procesamiento de directivas. Valida comandos mediante guardarraíses constitucionales y conecta de forma directa con la API de Groq con un límite optimizado de hasta 8192 tokens de salida.

- [ ] core/http_client.py: Cliente HTTP asíncrono robusto construido sobre aiohttp y aiohttp-retry. Cuenta con un único TCPConnector para reutilización de sockets (keep-alive), reintentos con back-off exponencial ante fallos de red y control estricto de concurrencia mediante semáforos. 

- [ ] atomum/inference/ & runner.py: Capa de inferencia desacoplada (InferenceService / GroqInferenceClient) y orquestador autónomo (AutonomousRunner) con telemetría de consumo (usage y finish_reason), validación sintáctica por AST y creación automatizada de ramas y Pull Requests en GitHub.

- [ ] security/port_scanner/: Escáner asíncrono de puertos de alto rendimiento con resolución DNS previa, banner grabbing en doble pasada, análisis de riesgos y exportación multiformato (CSV, JSON, Word, PDF y HTML Interactivo con KPIs y acordeones).

## 🧬 Gobernanza Autónoma, Guardrails y Cuotas de Tokens

El ciclo de Auto-Mejora & GitHub PRs opera bajo supervisión humana (Human-in-the-Loop) y atraviesa cuatro barreras de seguridad obligatorias antes de publicar cualquier cambio:

1. Validación Sintáctica Estricta (AST): Ninguna propuesta generada por el modelo se aplica sin superar ast.parse() sin errores ni truncamientos.

2. Compuerta de Pruebas Automatizadas (pytest): Los cambios candidatos deben mantener en verde la suite de pruebas unitarias antes de habilitar la creación de rama o PR.

3. Ejecución Acotada de Comandos: Las operaciones del sistema están restringidas a listas blancas de comandos seguros y timeouts explícitos.

4. Gobernanza Humana en GitHub: El agente nunca realiza merge directo a main; toda modificación queda sujeta a revisión y aprobación manual mediante Pull Request.

Nota Operativa (TPM / Tier Gratuito): El módulo de auto-mejora se encuentra funcional y validado. En entornos que operan sobre niveles gratuitos de API con límites estrictos de Tokens por Minuto (TPM) (~8.000 TPM), se recomienda ejecutar objetivos acotados a funciones o métodos puntuales en lugar de reescrituras completas de archivos extensos, evitando truncamientos (finish_reason="length") o saturación de ventana. La capa de inferencia está lista para escalar sin cambios estructurales hacia tiers de mayor throughput o modelos dedicados.   

## ⚡ Stack Tecnológico

- [ ] Python 3.11+

- [ ] Streamlit (Interfaz gráfica de operaciones en tiempo real)

- [ ] Groq API SDK (Inferencia ultrarrápida con modelos optimizados)

- [ ] Aiohttp & Aiohttp-Retry (Gestión de red asíncrona de alto rendimiento)

- [ ] Pandas / PyPDF2 / Python-Docx (Procesamiento y exportación de informes)

- [ ] Pydantic (Validación de esquemas y tipos de datos)  


## 🗺️ Roadmap & Próximas Actualizaciones

- [ ] Correlación Offline de CVEs (cpe_database.json): Mapeo local ultraligero entre banners de servicio y vulnerabilidades/CVSS sin requerir bases de datos pesadas.

- [ ] Escaneo de Aplicaciones Web (DAST): Fuzzing asíncrono de directorios, detección de tecnologías web y auditoría de cabeceras HTTP/HTTPS (HSTS, CSP, X-Frame-Options).

- [ ] Mapeo Topológico de Red (CIDR): Barrido de hosts activos en rangos completos de subred (ej. 192.168.1.0/24) y graficado de nodos vivos previo al escaneo de puertos.  

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

