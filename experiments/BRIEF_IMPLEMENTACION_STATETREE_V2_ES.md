# Brief de implementación — StateTree v2

**Fecha:** 27 de agosto de 2026  
**Objetivo:** corregir el colapso prematuro de la búsqueda verificada y aprovechar el presupuesto disponible sin violar las restricciones del take-home.

## 1. Resultado esperado

Construir una segunda versión de `StateTree` que:

- conserve y reintente estados Lean verificables en lugar de descartarlos después de una sola expansión;
- utilice los diagnósticos exactos de Lean para reparar acciones fallidas;
- pruebe directamente las sugerencias de búsqueda local de Mathlib;
- mantenga ramas de descomposición aunque aumenten temporalmente el número de objetivos;
- pueda resolver, de forma secuencial y genérica, archivos con varios teoremas o huecos;
- preserve el barrido determinista y el agente de reparación como respaldo seguro;
- respete los límites de USD 1 y ocho horas por problema.

No debe incorporarse ninguna regla basada en el identificador o la categoría matemática de un problema.

## 2. Diagnóstico principal

La arquitectura de verificación funciona, pero la política de búsqueda actual elimina demasiado pronto sus propios estados útiles.

En la implementación existente:

1. Un nodo se extrae de la frontera, se expande una sola vez y no vuelve a insertarse.
2. Las acciones inválidas y sus errores de Lean se descartan.
3. `node.tried` se actualiza después de generar el único prompt que podría utilizarlo. Por ello, la lista de acciones intentadas casi nunca llega al modelo.
4. Con Q y G activos, el límite de 14 llamadas permite expandir aproximadamente siete estados.
5. La puntuación favorece pocos objetivos y puede podar una descomposición correcta que produzca varios subobjetivos más sencillos.
6. La búsqueda local utiliza solamente `apply?`; todavía no explota plenamente `exact?`, `simp?`, `aesop?` ni la reparación guiada por errores.
7. Los desafíos con varios teoremas, como `p09_imo1964`, no entran en el árbol.

Por tanto, los cero cierres nativos de StateTree todavía no demuestran un límite real de capacidad de Q y G.

## 3. Restricciones invariantes

La implementación debe mantener estrictamente estas condiciones:

- modelos permitidos: únicamente Q (`qwen/qwen3.5-flash-02-23`) y G (`openai/gpt-oss-120b`);
- mismo mecanismo para todos los problemas;
- Lean y Mathlib como únicos verificadores y herramientas de ejecución;
- sin web, Loogle, LeanSearch, `#leansearch` ni servicios externos;
- no modificar nombres ni enunciados de teoremas;
- ningún archivo final puede contener `sorry`, `admit`, axiomas nuevos o instrumentación;
- aceptación final mediante el camino estricto existente y la comprobación de integridad;
- máximo de USD 1 y ocho horas por problema;
- ejecución secuencial compatible con dos CPU, 14 GB de RAM y un único worker Lean.

## 4. Prioridad P0 — Reintentos y retroceso reales

### 4.1 Estado adicional por nodo

Ampliar `Node` con información equivalente a:

```python
rounds: int
failed_actions: list[FailedAction]
valid_children: int
root_branch: str
last_progress_round: int
```

Cada acción fallida debe conservar:

```python
action: str
diagnostic: str
timed_out: bool
source_model: str
```

Los diagnósticos deben truncarse de forma determinista para evitar prompts excesivos.

### 4.2 Ciclo de expansión requerido

Para cada estado:

```text
1. Ejecutar la cartera Lean barata.
2. Probar directamente las sugerencias concretas obtenidas.
3. Pedir a G un lote de acciones nuevas.
4. Verificar todas las acciones con Lean.
5. Si no hay progreso, entregar a Q las mejores acciones fallidas y sus errores.
6. Verificar las reparaciones de Q.
7. Si todavía no hay hijos nuevos y quedan rondas, reinsertar el nodo.
8. Retirar el nodo solamente al agotar su cuota de rondas.
```

