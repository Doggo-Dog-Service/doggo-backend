import asyncio
import json

import websockets

SERVICE_ID = 1

WEBSOCKET_URL = (
    f"ws://localhost:8000/ws/services/{SERVICE_ID}/"
)


# Percurso fictício
ROUTE = [
    (-26.304400, -48.848700),
    (-26.304405, -48.848710),
    (-26.304410, -48.848720),
    (-26.304420, -48.848740),
    (-26.304450, -48.848780),
    (-26.304500, -48.848830),
    (-26.304550, -48.848880),
]


async def simulate_walk():
    async with websockets.connect(
        WEBSOCKET_URL
    ) as websocket:

        print("Conectado ao WebSocket.")
        print("Iniciando corrida...\n")

        for index, (latitude, longitude) in enumerate(ROUTE):
            message = {
                "type": "location",
                "latitude": latitude,
                "longitude": longitude,
            }

            await websocket.send(
                json.dumps(message)
            )

            print(
                f"[{index + 1}] "
                f"Enviado: "
                f"{latitude}, {longitude}"
            )

            response = await websocket.recv()

            print(
                f"    Recebido: {response}\n"
            )

            await asyncio.sleep(2)


if __name__ == "__main__":
    asyncio.run(simulate_walk())
