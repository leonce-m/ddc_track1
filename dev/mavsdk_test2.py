import asyncio
from mavsdk import System, offboard
from mavsdk.action import ActionError


def check_fence(drone, init_pos, dist):
    pos = drone.telemetry.position()
    if any(abs(x+y) > dist for x, y in zip(init_pos, pos)):
        return True


async def run():
    drone = System()
    await drone.connect(system_address="udp://:14550")
    print("Waiting for drone...")
    async for state in drone.core.connection_state():
        if state.is_connected:
            print(f"Drone discovered with UUID: {state.uuid}")
            break
    print("-- Arming")
    await drone.action.arm()
    print("-- Taking off")
    await drone.action.takeoff()
    home_pos = drone.telemetry.position()
    print(home_pos)

    await drone.offboard.set_velocity_ned(offboard.VelocityNedYaw(0.1, 0.1, 0, 0))
    if check_fence(drone, home_pos, 2):
        await drone.action.return_to_launch()
    await asyncio.sleep(5)
    print("-- Landing")
    await drone.action.land()


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(run())