El nodo padre debe conservarse al menos una ronda adicional cuando un hijo válido aumente el número de objetivos. Ese aumento puede ser una descomposición matemática legítima.

### 4.3 Nueva configuración

Agregar:

```text
ST_STATE_ROUNDS=3
ST_DIAGNOSTIC_LIMIT=2000
ST_REPAIR_ACTIONS_PER_CALL=4
```

Todos los valores deben tener límites seguros mediante las funciones de configuración existentes.

### 4.4 Criterios de aceptación de P0

- Un nodo sin hijos válidos vuelve a aparecer en la frontera mientras conserve rondas.
- El segundo prompt del mismo nodo incluye acciones ya intentadas.
- Los errores exactos de Lean aparecen en el prompt de reparación.
- La misma acción no se ejecuta dos veces en el mismo estado.
- Los nodos agotados se retiran de manera determinista.
- El límite global de llamadas y comprobaciones continúa respetándose.
- Ningún contenido de prueba interno puede llegar a la solución final sin la verificación estricta.

## 5. Prioridad P0 — Política de frontera

No conservar únicamente los nodos con menos objetivos. Utilizar una selección estratificada o de Pareto.

En cada poda de la frontera deben preservarse, cuando existan:

1. el estado con menos objetivos;
2. el estado verificado más profundo;
3. una rama estructural que haya aumentado objetivos;
4. un representante de cada rama raíz activa;
5. los mejores estados restantes según una puntuación determinista.

La puntuación nunca determina corrección. Lean sigue siendo la única autoridad.

### Criterios de aceptación

- Un hijo que pasa de un objetivo difícil a dos subobjetivos no se elimina automáticamente.
- Ninguna rama raíz monopoliza toda la frontera si existen alternativas válidas.
- La poda respeta exactamente `ST_BEAM`.
- El orden es reproducible a igualdad de entradas y respuestas.

## 6. Prioridad P1 — Cartera local de Lean

Ejecutar una secuencia universal y acotada en cada estado nuevo:

1. finalizadores directos baratos con timeout corto;
2. `exact?`;
3. `simp?`;
4. `aesop?`;
5. `apply?` solamente cuando las alternativas baratas no produzcan progreso, porque puede ser costosa.

Las sugerencias `Try this:` deben seguir este camino:

```text
sugerencia de Lean
→ acción candidata
→ comprobación como hijo
→ estado verificado o descarte
```

No deben utilizarse solamente como texto decorativo dentro del prompt.

Guardar los resultados en caché por:

```text
(hash del estado, tipo de consulta, entorno Mathlib)
```

### Verificación de lemas propuestos por el modelo

Cuando un modelo proponga nombres de lemas, permitir una verificación local y agrupada con `#check`. Solo los nombres confirmados y sus tipos exactos deben volver al generador de acciones.

### Criterios de aceptación

- Cada sugerencia local puede identificarse por su herramienta de origen.
- Se registra si produjo error, timeout, estado repetido, estado nuevo o cierre.
- Las sugerencias se verifican antes de agregarse a la frontera.
- Las consultas repetidas al mismo estado utilizan la caché.
- Cada herramienta tiene timeout y límite de resultados independientes.

## 7. Prioridad P1 — Soporte universal para varios teoremas

Implementar resolución secuencial de huecos:

```text
1. Detectar todos los cuerpos incompletos.
2. Seleccionar el primer hueco no resuelto.
3. Construir un probe aislado que no confunda los `sorry` posteriores con el estado actual.
4. Resolver y verificar estrictamente el hueco seleccionado.
5. Congelar la prueba verificada en el archivo de trabajo.
6. Continuar con el siguiente hueco.
7. Reconstruir el archivo completo sin modificar declaraciones.
8. Ejecutar integridad y aceptación estricta sobre el archivo completo.
```

Los teoremas resueltos anteriormente deben estar disponibles para los posteriores.

