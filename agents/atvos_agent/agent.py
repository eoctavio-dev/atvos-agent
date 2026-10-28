from google.adk.agents import Agent

root_agent = Agent(
    name="atvos_agent",
    model="gemini-2.5-flash",
    description="Asistente para probar integracion con Google Cloud.",
    instruction=(
        "Responde de forma breve, clara y util. Ayuda al usuario a crear, "
        "probar y operar soluciones en Google Cloud. No inventes resultados "
        "de recursos o comandos que no hayas ejecutado."
    ),
)
