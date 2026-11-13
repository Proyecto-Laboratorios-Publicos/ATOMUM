# CONSTITUTION.md – ATOMUM Security & Quality Charter

## 1. Propósito
Definir un marco de trabajo obligatorio para la **revisión estática**, **hardening** y **cumplimiento** de las mejores prácticas de desarrollo seguro en todos los repositorios gestionados por ATOMUM.

## 2. Alcance
Aplica a **código Python**, scripts de infraestructura (Dockerfile, Terraform, Ansible) y a cualquier artefacto que sea versionado en el repositorio.

## 3. Principios Fundamentales
| # | Principio (OWASP‑Top‑10) | Acción obligatoria |
|---|--------------------------|--------------------|
| A1 | **Inyección** | Validar y parametrizar todas las entradas externas. Nunca concatenar strings para construir consultas SQL/NoSQL, comandos de shell o rutas de archivo. |
| A2 | **Autenticación rota** | Usar siempre bibliotecas probadas (`passlib`, `bcrypt`, `jwt` con firma RS256). No almacenar credenciales en texto plano. |
| A3 | **Exposición de datos sensibles** | Encriptar datos en reposo y en tránsito (AES‑GCM, TLS 1.2+). No loggear valores sensibles (password, tokens, claves). |
| A4 | **XML External Entity (XXE)** | Desactivar DTD y entidades externas en cualquier parser XML (`defusedxml`). |
| A5 | **Control de acceso roto** | Aplicar *principio de menor privilegio* en funciones y endpoints. |
| A6 | **Configuración insegura** | Mantener `DEBUG=False`, usar variables de entorno para secretos, validar configuraciones con `checkov`/`tfsec`. |
| A7 | **Cross‑Site Scripting (XSS)** | Escapar siempre la salida que se renderiza en HTML/JS. Utilizar plantillas seguras (`jinja2.autoescape=True`). |
| A8 | **Deserialización insegura** | Evitar `pickle`/`yaml.load` con fuentes no confiables. Preferir `json` o `yaml.safe_load`. |
| A9 | **Uso de componentes vulnerables** | Ejecutar `pip-audit` y `safety` en CI; bloquear versiones con CVE conocidas. |
| A10| **Registro y monitoreo insuficientes** | Emitir logs estructurados (JSON) con nivel `INFO`/`WARN`/`ERROR`. No incluir datos sensibles. |

## 4. Revisión de Código Fuente
1. **Pull‑Request Mandatory Checks**  
   - `pylint >= 2.17` con perfil `security`.  
   - `bandit` (severity ≥ MEDIUM) sin hallazgos críticos.  
   - `mypy --strict` – tipado total.  
   - `pytest` con cobertura mínima **90 %** y pruebas de *fuzzing* para entradas externas.  

2. **Checklist del Revisor**  
   - [ ] Todas las entradas externas están validadas (tipo, rango, regex).  
   - [ ] No existen concatenaciones de strings para comandos o consultas.  
   - [ ] Se usan context managers (`with`) para recursos críticos (archivos, sockets).  
   - [ ] Se manejan excepciones específicas; no se captura `Exception` genérico.  
   - [ ] Los secretos están referenciados vía `os.getenv` o `python-decouple`.  

## 5. Validación y Sanitización de Entradas
| Tipo de dato | Técnica recomendada |
|--------------|---------------------|
| **String**   | `re.fullmatch(pattern, value)` o `cerberus.Schema`. |
| **Entero**   | `int(value)` dentro de rangos explícitos (`0 <= value <= MAX`). |
| **Lista/Dict**| Validar con `pydantic.BaseModel` o `marshmallow`. |
| **Archivo**  | Verificar `os.path.isabs`, `os.path.realpath` y limitar a directorios permitidos (`/var/app/data`). |
| **JSON**     | `jsonschema.validate`. |

## 6. Gestión de Hashes y Verificación de Integridad
- Cada artefacto (script, Docker image, paquete) debe generar **SHA‑256** al momento de *commit*.  
- El archivo `hashes.txt` (raíz) contiene: `<sha256>  <relative_path>`.  
- CI verifica que el hash calculado coincida antes de aceptar el merge.

## 7. Auditoría de Logs Locales
- Logs escritos en **JSON Lines** (`.log.jsonl`).  
- Campos obligatorios: `timestamp`, `level`, `module`, `message`, `request_id`.  
- **No** incluir: `password`, `api_key`, `jwt`, `private_key`.  
- Rotación automática con `logrotate` (max 10 MiB, 7 días).  

## 8. Hardening de Infraestructura
- Docker: `USER nonroot`, `no-new-privileges:true`, `read-only:true` cuando sea posible.  
- Terraform: `terraform validate`, `terraform fmt`, `checkov` con política `CKV_AWS_20` (IAM least‑privilege).  
- CI/CD: runners con **sandbox** (Docker‑in‑Docker deshabilitado), secretos en **Vault** o **GitHub Secrets**.

## 9. Cumplimiento y Métricas
- Dashboard semanal (Grafana) con:  
  - % de PRs que pasan `bandit` sin hallazgos críticos.  
  - Número de vulnerabilidades abiertas (CVEs).  
  - Cobertura de pruebas.  

## 10. Responsabilidades
- **Desarrollador**: escribe código conforme a esta guía.  
- **Revisor**: ejecuta checklist y bloquea PRs que no cumplan.  
- **CI Engineer**: mantiene pipelines de análisis estático y auditoría de hashes.  

---  
*Esta Constitución es versión 2.0, fecha de emisión: 2026‑11‑13. Cualquier desviación debe ser aprobada por el Comité de Seguridad de ATOMUM.*  
