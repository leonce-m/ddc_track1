import asyncio

from mavsdk import System, offboard
from mavsdk.telemetry import LandedState


def lat_lon(position):
    coords = position.latitude_deg, position.longitude_deg
    return coords

async def get_home_pos(drone):
    async for home in drone.telemetry.home():
        if home:
            print(f"Home: {lat_lon(home)}")
            return home

async def check_dist(drone, init_pos, dist):
    async for pos in drone.telemetry.position():
        for x, y in zip(lat_lon(init_pos), lat_lon(pos)):
            print(f"Distance from home: {abs(x - y)}")
        if any(abs(x-y) > dist for x, y in zip(lat_lon(init_pos), lat_lon(pos))):
            return True
        await asyncio.sleep(1)

async def wait_for(f_condition):
    while True:
        if await f_condition:
            return

async def run():
    drone = System()
    await drone.connect(system_address="udp://:14550")
    print("Waiting for drone...")
    async for state in drone.core.connection_state():
        if state.is_connected:
            print(f"Drone discovered with UUID: {state.uuid}")
            break
    home = await get_home_pos(drone)
    print("-- Arming")
    await drone.action.arm()
    print("-- Taking off")
    await drone.action.takeoff()
    await asyncio.sleep(10)
    await drone.offboard.set_velocity_ned(offboard.VelocityNedYaw(0, 0, 0, 0))
    await drone.offboard.start()
    v = 5
    await drone.offboard.set_velocity_ned(offboard.VelocityNedYaw(v, 0, 0, 0))
    print(f"-- Moving forward at {v} m/s")
    await asyncio.ensure_future(check_dist(drone, home, 5e-07))
    await drone.offboard.stop()
    await drone.action.return_to_launch()
    print("-- Returning Home")
    async for landed in drone.telemetry.landed_state():
        if landed == LandedState.ON_GROUND:
            print("-- Landed")
            break
    await asyncio.sleep(10)
    await drone.action.disarm()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(run())
