import asyncio
import websockets

async def send_signals(websocket):
    while True:
        try:
            await websocket.send("Signal")
            print("Signal sent")
            await asyncio.sleep(2)  # Send signal every 2 seconds
        except websockets.exceptions.ConnectionClosed:
            print("Connection closed while sending signals")
            break

async def handler(websocket, path):
    print("New connection established")
    signal_task = asyncio.create_task(send_signals(websocket))
    try:
        while True:
            # Handle incoming messages, such as pings, to keep the connection alive
            try:
                message = await asyncio.wait_for(websocket.recv(), timeout=10)
                print(f"Received message: {message}")
            except asyncio.TimeoutError:
                print("No message received, sending ping to keep connection alive")
                await websocket.ping()
    except websockets.exceptions.ConnectionClosedError as e:
        print(f"Connection closed: {e}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        signal_task.cancel()
        print("Connection closed")

async def main():
    async with websockets.serve(handler, "0.0.0.0", 6789):
        await asyncio.Future()  # Run forever

if __name__ == "__main__":
    asyncio.run(main())