No crear una excepción para `p09_imo1964`; el soporte debe funcionar para cualquier archivo con varios huecos compatibles.

### Pruebas mínimas

- Dos teoremas independientes.
- El segundo teorema utiliza el primero.
- El primer hueco se resuelve y el segundo falla: no devolver un archivo parcialmente aceptado.
- Un archivo con un solo teorema conserva el comportamiento anterior.
- Un archivo que no puede analizarse utiliza el fallback existente.
- La reconstrucción mantiene exactamente nombres y enunciados.

## 8. Uso recomendado de Q y G

En el agente práctico:

- G genera las acciones iniciales de cada estado.
- Q repara acciones rechazadas utilizando los errores exactos de Lean.
- Ambos generan propuestas independientes solamente después de estancamiento repetido.

Para evaluar si la diversidad de modelos aporta valor, comparar con el mismo presupuesto:

- `ST-GG`: dos lotes independientes de G;
- `ST-GQ`: un lote de G y uno de Q.

No atribuir una mejora a la heterogeneidad si `ST-GQ` no supera a `ST-GG` con llamadas y comprobaciones equivalentes.

## 9. Configuración para el primer experimento ampliado

Después de validar P0 con presupuesto equivalente a v1, utilizar:

```text
ST_BEAM=8
ST_MAX_DEPTH=24
ST_MAX_MODEL_CALLS=48
ST_MAX_LEAN_CHECKS=240
ST_ACTIONS_PER_CALL=6
ST_PREMISE_MAX_DEPTH=12
ST_STATE_ROUNDS=3
```

Preservar los límites de tiempo individuales existentes. Una acción novedosa que agote un timeout corto puede recibir un único reintento más largo; una acción repetida no.

## 10. Instrumentación obligatoria

Agregar por problema y por etapa:

- acciones solicitadas y recibidas por modelo;
- acciones extraídas correctamente del JSON;
- acciones filtradas antes de Lean;
- errores, timeouts y acciones Lean-válidas;
- estados nuevos y estados duplicados;
- hijos provenientes de `exact?`, `simp?`, `aesop?` y `apply?`;
- objetivos cerrados;
- rondas utilizadas por cada estado;
- máximo de profundidad;
- distribución de cantidad de objetivos;
- llamadas Q/G;
- comprobaciones Lean;
- tiempo Lean p50/p90;
- latencia por modelo;
- motivo de parada;
- fuente de cada acción de una prueba ganadora.

La profundidad aislada no debe presentarse como evidencia de cercanía a una solución. Las señales fuertes son subobjetivos cerrados, lemas intermedios no triviales utilizados y aceptación final.

## 11. Plan experimental

### Fase A — Pruebas mecánicas

1. Probar reinserción y agotamiento de nodos con servicios simulados.
2. Confirmar que los diagnósticos llegan a la reparación.
3. Probar deduplicación de acciones y estados.
4. Probar la frontera estratificada.
5. Probar archivos con cero, uno y varios objetivos.
6. Probar archivos con uno y varios teoremas.
7. Confirmar que el camino final rechaza cualquier `sorry` interno.

### Fase B — Comparación causal

Comparar primero con 14 llamadas:

| Brazo | Reintentos | Diagnósticos | Presupuesto |
|---|---:|---:|---:|
| StateTree v1 | no | no | 14 llamadas |
| StateTree v2 | sí | sí | 14 llamadas |

Objetivo: demostrar que la política corregida mejora la producción de estados nuevos sin depender de más cómputo.

### Fase C — Escalado

Solo si v2 mejora la eficiencia, ejecutar la configuración de 48 llamadas. El algoritmo debe ser idéntico para todos los problemas, aunque durante el desarrollo puedan repetirse solamente los artefactos actualmente fallidos para ahorrar tiempo.

### Fase D — Diversidad de modelos

Comparar `ST-GG` con `ST-GQ` usando el mismo número total de llamadas, tokens y comprobaciones Lean.

## 12. Criterios de continuidad y abandono

