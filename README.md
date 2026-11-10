# 🤖 ATOMUM: Centro de Control Autónomo

ATOMUM es un núcleo cognitivo autónomo y motor de orquestación de agentes diseñado con un enfoque modular, seguro y altamente escalable en Python. Su arquitectura combina filtrado constitucional de guardarraíses, gestión de memoria estructurada y procesamiento asíncrono de alto rendimiento conectado a modelos cognitivos avanzados mediante Groq.

---

## 🏗️ Arquitectura del Sistema

El ecosistema opera bajo una separación estricta de responsabilidades:

+-------------------+          +---------------------+
|  ATOMUM Engine    |  <--->   |  AsyncHttpClient    |
|  - Orquestación   |          |  - aiohttp.Session  |
|  - Guardarraíses  |          |  - Retry Exponencial|
+-------------------+          +---------------------+
^                               ^
|                               |
+-------v-------+               +-------v-------+
|  Guardrails   |               |   Groq SDK    |
|  (Seguridad)  |               | (Motor LLM)   |
+---------------+               +---------------+


### Componentes Clave (`/core`)
* **`engine.py`**: Núcleo de procesamiento de directivas. Valida comandos mediante guardarraíses constitucionales y conecta de forma directa con la API de Groq con un límite optimizado de hasta `8192` tokens de salida.
* **`http_client.py`**: Cliente HTTP asíncrono robusto construido sobre `aiohttp` y `aiohttp-retry`. Cuenta con un único `TCPConnector` para reutilización de sockets (*keep-alive*), reintentos con back-off exponencial ante fallos de red y control estricto de concurrencia mediante semáforos.
* **`guardrails.py`**: Capa de seguridad y filtrado estricto que evalúa y previene patrones de ejecución destructivos antes de procesar cualquier instrucción.

---

## ⚡ Stack Tecnológico

* **Python 3.11+**
* **Streamlit** (Interfaz gráfica de operaciones en tiempo real)
* **Groq API SDK** (Inferencia ultrarrápida con modelos optimizados como `openai/gpt-oss-120b`)
* **Aiohttp & Aiohttp-Retry** (Gestión de red asíncrona de alto rendimiento)
* **Pydantic** (Validación de esquemas y tipos de datos)

---

## 🚀 Despliegue y Configuración

1. **Clonar el repositorio:**
   ```bash
   git clone [https://github.com/Proyecto-Laboratorios-Publicos/ATOMUM.git](https://github.com/Proyecto-Laboratorios-Publicos/ATOMUM.git)
   cd ATOMUM
Instalar dependencias:

Bash
pip install -r requirements.txt
Configurar variables de entorno (o secrets en Streamlit):

Fragmento de código
GROQ_API_KEY=tu_clave_de_api_aqui
ATOMUM_LLM_MODEL=openai/gpt-oss-120b
Ejecutar la interfaz de control:

Bash
streamlit run app.py
🛡️ Principios Operativos
Seguridad Primero: Ninguna directiva bypasses los guardarraíses constitucionales.

Resiliencia: Reintentos automáticos y manejo elegante de excepciones de red para evitar interrupciones en el bucle principal.

Optimización I/O: Concurrencia controlada para maximizar el throughput sin saturar recursos locales ni remotos.

🧬 ATOMUM Core v1.0 | Operativo y Sincronizado
