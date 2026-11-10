# 🧬 ATOMUM (Autonomous Modular Entity)

> *"Una entidad autónoma modular diseñada para razonar, ejecutar operaciones seguras y expandir sus propias capacidades."*

---

## 🏛️ Arquitectura del Organismo

ATOMUM está estructurado de forma modular para separar sus leyes éticas, su núcleo de razonamiento, su memoria y sus extremidades operativas:

```text
ATOMUM/
│
├── core/
│   ├── engine.py         # Núcleo de razonamiento y validación
│   └── guardrails.py     # Filtros éticos y de seguridad (Constitución)
│
├── memory/
│   └── context_manager.py # Registro dinámico de eventos en JSON
│
├── skills/
│   ├── git_ops.py        # Extremidad de control de versiones y Git
│   ├── system_tools.py   # Extremidad de terminal y comandos seguros
│   ├── data_tools.py     # Extremidad de análisis de datos estructurados
│   ├── file_tools.py     # Extremidad de lectura y escritura de archivos
│   └── web_tools.py      # Extremidad de red y consultas HTTP
│
├── CONSTITUTION.md       # Leyes éticas supremas del sistema
├── tasks.json            # Cola de tareas dinámica y persistente
├── autonomous_loop.py    # Bucle autónomo con auto-generación de directivas
├── runner.py             # Script maestro de integración inicial
├── main.py               # Punto de entrada y validación constitucional
└── requirements.txt      # Dependencias del proyecto

🚀 Instalación y Puesta en Marcha

Clona este repositorio en tu estación de trabajo local y prepárate para inicializar el organismo:

Bash
# 1. Clonar el repositorio
git clone [https://github.com/Proyecto-Laboratorios-Publicos/ATOMUM.git](https://github.com/Proyecto-Laboratorios-Publicos/ATOMUM.git)
cd ATOMUM

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Ejecutar el bucle autónomo
python autonomous_loop.py

🛡️ Principios de Seguridad

Cualquier directiva que intente vulnerar los guardarraíses éticos establecidos en la CONSTITUTION.md (como comandos destructivos o accesos no autorizados) es interceptada y neutralizada automáticamente por el núcleo antes de tener contacto con el sistema operativo.

Creado y dirigido por 7073N.
