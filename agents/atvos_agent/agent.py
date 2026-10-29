from google.adk.agents import Agent, SequentialAgent

MODEL = "gemini-2.5-flash"

campaign_prompt_agent = Agent(
    name="campaign_prompt_agent",
    model=MODEL,
    description="Crea el prompt maestro para una campana interna de Atvos.",
    instruction="""
A partir de la solicitud del usuario, genera un prompt maestro listo para otro agente.
Incluye: objetivo de comunicacion, publico interno, mensaje central, tono,
canales autorizados, datos sensibles, requisitos de compliance, aprobadores,
restricciones legales y metricas de seguimiento.

Si falta informacion esencial, solicitala antes de generar el prompt.
No inventes requisitos de la organizacion ni politicas no proporcionadas.
Devuelve un prompt completo, claro y directamente reutilizable.
""".strip(),
    output_key="campaign_prompt",
)

campaign_description_agent = Agent(
    name="campaign_description_agent",
    model=MODEL,
    description="Convierte el prompt maestro en una descripcion detallada de campana.",
    instruction="""
Usa el prompt maestro guardado en el estado como {campaign_prompt} y crea la
descripcion detallada de la campana interna de Atvos.

La salida debe contener:
1. Resumen ejecutivo.
2. Objetivo y resultado esperado.
3. Publicos y segmentacion.
4. Mensaje clave y argumentos aprobados.
5. Tono, canales, formato y calendario de diffusion.
6. Controles de compliance, privacidad, anti-spam y revision legal.
7. Flujo de aprobacion y responsables sugeridos.
8. Plan de ejecucion por etapas.
9. KPI, medicion y ventana de seguimiento.
10. Riesgos, mitigaciones y lista de comprobacion final.

No afirmes aprobacion legal, ni inventes datos, personas, normas o canales.
Marca como pendiente cualquier dato necesario que falte.
""".strip(),
    output_key="campaign_description",
)

campaign_orchestrator = SequentialAgent(
    name="atvos_campaign_orchestrator",
    description=(
        "Orquesta la generacion y descripcion detallada de campanas internas "
        "de Atvos con foco en compliance y diffusion."
    ),
    sub_agents=[campaign_prompt_agent, campaign_description_agent],
)

root_agent = campaign_orchestrator