### StateTree v2 continúa si cumple al menos una condición

- consigue una nueva prueba aceptada;
- incrementa claramente los estados nuevos por llamada;
- alcanza trayectorias verificadas más profundas que cierran subobjetivos reales;
- reduce significativamente la tasa de acciones inválidas mediante reparación;
- habilita progreso verificable en `p09` después del soporte multi-teorema.

### StateTree v2 se congela o abandona si

- después de tres repeticiones no mejora estados nuevos por llamada;
- el aumento de profundidad es puramente administrativo y no cierra objetivos;
- los reintentos repiten los mismos errores;
- el último cuarto del presupuesto no produce estados nuevos, objetivos cerrados ni artefactos verificables útiles.

### Herramienta local individual se elimina si

- su p90 de tiempo es elevado;
- menos de aproximadamente el 10 % de sus sugerencias produce hijos nuevos;
- nunca participa en una trayectoria útil.

## 13. Fase posterior opcional — Intercambio de lemas verificados

No implementar esta fase antes de completar P0 y P1.

Activarla solamente cuando el árbol alcance estados relevantes pero se estanque:

1. G propone como máximo dos afirmaciones intermedias exactas y explica su uso.
2. Q intenta formalizar sus pruebas.
3. Lean verifica cada lema de manera aislada.
4. Solo los lemas aceptados entran en el contexto compartido.
5. Un lema se elimina si no produce un nuevo estado relacionado con el objetivo.

Abandonar esta fase si varias activaciones producen únicamente lemas triviales o nunca utilizados.

## 14. Evaluación honesta de los problemas persistentes

- **`p09_imo1964`:** probablemente alcanzable, pero StateTree todavía no lo ha probado debido al bypass de múltiples teoremas.
- **`rmo_2000_2`:** incierto; merece una búsqueda más profunda con reparación porque probablemente requiere una cadena de desigualdades o factorizaciones verificadas.
- **`rmo_2000_3`:** es el candidato más probable a representar una limitación real por la combinación de matemática no trivial y formalización delicada con `Finset`.

No declarar un límite de capacidad basándose solamente en profundidad o en el fracaso de la v1.

## 15. Arquitectura final segura

```text
desafío inmutable
→ comprobación de integridad
→ barrido determinista
→ propuesta y reparación corta de archivo completo
→ StateTree v2 con reintentos y búsqueda local
→ fallback al mejor candidato verificado
→ reconstrucción sin instrumentación
→ comprobación estricta de Lean
→ integridad del enunciado
→ comparador privado
```

StateTree nunca debe reducir el piso obtenido por el barrido y la reparación existentes.

## 16. Cronograma recomendado

### 27 de agosto

- implementar reintentos por estado;
- conservar diagnósticos;
- corregir la política de frontera;
- agregar pruebas unitarias básicas.

### 28 de agosto

- implementar soporte multi-teorema;
- ampliar la cartera local de Lean;
- ejecutar la comparación v1/v2 con 14 llamadas.

### 29 de agosto

- si v2 mejora, ejecutar el presupuesto de 48 llamadas;
- comparar `ST-GG` y `ST-GQ` si queda tiempo;
- congelar la configuración final;
- repetir el brazo elegido para medir variabilidad.

### 30 de agosto

- prueba final del comparador;
- comprobación de integridad y ausencia de constructos prohibidos;
- terminar el informe y entregar.

## 17. Decisión de entrega

Si la versión corregida no obtiene una prueba nueva, la entrega defendible es:

```text
barrido determinista
→ ciclo corto y robusto de propuesta/reparación
→ StateTree v2 como etapa adicional segura
→ mejor candidato estrictamente verificado
```

El informe debe distinguir claramente:

- progreso local verificado;
- eficiencia de generación de hijos;
- cierre de subobjetivos;
- pruebas finalmente aceptadas.

Los resultados actuales justifican corregir la política de búsqueda antes de concluir que Q y G han alcanzado un techo definitivo.
