# Mantenimiento del perfil de GitHub

Este repositorio contiene el README del perfil de **AdevTC**, sus recursos visuales y la actualización automática de sus métricas públicas.

## 1. Estructura del perfil

El archivo `README.md` está en la raíz y utiliza las imágenes de `assets/`. Mantén esa estructura al editar el contenido o añadir recursos. El resultado se muestra en **[github.com/AdevTC](https://github.com/AdevTC)**.

GitHub muestra un README de perfil cuando el repositorio es público, tiene exactamente el mismo nombre que el usuario y contiene un `README.md` no vacío en la raíz. [Documentación oficial](https://docs.github.com/en/account-and-profile/how-tos/profile-customization/managing-your-profile-readme).

## 2. Actualizar las métricas

Las tarjetas se actualizan al modificar el script o el workflow en `main`, cada lunes y cuando se solicita una ejecución manual. Los cambios del bot en `assets/` no vuelven a disparar el workflow.

Para actualizar manualmente:

1. Abre **Actions → Actualizar métricas del perfil**.
2. Ejecuta **Run workflow** sobre la rama por defecto.
3. Comprueba el resultado de la ejecución.

El archivo configura después una actualización semanal: **lunes a las 06:17 UTC** (07:17 en invierno y 08:17 en verano en Madrid). GitHub puede retrasar las ejecuciones programadas; no es un servicio de ejecución puntual garantizada. En repositorios públicos, las programaciones se desactivan tras 60 días sin actividad en el repositorio. [Documentación del evento schedule](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).

No necesitas crear un Personal Access Token. El workflow utiliza el `GITHUB_TOKEN` temporal que proporciona GitHub y solicita escritura de contenido solo al trabajo que guarda las tarjetas. Si las reglas de tu rama bloquean commits directos del bot, la actualización fallará y conservarás las imágenes anteriores. Puedes seguir usando la versión estática o adaptar el guardado al flujo de revisión de tu repositorio.

El workflow está limitado a `AdevTC/AdevTC` y a su rama por defecto. Los forks pueden mostrar los recursos estáticos incluidos.

## 3. Qué contienen las estadísticas

- **Repositorios públicos:** todos los repositorios públicos de tu usuario; incluye el propio repositorio de perfil y los forks públicos si los hubiera.
- **Lenguajes:** suma de bytes que devuelve la API de GitHub para cada lenguaje, excluyendo forks y el repositorio de perfil. Incluye repositorios archivados.
- **Fecha:** el día de la consulta, presentado con la zona horaria de Madrid.

La distribución de código no equivale a dominio técnico ni representa el trabajo que realizas en sistemas privados o corporativos. GitHub documenta los resultados del endpoint de lenguajes como bytes de código por lenguaje. [API oficial](https://docs.github.com/en/rest/repos/repos#list-repository-languages).

Si alguna consulta falla o devuelve datos incompletos, el script termina antes de sustituir los resultados existentes. Las tarjetas permanecen disponibles mientras esperas una actualización correcta.

## 4. Personalizarlo

| Cambio | Archivo |
| --- | --- |
| Puesto, experiencia, enlaces, proyectos y texto | `README.md` |
| Colores, nombre, cabecera, botones y etiquetas | `scripts/build_assets.py` |
| Formato o alcance de las estadísticas | `scripts/update_metrics.py` |
| Frecuencia de actualización | `.github/workflows/update-metrics.yml` |

Para regenerar los recursos de marca con Python 3.9 o posterior:

```bash
python3 scripts/build_assets.py
```

Para renovar manualmente las métricas:

```bash
python3 scripts/update_metrics.py --username AdevTC
```

En Windows, puedes utilizar `py` en lugar de `python3`. Ambos scripts utilizan la biblioteca estándar de Python. El script de métricas necesita acceso a internet y una base de zonas horarias disponible; Ubuntu en GitHub Actions ya la incluye. Si tu Python de Windows indica que falta la zona `Europe/Madrid`, puedes usar el workflow o instalar los datos con `py -m pip install tzdata`.

El script de métricas admite `GITHUB_TOKEN` como variable de entorno opcional para ampliar los límites de la API. No pongas un token dentro del archivo ni en el README.

## 5. Completar la coherencia del perfil

El README no modifica la bio lateral ni el campo Company de GitHub. En la consulta pública del 21 de octubre de 2026, esos campos todavía hacían referencia a tus estudios en Cesur.

**Bio propuesta:**

> SAP BTP & Integration Suite @ Alsea | Groovy, CAP & Node.js | Full Stack Developer | Madrid

**Company:** `Alsea`

**Website:** `https://adriantomascerda.vercel.app`

Como repositorios fijados, seleccionaría **Manchester-Piti**, **fantasya-app** y **2026-World-Cup-Simulator**. El portfolio puede seguir como enlace principal de tu perfil.

## 6. Archivos del repositorio

| Elemento | Para qué sirve |
| --- | --- |
| `README.md` | Perfil completo, con experiencia anterior y bloque en inglés desplegables. |
| `assets/` | SVG de marca, botones, stack y métricas; versiones clara, oscura y móvil donde corresponde. |
| `scripts/build_assets.py` | Fuente editable de los recursos visuales originales. |
| `scripts/update_metrics.py` | Generación de estadísticas desde la API pública de GitHub. |
| `.github/workflows/update-metrics.yml` | Actualización semanal, manual y al modificar el generador. |
| `docs/INSTALACION.md` | Esta guía. |

`docs/` contiene la documentación de mantenimiento y `scripts/build_assets.py` conserva la fuente editable del diseño.
