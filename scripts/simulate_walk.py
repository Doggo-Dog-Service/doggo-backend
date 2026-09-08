import asyncio
import json

import websockets

WS_URL = "ws://127.0.0.1:8000"
SERVICE_ID = 1

CLIENT_TOKEN = ""
PROVIDER_TOKEN = ""


LOCATIONS = [
    (-26.304400, -48.848700),
    (-26.304450, -48.848650),
    (-26.304500, -48.848600),
    (-26.304550, -48.848550),
    (-26.304600, -48.848500),
    (-26.304650, -48.848450),
    (-26.304700, -48.848400),
]


def get_url(token):
    return (
        f"{WS_URL}/ws/services/"
        f"{SERVICE_ID}/?token={token}"
    )


async def client_listener(websocket):
    try:
        while True:
            message = await websocket.recv()

            print("\n========== CLIENT ==========")
            print("Mensagem recebida:")
            print(message)
            print("============================\n")

    except websockets.exceptions.ConnectionClosed as error:
        print(
            f"\n[CLIENT] WebSocket fechado: "
            f"{error.code} - {error.reason}"
        )


async def provider_sender(websocket):
    try:
        for index, (latitude, longitude) in enumerate(
            LOCATIONS,
            start=1,
        ):
            location = {
                "type": "location",
                "latitude": latitude,
                "longitude": longitude,
            }

            print(
                f"\n[PROVIDER] Enviando localização "
                f"{index}/{len(LOCATIONS)}:"
            )

            print(
                json.dumps(
                    location,
                    indent=4,
                )
            )

            await websocket.send(
                json.dumps(location)
            )

            await asyncio.sleep(2)

        print(
            "\n[PROVIDER] Todas as localizações "
            "foram enviadas."
        )

        print(
            "[PROVIDER] Mantendo conexão aberta..."
        )

        await asyncio.Future()

    except websockets.exceptions.ConnectionClosed as error:
        print(
            f"\n[PROVIDER] WebSocket fechado: "
            f"{error.code} - {error.reason}"
        )


async def provider_listener(websocket):
    try:
        while True:
            message = await websocket.recv()

            print(
                "\n[ERRO] PROVIDER recebeu uma mensagem:"
            )
            print(message)

    except websockets.exceptions.ConnectionClosed:
        pass


async def main():
    client_url = get_url(CLIENT_TOKEN)
    provider_url = get_url(PROVIDER_TOKEN)

    print("========================================")
    print("      TESTE WEBSOCKET - DOGGO")
    print("========================================")
    print(f"Service ID: {SERVICE_ID}")
    print()

    print("[CLIENT] Conectando...")

    client = await websockets.connect(
        client_url
    )

    print(
        "[CLIENT] WebSocket conectado!"
    )

    print()

    print("[PROVIDER] Conectando...")

    provider = await websockets.connect(
        provider_url
    )

    print(
        "[PROVIDER] WebSocket conectado!"
    )

    print()
    print("========================================")
    print("Conexões estabelecidas!")
    print("========================================")

    client_task = asyncio.create_task(
        client_listener(client)
    )

    provider_listener_task = asyncio.create_task(
        provider_listener(provider)
    )

    try:
        await provider_sender(provider)

    except KeyboardInterrupt:
        print("\nTeste interrompido.")

    finally:
        client_task.cancel()
        provider_listener_task.cancel()

        await client.close()
        await provider.close()

        print("\nWebSockets fechados.")


if __name__ == "__main__":
    asyncio.run(main())